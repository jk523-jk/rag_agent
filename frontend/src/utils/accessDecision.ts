// 准入三闸判定：与后端 app/tools/access_tools.py 的 _judge 保持同一口径。
//
// 闸位顺序固定为 资质闸 → 授权闸 → 双人闸，任一闸未通过即短路，不再评估后续闸位。
// 顺序固定是为了防住最常见的人工失误——只看了授权、忘了资质。
//
// 两条容易写错的口径，前端必须一致：
// 1. 资质是否有效一律以 expireDate 与判定日期比较为准，**不看 status 字段**：
//    库里存在「status 仍是有效、expireDate 早已过期」的记录（王某的合格证即如此），
//    只看 status 会漏判。当天到期算有效。
// 2. 双人闸查不到当天记录时 fail-closed，判「需双人同行」而非放行——
//    无记录不等于满足双人要求，宁可拦下让人工核实。
import type {
  AccessDecision, AccessEvent, AccessVerdict, Lab, LabAuthorization, Qualification,
} from '@/types'

/** 判定所需的输入快照 */
export interface AccessInput {
  personName: string
  empNo: string
  role: string
  lab: Lab
  /** 判定日期 YYYY-MM-DD 或完整时间戳 */
  atDate: string
  /** 该人全部资质 */
  qualifications: Qualification[]
  /** 该人全部授权 */
  authorizations: LabAuthorization[]
  /** 该实验室的全部通行事件，用于双人闸 */
  accessEvents: AccessEvent[]
}

/** 安全考试合格证是资质闸唯一认可的证书类型（与后端一致） */
const CERT_GATE_TYPE = '安全考试合格证'

/** 取日期部分，便于与 YYYY-MM-DD 字段做字典序比较 */
function dayOf(value: string): string {
  return value.slice(0, 10)
}

/**
 * 同一资质类型可能因换证/复审存在多条记录，只保留 expireDate 最新一条，
 * 否则逐条判定会输出互相矛盾的结论（与后端按 person_id 去重同理）。
 */
function latestQualification(list: Qualification[], certType: string): Qualification | null {
  const matched = list.filter((q) => q.certType === certType)
  if (!matched.length) return null
  return matched.reduce((a, b) => (b.expireDate > a.expireDate ? b : a))
}

/**
 * 双人闸证据：取判定当日「进 + 通过」事件的最大同行人数。
 * 只认「进」和「通过」，拒绝/超时/出方向都不算证据——
 * 顺序一变就翻转结论的判定是不可靠的。
 */
function maxCompanionSameDay(events: AccessEvent[], labId: string, atDate: string): number | null {
  const day = dayOf(atDate)
  const evidence = events.filter(
    (e) => e.labId === labId && e.direction === '进' && e.authResult === '通过' && dayOf(e.eventTime) === day,
  )
  if (!evidence.length) return null
  return Math.max(...evidence.map((e) => e.companionNo ?? 0))
}

/**
 * 执行三闸判定，返回结论与逐条理由。
 * 结论词汇严格限定为四值：资质过期 / 无授权 / 需双人同行 / 准予进入。
 */
export function judge(input: AccessInput): AccessDecision {
  const { lab, atDate } = input
  const day = dayOf(atDate)
  const reasons: string[] = []

  // ---------- 闸 1：资质闸 ----------
  const cert = latestQualification(input.qualifications, CERT_GATE_TYPE)
  const certOk = !!cert && cert.expireDate >= day
  if (certOk) {
    reasons.push(
      `资质闸：通过（${CERT_GATE_TYPE} ${cert!.certNo}，有效期至 ${cert!.expireDate}，状态 ${cert!.status}）`,
    )
  } else {
    const detail = cert
      ? `${CERT_GATE_TYPE} ${cert.certNo}，有效期至 ${cert.expireDate}，状态 ${cert.status}`
      : `未登记${CERT_GATE_TYPE}`
    reasons.push(`资质闸：未通过（${detail}）`)
    // 状态与有效期不一致时明确点出，避免用户以为系统读错
    if (cert && cert.status === '有效' && cert.expireDate < day) {
      reasons.push(`说明：该证书状态仍登记为「有效」，但有效期已于 ${cert.expireDate} 届满，判定以有效期为准。`)
    }
    return { verdict: '资质过期', reasons, failedGate: '资质闸' }
  }

  // ---------- 闸 2：授权闸 ----------
  const auth = input.authorizations.find((a) => a.labId === lab.labId) ?? null
  const authOk = !!auth && auth.status === '有效' && auth.authFrom <= day && day <= auth.authTo
  if (authOk) {
    reasons.push(`授权闸：通过（${auth!.authFrom} ~ ${auth!.authTo}，状态 ${auth!.status}，授权人 ${auth!.grantor}）`)
  } else {
    const detail = auth
      ? `${auth.authFrom} ~ ${auth.authTo}，状态 ${auth.status}，授权人 ${auth.grantor}`
      : `未登记该实验室授权`
    reasons.push(`授权闸：未通过（${detail}）`)
    return { verdict: '无授权', reasons, failedGate: '授权闸' }
  }

  // ---------- 闸 3：双人闸（仅需双人的实验室）----------
  if (!lab.needsDouble) {
    reasons.push('双人闸：本实验室不要求双人准入，无需核查。')
    reasons.push('结论：三闸全部通过。')
    return { verdict: '准予进入', reasons, failedGate: null }
  }

  const companion = maxCompanionSameDay(input.accessEvents, lab.labId, atDate)
  if (companion === null) {
    reasons.push(
      `双人闸：未通过（${day} 未查到本人在 ${lab.labId} 的「进 + 通过」通行记录，` +
        '无法证明双人同行，按从严原则判定）。',
    )
    return { verdict: '需双人同行', reasons, failedGate: '双人闸' }
  }
  if (companion < 1) {
    reasons.push(`双人闸：未通过（${day} 最大同行人数 ${companion}，不足 1 人）。`)
    return { verdict: '需双人同行', reasons, failedGate: '双人闸' }
  }
  reasons.push(`双人闸：通过（${day} 最大同行人数 ${companion}）。`)
  reasons.push('结论：三闸全部通过。')
  return { verdict: '准予进入', reasons, failedGate: null }
}

/** 结论对应的展示色调。不能只靠颜色区分，页面须同时渲染文字结论。 */
export function verdictTone(v: AccessVerdict): 'success' | 'failed' | 'warning' {
  if (v === '准予进入') return 'success'
  if (v === '需双人同行') return 'warning'
  return 'failed'
}
