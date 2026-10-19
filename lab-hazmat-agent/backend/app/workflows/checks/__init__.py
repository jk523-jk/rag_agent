"""checks 注册。check 均为 async run(ctx) -> list[Finding] 的实例。"""
from __future__ import annotations

from app.workflows.checks import (
    double_entry,
    machine_machine,
    machine_person,
    material,
    person_env,
)

CHECKS = [
    person_env.CHECK,
    material.CHECK,
    machine_machine.CHECK,
    machine_person.CHECK,
    double_entry.CHECK,
]
