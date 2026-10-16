"""政策检索工具。"""
from __future__ import annotations

from langchain_core.tools import tool

from app.rag.retriever import format_hits, retrieve_policy


@tool
async def search_policy(query: str, doc_name: str | None = None) -> str:
    """检索实验室安全规程、危化品管理制度与重点试剂 SDS 摘要。

    用于回答"应该怎么做"类问题：药品存放要求、领用规定（是否需双人/见证人）、
    资质过期的处置流程、泄漏应急处置。查不到时如实返回"规程中未找到相关规定"。
    """
    docs = await retrieve_policy(query, doc_name=doc_name)
    return format_hits(docs)
