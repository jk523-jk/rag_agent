"""分级切分：SDS 按小节，规程按条款。切完带元数据入 Chroma。

红线（对应开发文档 §5.1）：SDS 绝不能用固定长度硬切，否则"储存条件"和"应急措施"
会进同一个 chunk，模型可能把储存要求当成泄漏处置措施讲出来——这是安全要求。
"""
from __future__ import annotations

import re
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import get_settings

SDS_SECTIONS = ["理化特性", "危害", "储存", "应急处置"]      # 固定四段，顺序不可乱
CLAUSE_SPLITTER = re.compile(r"(?=第[一二三四五六七八九十百零〇\d]+条)")
# 章节标题（用于"一、XX""第一章 XX"这类非条款式制度文档）
HEADING_SPLITTER = re.compile(r"^#{1,4}\s*(.+?)\s*$", re.M)

# 标题 → 四段语义 的归并映射。SDS 语料实际用国标 16 项细分标题，
# 这里把它们收敛到文档要求的四段，保证「应急处置」绝不混入「储存」。
_SECTION_ALIAS = {
    "标识信息": "理化特性",
    "理化特性": "理化特性",
    "成分组成": "理化特性",
    "危险性概述": "危害",
    "危害": "危害",
    "健康危害": "危害",
    "急救措施": "危害",          # 急救属危害范畴（中毒/灼伤处置）
    "消防措施": "危害",          # 火灾危险性归危害
    "储存要求": "储存",
    "储存": "储存",
    "操作处置与储存": "储存",
    "泄漏应急处理": "应急处置",
    "应急处置": "应急处置",
    "泄漏处理": "应急处置",
    "废弃处置": "应急处置",
}

_inside = RecursiveCharacterTextSplitter(
    chunk_size=800, chunk_overlap=100, separators=["\n\n", "\n", "。", "；", ""]
)


def split_policy(text: str, doc_name: str) -> list[Document]:
    """规程/制度：按条款或章节标题切，一条即一 chunk（过长再细分）。"""
    docs: list[Document] = []
    # 优先按"第X条"切；若无条款（如"一、二、三"式制度），退回按 ## 标题切
    if CLAUSE_SPLITTER.search(text):
        parts = CLAUSE_SPLITTER.split(text)
    else:
        # 按标题切，标题作为章节名
        marks = [(m.start(), m.group(1).strip()) for m in HEADING_SPLITTER.finditer(text)]
        parts = []
        for idx, (pos, title) in enumerate(marks):
            if title.startswith("#") or len(title) < 2:
                continue
            end = marks[idx + 1][0] if idx + 1 < len(marks) else len(text)
            body = text[pos:end].strip()
            body = "\n".join(l for l in body.splitlines() if not l.lstrip().startswith("#")).strip()
            parts.append(f"## {title}\n{body}")

    for raw in parts:
        raw = raw.strip()
        if not raw:
            continue
        chapter = raw.split("\n", 1)[0][:32]
        for i, piece in enumerate(_inside.split_text(raw)):
            docs.append(Document(
                page_content=piece,
                metadata={"doc_name": doc_name, "chapter": chapter, "kind": "policy", "part": i},
            ))
    return docs


def split_sds(text: str, doc_name: str) -> list[Document]:
    """SDS：先按小节硬隔离，再在小节内细分。跨小节绝不允许出现在同一 chunk。

    现有语料用国标 SDS 细分标题（标识/危险性/急救/消防/储存/泄漏），
    切分时经 _SECTION_ALIAS 归并到文档要求的四段语义，保证
    「应急处置」（泄漏处理）不会和「储存」落在同一 chunk。
    """
    # 提取所有标题及其位置（跳过文档级 # 标题）
    marks: list[tuple[int, str]] = []
    for m in HEADING_SPLITTER.finditer(text):
        title = m.group(1).strip()
        section = _SECTION_ALIAS.get(title)
        if section is None:
            continue                      # 不在映射表里的标题（如文档标题）跳过
        marks.append((m.start(), section))

    if not marks:
        raise ValueError(f"{doc_name} 未识别到 SDS 小节标题，拒绝入库（避免被硬切）")

    # 相邻同段合并成一段，避免同一语义被标题拆碎
    merged: list[tuple[str, list[str]]] = []
    for idx, (pos, section) in enumerate(marks):
        end = marks[idx + 1][0] if idx + 1 < len(marks) else len(text)
        body = text[pos:end].strip()
        # 去掉本段标题行本身，只留正文
        body = "\n".join(line for line in body.splitlines() if not line.lstrip().startswith("#"))
        body = body.strip()
        if not body:
            continue
        if merged and merged[-1][0] == section:
            merged[-1][1].append(body)
        else:
            merged.append((section, [body]))

    docs: list[Document] = []
    for section, bodies in merged:
        joined = "\n\n".join(bodies)
        for i, piece in enumerate(_inside.split_text(joined)):
            docs.append(Document(
                page_content=piece,
                metadata={"doc_name": doc_name, "section": section, "kind": "sds", "part": i},
            ))
    return docs


def build_index(corpus_dir: str = "corpus", reset: bool = True) -> None:
    """建索引。向量空间锁定 cosine，与检索侧 COLLECTION_CONFIG 保持一致。

    reset=True 时先删旧集合再重建，避免重复执行导致 chunk 成倍累积
    （原实现每次调用都是 append，跑两次就有两份语料，检索结果会重复）。
    """
    from app.rag.retriever import COLLECTION, COLLECTION_CONFIG, reset_store

    s = get_settings()
    embeddings = OpenAIEmbeddings(
        model=s.embed_model,
        base_url=s.llm_base_url,
        api_key=s.llm_api_key,
        # 与 retriever._embeddings() 保持一致：DashScope 兼容模式不接受 token id 数组
        check_embedding_ctx_length=False,
        # DashScope 单批最多 10 条
        chunk_size=10,
    )
    docs: list[Document] = []
    root = Path(corpus_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"语料目录不存在：{root.resolve()}")

    for p in sorted(root.glob("*.md")):
        docs += split_policy(p.read_text(encoding="utf-8"), p.stem)
    for p in sorted((root / "sds").glob("*.md")):
        docs += split_sds(p.read_text(encoding="utf-8"), p.stem)

    if not docs:
        raise ValueError(f"{root.resolve()} 下没有切出任何 chunk，请检查语料格式。")

    if reset:
        try:
            old = Chroma(
                collection_name=COLLECTION,
                embedding_function=embeddings,
                persist_directory=str(s.chroma_path),
                collection_configuration=COLLECTION_CONFIG,
            )
            old.delete_collection()
            print(f"已删除旧集合 {COLLECTION}")
        except Exception as exc:                                  # noqa: BLE001
            print(f"删除旧集合跳过（可能本就不存在）：{type(exc).__name__}")

    Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        collection_name=COLLECTION,
        persist_directory=str(s.chroma_path),
        collection_configuration=COLLECTION_CONFIG,
    )
    reset_store()                       # 丢掉可能已缓存的旧句柄

    by_kind: dict[str, int] = {}
    by_section: dict[str, int] = {}
    for d in docs:
        by_kind[d.metadata["kind"]] = by_kind.get(d.metadata["kind"], 0) + 1
        sec = d.metadata.get("section")
        if sec:
            by_section[sec] = by_section.get(sec, 0) + 1
    print(f"入库 {len(docs)} 个 chunk：{by_kind}")
    if by_section:
        print(f"SDS 四段分布：{by_section}")


if __name__ == "__main__":
    import sys

    build_index(sys.argv[1] if len(sys.argv) > 1 else "corpus")
