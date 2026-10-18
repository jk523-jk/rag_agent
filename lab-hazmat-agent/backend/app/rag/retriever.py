"""检索：MMR 去重 + 相似度阈值兜底 + 元数据过滤（三份文档不串味）。

关键修正：**向量空间必须显式指定为 cosine**。
Chroma 默认用 l2 距离，而 langchain-chroma 的 `_select_relevance_score_fn`
在未指定 distance 时按 collection 配置走 l2，得到的是欧氏距离归一化值，
在 embedding 维度很高时几乎所有结果都挤在 0.3 以上——阈值形同虚设，
"严禁编造条款"的兜底就失效了。建索引与查询两侧都锁定 cosine（见 settings）。
"""
from __future__ import annotations

import logging
from functools import lru_cache

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from app.core.config import get_settings

log = logging.getLogger(__name__)
COLLECTION = "lab_policy"
# 建索引与查询必须一致，否则相关度阈值没有可比性
COLLECTION_CONFIG = {"hnsw": {"space": "cosine"}}


@lru_cache
def known_doc_names() -> tuple[str, ...]:
    """语料文件名（即 doc_name），用于把问题绑定到具体文档。

    语料目录取 CHROMA_DIR 的上一级（默认 <项目根>/corpus）。
    """
    s = get_settings()
    corpus = s.chroma_path.parent
    names = [p.stem for p in sorted(corpus.glob("*.md"))]
    names += [p.stem for p in sorted((corpus / "sds").glob("*.md"))]
    return tuple(names)


def match_docs(question: str) -> list[str]:
    """问题里出现的化学品/文档名。

    为什么要做这一步：SDS 按四段硬隔离只保证**单个文档内**不串段，
    但检索时问「丙酮着火」仍可能召回《氰化钾》的灭火条目——实测模型据此
    回答「丙酮着火用雾状水」（错，丙酮与水互溶）。语料里每个 SDS 都以
    化学品名命名，所以问题里出现哪个名字，就把检索限定在那份文档。
    """
    q = question or ""
    return [n for n in known_doc_names() if n and n in q]


def _embeddings() -> OpenAIEmbeddings:
    s = get_settings()
    return OpenAIEmbeddings(
        model=s.embed_model,
        base_url=s.llm_base_url,
        api_key=s.llm_api_key,
        # DashScope 兼容模式只接受原始字符串，不接受 token id 数组。
        # langchain_openai 默认会先 tiktoken 分词再发送（为了绕开 OpenAI 的 token 上限），
        # 在 DashScope 上会报 400 InvalidParameter: contents is neither str nor list of str。
        check_embedding_ctx_length=False,
        # DashScope text-embedding-v3 单次请求上限 10 条，langchain 默认 chunk_size=1000。
        chunk_size=10,
    )


@lru_cache
def _store() -> Chroma:
    s = get_settings()
    return Chroma(
        collection_name=COLLECTION,
        embedding_function=_embeddings(),
        persist_directory=str(s.chroma_path),
        collection_configuration=COLLECTION_CONFIG,
    )


def reset_store() -> None:
    """清掉缓存的 store（索引重建后调用，避免拿到旧句柄）。"""
    _store.cache_clear()


async def retrieve_policy(
    query: str,
    doc_name: str | None = None,
    kind: str | None = None,
    k: int | None = None,
) -> list[Document]:
    """返回命中的规程片段；低于阈值一律返回空（严禁编造条款）。"""
    s = get_settings()
    top_k = k or s.rag_top_k
    store = _store()

    where: dict = {}
    if doc_name:
        where["doc_name"] = doc_name
    else:
        # 问题里点了名就锁定文档：问「丙酮着火」不准拿《氰化钾》的灭火条目来答
        docs = match_docs(query)
        if len(docs) == 1:
            where["doc_name"] = docs[0]
        elif len(docs) > 1:
            where["doc_name"] = {"$in": docs}
    if kind:
        where["kind"] = kind

    try:
        scored = await store.asimilarity_search_with_relevance_scores(
            query, k=s.rag_fetch_k, filter=where or None
        )
    except Exception as exc:                                      # noqa: BLE001
        log.warning("向量检索失败（返回空结果，避免编造条款）：%s: %s", type(exc).__name__, exc)
        return []

    if not scored:
        return []

    best = max(score for _, score in scored)
    if best < s.rag_score_threshold:
        log.info("检索最高相关度 %.3f 低于阈值 %.2f，按无命中处理",
                 best, s.rag_score_threshold)
        return []

    try:
        return await store.amax_marginal_relevance_search(
            query, k=top_k, fetch_k=s.rag_fetch_k, lambda_mult=0.5, filter=where or None
        )
    except Exception as exc:                                      # noqa: BLE001
        log.warning("MMR 检索失败，退回按相关度取前 %d 条：%s", top_k, type(exc).__name__)
        return [doc for doc, _ in scored[:top_k]]


def format_hits(docs: list[Document]) -> str:
    if not docs:
        return "规程中未找到相关规定。"
    blocks = []
    for i, d in enumerate(docs, 1):
        loc = d.metadata.get("chapter") or d.metadata.get("section") or "-"
        blocks.append(f"[{i}] 来源：《{d.metadata.get('doc_name')}》{loc}\n{d.page_content}")
    return "\n\n".join(blocks)
