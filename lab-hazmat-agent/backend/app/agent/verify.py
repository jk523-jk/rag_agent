"""回答后置校验：不信任模型复述，机械核对日期、数量区间与准入结论。

为什么需要这一层（都是实测发生过的）：
| 工具返回 | 模型回答 |
|---|---|
| `数据截至 2026-10-16 20:37` | `截至 2024-04-05 16:30` |
| `少量（不足 5 克）` | `10–50 克` |
| `资质有效期至 2026-10-06`（已过期） | `当前为 2024-04-05` → 判成「有效」 |

提示词第 10 条要求"原样照抄"只能降低概率，不能消除。这里做机械核对，
策略是「能改就改，改不了就标注，结论无依据就不给结论」。

三档处置：
A. 结论词无依据（只对"准入类问题"启用）→ **作废结论**，返回安全话术。
   宁可答不出来，也不能放错人。
B. 日期 / 数量区间与证据不符 → 自动替换为证据原文，并在末尾注明已校正。
C. 无法安全替换 → 不改正文，末尾追加"以查询结果为准"的提示。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

# 准入结论四值（与工具层严格一致）
VERDICTS = ("准予进入", "资质过期", "无授权", "需双人同行")

DATE_RE = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")
# 「数据截至 2026-10-16」这类时间锚点
ASOF_RE = re.compile(r"(?:数据截至|数据更新于|更新于|截至)[^0-9]{0,6}(20\d{2}-\d{2}-\d{2})")
# 数量区间：约 5–10 瓶 / 10-50 克 / 少量（不足 5 克）/ 不足 5 克
RANGE_RE = re.compile(
    r"(?:少量[^。；，,]{0,14}?(?:克|瓶|毫升)）?"
    r"|不足\s*\d+(?:\.\d+)?\s*(?:克|瓶|毫升)）?"
    r"|约?\s*\d+(?:\.\d+)?\s*[-–—~～至到]\s*\d+(?:\.\d+)?\s*(?:克|瓶|毫升)）?)"
)
UNIT_RE = re.compile(r"(克|瓶|毫升)")

# 只在这些问法上启用「结论无依据即作废」
ACCESS_INTENT = re.compile(
    r"(能不能|能否|可不可以|可以不可以)[^。？！]{0,10}(进|入|进入)"
    r"|准入|能否进入|可以进入"
)

# 需要查库/检索才能回答的事实类问题
FACTUAL_INTENT = re.compile(
    r"库存|结存|台账|领用|资质|证书|授权|准入|能不能进|能否进|"
    r"校准|借出|借用|逾期|未还|门禁|通行|记录|"
    r"规程|规定|标准|要求|流程|手续|处置|灭火|储存|存放|SDS|"
    r"多少|几个|几瓶|几台|哪些|哪个|谁|什么时候|是否"
)

# 寒暄 / 自我介绍类，不需要查库
META_INTENT = re.compile(r"^\s*(你好|您好|你是谁|你能做什么|能干什么|有什么功能|帮助|谢谢|感谢|在吗)")

SAFE_REPLY = (
    "本次未能取得可信的准入结论：回答里的结论没有对应的查询依据，系统已作废该结论。\n"
    "请重试，或直接指定人员与实验室编号（如「王某 T2023001 能否进入 LAB-3」）。\n"
    "如仍异常，请联系实验室安全负责人人工核实。"
)

# 事实类问题但一次工具都没调：回答必然是编的（实测模型会直接编出库存和日期）
NO_EVIDENCE_REPLY = (
    "本次未能取得查询依据：回答没有对应的工具查询结果，系统已作废该回答。\n"
    "请重试，或把问题说得更具体（注明人员姓名/工号、实验室编号或化学品名称）。"
)

# 工具明确说没查到，模型却给出具体数值或时间——同样是编的
NOT_FOUND_RE = re.compile(r"未找到|不存在|未匹配到|查无")
NOT_FOUND_REPLY = (
    "查询未返回可用记录，回答里的具体数值与时间已作废。\n"
    "请确认名称或编号（化学品建议直接给 CAS 号）后重试；"
    "若确认台账应有该条目，请联系实验室安全负责人核对。"
)


@dataclass
class Issue:
    kind: str          # date_unverified / range_mismatch / verdict_unfounded / asof_fixed
    claim: str         # 模型说的
    evidence: str      # 证据里有的（可能为空）
    fixed: bool        # 是否已自动改掉


@dataclass
class VerifyResult:
    ok: bool
    reply: str
    issues: list[Issue] = field(default_factory=list)
    severity: str = "none"      # none / low / medium / high

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "severity": self.severity,
            "issues": [
                {"kind": i.kind, "claim": i.claim, "evidence": i.evidence, "fixed": i.fixed}
                for i in self.issues
            ],
        }


def _norm(text: str) -> str:
    """归一化：去空白、统一各种横线与波浪号，便于比较。"""
    t = re.sub(r"\s+", "", text)
    for ch in ("－", "—", "–", "~", "～", "至", "到"):
        t = t.replace(ch, "-")
    return t


def _evidence_text(tool_outputs: list[str], now_text: str, question: str) -> str:
    return "\n".join([*tool_outputs, now_text, question])


def _fix_ranges(reply: str, evidence: str, issues: list[Issue]) -> tuple[str, bool]:
    """把与证据不符的数量区间替换为证据原文（按单位唯一匹配时才替换）。"""
    ev_norm = _norm(evidence)
    claims = [m.group(0) for m in RANGE_RE.finditer(reply)]
    if not claims:
        return reply, False

    # 证据里的区间原文（去重）
    ev_claims = [m.group(0).strip() for m in RANGE_RE.finditer(evidence)]
    by_unit: dict[str, set[str]] = {}
    for c in ev_claims:
        u = UNIT_RE.search(c)
        if u:
            by_unit.setdefault(u.group(1), set()).add(c)

    changed = False
    for claim in claims:
        if _norm(claim) in ev_norm:
            continue
        u = UNIT_RE.search(claim)
        candidates = by_unit.get(u.group(1)) if u else None
        if candidates and len(candidates) == 1:
            replacement = next(iter(candidates))
            reply = reply.replace(claim, replacement)
            issues.append(Issue("range_mismatch", claim, replacement, fixed=True))
            changed = True
        else:
            issues.append(Issue("range_mismatch", claim, "、".join(sorted(candidates or [])), fixed=False))
    return reply, changed


def _fix_asof(reply: str, evidence: str, issues: list[Issue], now_text: str = "") -> tuple[str, bool]:
    """「数据截至 X」里的日期若与证据不符，换成证据里的那个日期。

    证据里没有「数据截至」时（例如设备清单只回有效期），以**服务器当天**为准：
    这类回答的时间锚点本来就是"查询时刻"，模型常把它写成上一年（实测 2024-10-18）。
    """
    ev_asof = ASOF_RE.findall(evidence)
    if ev_asof:
        truth = ev_asof[0]
        source = "evidence"
    else:
        m = DATE_RE.search(now_text or "")
        if not m:
            return reply, False
        truth = m.group(0)
        source = "server_date"
    changed = False

    def repl(m: re.Match) -> str:
        nonlocal changed
        claim = m.group(1)
        if claim == truth:
            return m.group(0)
        changed = True
        issues.append(Issue("asof_fixed" if source == "evidence" else "asof_to_today",
                            claim, truth, fixed=True))
        return m.group(0).replace(claim, truth)

    return ASOF_RE.sub(repl, reply), changed


def _check_dates(reply: str, evidence: str, issues: list[Issue]) -> list[str]:
    """返回回答里出现、但证据中没有的日期。"""
    allowed = set(DATE_RE.findall(evidence))
    allowed_text = {"-".join(t) for t in allowed}
    unverified = []
    for m in DATE_RE.finditer(reply):
        d = m.group(0)
        if d not in allowed_text:
            unverified.append(d)
    for d in sorted(set(unverified)):
        issues.append(Issue("date_unverified", d, "", fixed=False))
    return sorted(set(unverified))


def verify_reply(
    reply: str,
    tool_outputs: list[str],
    *,
    question: str = "",
    now_text: str = "",
) -> VerifyResult:
    """核对模型回答与工具证据是否一致。返回可能被修正过的回答。"""
    text = (reply or "").strip()
    if not text:
        return VerifyResult(ok=True, reply=reply)

    evidence = _evidence_text(tool_outputs, now_text, question)
    issues: list[Issue] = []

    # —— A0 档：事实类问题却一次工具都没调 ——
    # 实测模型会跳过工具直接编出「少量（不足 5 克）」和「数据截至 2024-04-15」，
    # 这种回答没有任何证据可核对，只能整体作废。
    if not any((t or "").strip() for t in tool_outputs):
        if META_INTENT.search(question) or not question.strip():
            return VerifyResult(ok=True, reply=reply)
        if FACTUAL_INTENT.search(question):
            log.error("事实类问题未调用任何工具，回答已作废：%s", question[:60])
            issues.append(Issue("no_evidence", question[:40], "", fixed=True))
            return VerifyResult(ok=False, reply=NO_EVIDENCE_REPLY, issues=issues, severity="high")

    # —— A0.5 档：工具明确说没查到，回答却给出了数值/日期 ——
    if tool_outputs and all(NOT_FOUND_RE.search(t or "") for t in tool_outputs):
        if RANGE_RE.search(text) or DATE_RE.search(text):
            log.error("工具返回未找到，回答却给出具体数值/日期，已作废：%s", question[:60])
            issues.append(Issue("not_found_but_asserted", text[:40], "工具返回未找到", fixed=True))
            return VerifyResult(ok=False, reply=NOT_FOUND_REPLY, issues=issues, severity="high")

    # —— A 档：准入结论必须有工具依据 ——
    if ACCESS_INTENT.search(question):
        ev = _norm(evidence)
        claimed = [v for v in VERDICTS if v in text]
        unfounded = [v for v in claimed if v not in ev]
        if unfounded:
            log.error("准入结论缺少工具依据：%s（问题：%s）", unfounded, question[:60])
            for v in unfounded:
                issues.append(Issue("verdict_unfounded", v, "", fixed=True))
            return VerifyResult(ok=False, reply=SAFE_REPLY, issues=issues, severity="high")

    # —— B/C 档：日期与区间 ——
    text, asof_fixed = _fix_asof(text, evidence, issues, now_text)
    text, range_fixed = _fix_ranges(text, evidence, issues)
    unverified_dates = _check_dates(text, evidence, issues)

    fixed_any = asof_fixed or range_fixed
    if fixed_any:
        text = text.rstrip() + "\n\n（已按查询结果校正时间与数量；以工具返回为准。）"
    elif unverified_dates:
        # 无法确定该换成哪一天：不改正文，避免把别的日期改坏
        text = text.rstrip() + (
            f"\n\n（提示：回答中的日期 {'、'.join(unverified_dates)} 未在本次查询结果中出现，请以查询结果为准。）"
        )

    severity = "medium" if fixed_any else ("low" if unverified_dates else "none")
    return VerifyResult(ok=not fixed_any and not unverified_dates, reply=text, issues=issues, severity=severity)


__all__ = ["verify_reply", "VerifyResult", "Issue", "SAFE_REPLY", "NO_EVIDENCE_REPLY", "NOT_FOUND_REPLY", "VERDICTS"]
