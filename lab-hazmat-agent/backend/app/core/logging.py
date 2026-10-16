"""结构化日志。合规硬要求：日志不落盘姓名、工号与化学品精确数量。"""
from __future__ import annotations

import logging
import sys

_MASK_KEYS = {"name", "person_name", "emp_no", "cert_no", "quantity", "witness_id"}


def scrub(payload: dict) -> dict:
    """结构化日志过滤器：命中敏感键一律替换为占位符。"""
    out = {}
    for k, v in payload.items():
        if k in _MASK_KEYS:
            out[k] = "***"
        elif isinstance(v, dict):
            out[k] = scrub(v)
        elif isinstance(v, list):
            out[k] = [scrub(x) if isinstance(x, dict) else x for x in v]
        else:
            out[k] = v
    return out


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
