// 对话模拟引擎：根据问题关键词返回预设回答，按片段流式输出。
// 全部内容为演示数据，回答中会明确标注“模拟”。不声称连接了真实模型。
import type { ChatSource } from '@/types'
import { detectControlIntent, toInterval } from '@/utils/guard'

export interface SimAnswer {
  text: string
  sources: ChatSource[]
  refused: boolean
}

// 引用来源为内联常量。原实现从知识库分块数据里按 id 查（ck-001…），
// 知识库页面移除后该数据源不复存在，改为在此就地定义，避免悬空引用。
const SOURCES = {
  doubleRule: { docName: '危化品管理制度', chapter: '第十二条', text: '剧毒化学品与易制爆化学品的领用，必须由两人共同完成，其中一人为见证人，并在领用记录中登记见证人工号。' },
  acetoneSpill: { docName: '丙酮_SDS', chapter: '应急处置', text: '泄漏处置：立即疏散无关人员，切断火源，佩戴防毒面具与耐溶剂手套，使用惰性材料吸附后装入密闭容器，按危废流程上报。' },
  acetoneStorage: { docName: '丙酮_SDS', chapter: '储存', text: '储存于阴凉、通风的专用防火柜中，远离氧化剂与火源，容器密封保存。' },
  certExpired: { docName: '实验室安全规程', chapter: '第二十一条', text: '人员资质过期的，不得进入危化品实验室；已进入的，应立即停止作业并由实验室负责人登记处置。' },
} as const

const src = (key: keyof typeof SOURCES, similarity: number, rerank: number): ChatSource => ({
  ...SOURCES[key],
  similarity,
  rerank,
})

export function answerFor(question: string): SimAnswer {
  const refusal = detectControlIntent(question)
  if (refusal) return { text: refusal, sources: [], refused: true }

  const q = question

  if (/双人|见证|几个人/.test(q)) {
    return {
      text:
        '**结论**：剧毒化学品与易制爆化学品的领用需要**两人共同完成**，其中一人为见证人，并在领用记录中登记见证人工号。\n\n' +
        '依据：[规程] 《危化品管理制度》第十二条。\n\n数据覆盖：制度原文，模拟数据。',
      sources: [src('doubleRule', 0.81, 0.93)],
      refused: false,
    }
  }

  if (/丙酮/.test(q) && /泄漏|处置|应急/.test(q)) {
    return {
      text:
        '**结论**：丙酮泄漏按 SDS「应急处置」小节处理：\n\n' +
        '1. 立即疏散无关人员，切断火源；\n' +
        '2. 佩戴防毒面具与耐溶剂手套；\n' +
        '3. 用惰性材料吸附后装入密闭容器；\n' +
        '4. 按危废流程上报。\n\n依据：[规程] 丙酮 SDS 应急处置小节（仅引用该小节，不含储存要求）。\n\n数据覆盖：SDS 摘要，模拟数据。',
      sources: [src('acetoneSpill', 0.79, 0.9)],
      refused: false,
    }
  }

  if (/丙酮/.test(q) && /台账|领用|对得上|瓶/.test(q)) {
    // 演示口径与 reconcile_inventory 一致：未提供期初结存时，按“领用是否超过现有结存”做周转校验
    const bookQty = 8
    const usedQty = 12
    const threshold = Math.max(1, bookQty * 0.05)
    const diff = usedQty - bookQty
    const anomaly = Math.abs(diff) > threshold
    return {
      text:
        `**结论**：${anomaly ? '存在账物不符，需要核实' : '在合理损耗范围内，暂未发现异常'}（演示）。\n\n` +
        `- 台账结存：${bookQty} 瓶\n` +
        `- 近 30 天领用：${usedQty} 瓶，共 3 笔\n` +
        `- 比对口径：未提供期初结存，按周转校验，领用合计 ${usedQty} 瓶超过现有结存 ${bookQty} 瓶\n` +
        `- 差异：+${diff.toFixed(2)} 瓶（合理损耗阈值 ±${threshold.toFixed(2)} 瓶）\n\n` +
        '建议：核对出入库单与领用记录的时间窗口是否一致，并按《危化品管理制度》的盘点与上报条款处理。\n\n' +
        '依据：[数据] 台账核查演示结果。\n\n' +
        '数据覆盖：近 30 天，台账更新时间 2026-10-14，仅供参考。',
      sources: [],
      refused: false,
    }
  }

  if (/剧毒/.test(q) && /精确|多少|剩|还剩/.test(q)) {
    return {
      text:
        `当前剧毒品柜结存（演示）：${toInterval(0.8, '克')}。\n\n` +
        '剧毒品精确数量不予直接提供，如需精确值请联系实验室安全负责人。\n\n' +
        '为什么只给区间：精确结存属于合规敏感信息；区间宽度随数量增大而变宽（不足 5 显示“少量”，5–50 按 5 分段，50–500 按 50 分段，以上按 500 分段），' +
        '这样反复提问也无法反推出精确值。\n\n数据覆盖：台账演示数据。',
      sources: [],
      refused: false,
    }
  }

  // 设备类问法：与后端 equipment_tools 的口径一致——校准以有效期为准，不看状态字段
  if (/校准|检定|送检/.test(q)) {
    return {
      text:
        '**结论**：当前有 1 台设备校准已过期，1 台将在 30 天内到期（演示）。\n\n' +
        '- EQ-0002 气相色谱质谱联用仪：校准已于 2026-09-25 到期，**已过期 20 天**\n' +
        '  · 台账状态仍登记为「在用」，但校准过期一律以校准有效期为准，不得用于出具数据\n' +
        '  · 保管人 张某（T2021001），LAB-2\n' +
        '- EQ-0007 便携式气体检测仪：校准将于 2026-10-30 到期（15 天后）\n' +
        '  · 保管人 张某（T2021001），LAB-5\n\n' +
        '后续处置：校准过期的设备应停止用于出具数据并安排送检；是否需要停用请咨询实验室安全负责人。\n\n' +
        '依据：[数据] list_calibration_due 演示结果。\n\n数据覆盖：预警窗口 30 天，模拟数据。',
      sources: [],
      refused: false,
    }
  }

  if (/借|归还|逾期/.test(q) && !/手续|流程|多久|多少天|规定/.test(q)) {
    return {
      text:
        '**结论**：便携式气体检测仪（EQ-0007）当前被借出且已逾期未还（演示）。\n\n' +
        '- 持有人：赵某（S2024002）\n' +
        '- 借出时间：2026-10-05 09:00\n' +
        '- 应还时间：2026-10-12 18:00 —— **已逾期 3 天**\n' +
        '- 用途：剧毒品间气体浓度检测；批准人 周建国\n\n' +
        '另有 1 台在借未到期：高效液相色谱仪（EQ-0001），持有人 李某（U2023002），应还 2026-10-20。\n\n' +
        '依据：[数据] check_equipment_loan 演示结果。\n\n' +
        '数据覆盖：台账记录截至 2026-10-15，模拟数据。',
      sources: [],
      refused: false,
    }
  }

  if (/过期|资质/.test(q)) {
    return {
      text:
        '**结论**：当前有 1 人安全考试合格证已过期（以下为脱敏演示）。\n\n' +
        '- 王某（T2023001）：安全考试合格证有效期至 2026-10-05，**已过期 10 天**\n' +
        '  · 台账状态仍登记为「有效」——判定一律以有效期为准，不看状态字段\n' +
        '  · 该人 LAB-3 授权仍在有效期内，但资质闸未通过，判定为「资质过期」\n\n' +
        '依据：[数据] 资质台账（演示）；[规程] 《实验室安全规程》第二十一条：资质过期的，不得进入危化品实验室，已进入的应立即停止作业并由实验室负责人登记处置。\n\n' +
        '数据覆盖：截至 2026-10-15，不回放逐条进出明细。',
      sources: [src('certExpired', 0.84, 0.95)],
      refused: false,
    }
  }

  if (/能不能进|能否进|准入|进入/.test(q)) {
    return {
      text:
        '**结论**：资质闸未通过（演示），判定为「资质过期」，不再继续授权闸与双人闸。\n\n' +
        '- 资质闸：未通过（安全考试合格证 AQ-2023-0001，有效期至 2026-10-05，状态「有效」但已过期）\n' +
        '- 授权闸：未评估（资质未通过即停止）\n' +
        '- 双人闸：未评估\n\n' +
        '依据：[数据] 三闸判定（演示）；[规程] 《实验室安全规程》第二十一条。\n\n' +
        '数据覆盖：判定日期 2026-10-15，模拟数据。\n\n' +
        '提示：可在「许可管理」页用三闸判定器逐人逐实验室核查，结论与后端口径一致。',
      sources: [src('certExpired', 0.8, 0.92)],
      refused: false,
    }
  }

  if (/存放|储存|柜/.test(q)) {
    return {
      text:
        '**结论**：丙酮储存于阴凉、通风的专用防火柜中，远离氧化剂与火源，容器密封保存。\n\n' +
        '依据：[规程] 丙酮 SDS「储存」小节（演示）。\n\n数据覆盖：SDS 摘要，模拟数据。',
      sources: [src('acetoneStorage', 0.78, 0.88)],
      refused: false,
    }
  }

  return {
    text: '规程中未找到相关规定。\n\n（模拟模式仅覆盖演示问题；真实系统在未命中时同样不会编造条款。）',
    sources: [],
    refused: false,
  }
}

// 模拟流式输出：按字符分批推送，支持 AbortSignal 中断（对应“停止生成”）
export function streamAnswer(
  question: string,
  onDelta: (delta: string) => void,
  signal: AbortSignal,
): Promise<SimAnswer & { aborted: boolean }> {
  const answer = answerFor(question)
  const chars = Array.from(answer.text)
  return new Promise((resolve) => {
    let i = 0
    const tick = () => {
      if (signal.aborted) {
        resolve({ ...answer, text: chars.slice(0, i).join(''), aborted: true })
        return
      }
      if (i >= chars.length) {
        resolve({ ...answer, aborted: false })
        return
      }
      const step = Math.min(3 + Math.floor(Math.random() * 4), chars.length - i)
      onDelta(chars.slice(i, i + step).join(''))
      i += step
      window.setTimeout(tick, 22)
    }
    window.setTimeout(tick, 650)
  })
}
