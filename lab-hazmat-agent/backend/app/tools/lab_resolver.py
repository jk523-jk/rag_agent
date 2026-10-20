"""Shared resolver for laboratory IDs and display names."""
from __future__ import annotations

from app.db.connection import fetch_all

_SQL_LAB_LOOKUP = """
SELECT lab_id, lab_name FROM labs
WHERE lab_id = %(key)s OR lab_name = %(key)s
LIMIT 1
"""


async def resolve_lab(lab_id: str | None) -> tuple[str | None, str]:
    """Normalize a laboratory ID/name to its ID, returning a user-facing hint on failure."""
    if not lab_id or not str(lab_id).strip():
        return None, ""
    key = str(lab_id).strip()
    rows = await fetch_all(_SQL_LAB_LOOKUP, {"key": key})
    if rows:
        return rows[0]["lab_id"], ""
    return None, f"未识别实验室「{key}」。可用编号 LAB-1 ~ LAB-5，或实验室名称（如「剧毒品间」）。"
