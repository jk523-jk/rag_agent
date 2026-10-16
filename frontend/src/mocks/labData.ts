// 实验室领域演示数据：全部为虚构，仅用于前端演示。页面上必须标注 DEMO / 模拟。
//
// 数据口径严格对齐后端 lab_hazmat 库（mysql/init/03_seed.sql、04_labs.sql、06_equipment_seed.sql），
// 包含六类边界样本，页面必须能如实呈现这些「异常」而不是掩盖：
//   1. 王某：安全考试合格证已过期 10 天，但 status 仍为「有效」→ 状态与有效期是两个独立信号
//   2. 李某（硕）：LAB-3 授权已撤销
//   3. 李某 ×2 重名（S2024001 / U2023002）→ UI 必须用工号区分
//   4. 张某：单人进 LAB-5（companion_no=0）→ 违反双人准入
//   5. 丙酮：台账结存 8 瓶 vs 领用 12 瓶 → 账物不符
//   6. EQ-0002 校准已过期 20 天但状态仍为「在用」；EQ-0007 借出后逾期未还
import type {
  AccessEvent, Equipment, EquipmentLoan, HazardItem, HazmatUse,
  Lab, LabAuthorization, Person, Qualification,
} from '@/types'

/** 演示时钟锚点。所有相对时间均以此为基准，避免真实日期与演示数据错位。 */
export const DEMO_TODAY = '2026-10-15'

export const labs: Lab[] = [
  { labId: 'LAB-1', labName: '有机合成实验室', hazmatClass: '易燃液体', needsDouble: false, mgrName: '陈志远' },
  { labId: 'LAB-2', labName: '分析测试实验室', hazmatClass: '一般化学品', needsDouble: false, mgrName: '林晓梅' },
  { labId: 'LAB-3', labName: '3号危化品暂存间', hazmatClass: '易燃液体/腐蚀品', needsDouble: false, mgrName: '陈志远' },
  { labId: 'LAB-4', labName: '无机材料实验室', hazmatClass: '氧化剂/一般化学品', needsDouble: false, mgrName: '林晓梅' },
  { labId: 'LAB-5', labName: '剧毒品间', hazmatClass: '剧毒品/易制爆', needsDouble: true, mgrName: '周建国' },
]

export const persons: Person[] = [
  { id: '1', name: '王某', empNo: 'T2023001', dept: '化学系·有机化学课题组', role: '博士生' },
  { id: '2', name: '李某', empNo: 'S2024001', dept: '化学系·分析化学课题组', role: '硕士生' },
  { id: '3', name: '李某', empNo: 'U2023002', dept: '材料学院·功能材料课题组', role: '本科生' },
  { id: '4', name: '张某', empNo: 'T2021001', dept: '化学系', role: '教师' },
  { id: '5', name: '赵某', empNo: 'S2024002', dept: '化学系·有机化学课题组', role: '硕士生' },
]

export const qualifications: Qualification[] = [
  // 边界样本 1：expireDate 已过期 10 天，status 仍是「有效」
  { id: 'q-1', personId: '1', certType: '安全考试合格证', certNo: 'AQ-2023-0001', issueDate: '2025-10-05', expireDate: '2026-10-05', status: '有效' },
  { id: 'q-2', personId: '1', certType: '危化品操作证', certNo: 'WH-2023-0110', issueDate: '2025-12-19', expireDate: '2026-12-19', status: '有效' },
  { id: 'q-3', personId: '2', certType: '安全考试合格证', certNo: 'AQ-2024-0201', issueDate: '2026-03-29', expireDate: '2027-03-29', status: '有效' },
  { id: 'q-4', personId: '3', certType: '安全考试合格证', certNo: 'AQ-2023-0330', issueDate: '2025-11-29', expireDate: '2026-11-29', status: '有效' },
  { id: 'q-5', personId: '4', certType: '安全考试合格证', certNo: 'AQ-2021-0007', issueDate: '2026-07-07', expireDate: '2027-07-07', status: '有效' },
  { id: 'q-6', personId: '4', certType: '危化品操作证', certNo: 'WH-2021-0007', issueDate: '2026-07-07', expireDate: '2027-07-07', status: '有效' },
  { id: 'q-7', personId: '4', certType: '特种作业证', certNo: 'TZ-2022-0015', issueDate: '2025-09-10', expireDate: '2028-09-14', status: '有效' },
  { id: 'q-8', personId: '5', certType: '安全考试合格证', certNo: 'AQ-2024-0218', issueDate: '2026-04-18', expireDate: '2027-04-18', status: '有效' },
]

export const authorizations: LabAuthorization[] = [
  { id: 'a-1', personId: '1', labId: 'LAB-3', authFrom: '2025-12-19', authTo: '2026-12-19', grantor: '陈某导师', status: '有效' },
  // 边界样本 2：授权已撤销
  { id: 'a-2', personId: '2', labId: 'LAB-3', authFrom: '2026-03-29', authTo: '2027-03-29', grantor: '陈某导师', status: '已撤销' },
  { id: 'a-3', personId: '3', labId: 'LAB-1', authFrom: '2026-07-07', authTo: '2027-07-07', grantor: '刘某导师', status: '有效' },
  { id: 'a-4', personId: '4', labId: 'LAB-3', authFrom: '2025-09-10', authTo: '2027-09-10', grantor: '周建国', status: '有效' },
  { id: 'a-5', personId: '4', labId: 'LAB-5', authFrom: '2025-09-10', authTo: '2027-09-10', grantor: '周建国', status: '有效' },
  { id: 'a-6', personId: '5', labId: 'LAB-1', authFrom: '2026-05-18', authTo: '2027-05-18', grantor: '陈某导师', status: '有效' },
]

export const accessEvents: AccessEvent[] = [
  { id: 'e-1', personId: '1', labId: 'LAB-3', eventTime: '2026-10-12 09:14', direction: '进', authType: '工卡', authResult: '通过', companionNo: 0 },
  { id: 'e-2', personId: '4', labId: 'LAB-3', eventTime: '2026-10-13 14:02', direction: '进', authType: '人脸', authResult: '通过', companionNo: 0 },
  { id: 'e-3', personId: '4', labId: 'LAB-3', eventTime: '2026-10-13 16:31', direction: '出', authType: '人脸', authResult: '通过', companionNo: 0 },
  // 边界样本 4：张某单人进入剧毒品间，companionNo=0 违反双人准入
  { id: 'e-4', personId: '4', labId: 'LAB-5', eventTime: '2026-10-14 10:20', direction: '进', authType: '人脸', authResult: '通过', companionNo: 0 },
  { id: 'e-5', personId: '4', labId: 'LAB-5', eventTime: '2026-10-14 10:52', direction: '出', authType: '人脸', authResult: '通过', companionNo: 0 },
  // 授权已撤销者的尝试记录
  { id: 'e-6', personId: '2', labId: 'LAB-3', eventTime: '2026-10-14 15:08', direction: '进', authType: '工卡', authResult: '拒绝', companionNo: null },
  { id: 'e-7', personId: '5', labId: 'LAB-1', eventTime: '2026-10-14 08:45', direction: '进', authType: '密码', authResult: '通过', companionNo: 0 },
  { id: 'e-8', personId: '5', labId: 'LAB-1', eventTime: '2026-10-14 17:20', direction: '出', authType: '密码', authResult: '通过', companionNo: 0 },
  { id: 'e-9', personId: '3', labId: 'LAB-1', eventTime: '2026-10-15 09:05', direction: '进', authType: '人工放行', authResult: '通过', companionNo: 1 },
  { id: 'e-10', personId: '1', labId: 'LAB-3', eventTime: '2026-10-15 09:30', direction: '进', authType: '工卡', authResult: '超时', companionNo: null },
]

export const inventory: HazardItem[] = [
  // 边界样本 5：结存 8 瓶，但领用合计 12 瓶 → 账物不符
  { id: 'i-1', chemName: '丙酮', casNo: '67-64-1', hazardClass: '易燃液体', labId: 'LAB-3', cabinetNo: '3号柜', quantity: 8, unit: '瓶', updatedAt: '2026-10-14 18:00' },
  { id: 'i-2', chemName: '硝酸', casNo: '7697-37-2', hazardClass: '腐蚀品', labId: 'LAB-3', cabinetNo: '2号柜', quantity: 5.5, unit: '瓶', updatedAt: '2026-10-14 18:00' },
  { id: 'i-3', chemName: '高锰酸钾', casNo: '7722-64-7', hazardClass: '氧化剂', labId: 'LAB-4', cabinetNo: '3号柜', quantity: 2, unit: '克', updatedAt: '2026-10-14 18:00' },
  { id: 'i-4', chemName: '氰化钾', casNo: '151-50-8', hazardClass: '剧毒品', labId: 'LAB-5', cabinetNo: 'A柜', quantity: 0.8, unit: '克', updatedAt: '2026-10-14 18:00' },
  { id: 'i-5', chemName: '金属钠', casNo: '7440-23-5', hazardClass: '易制爆', labId: 'LAB-5', cabinetNo: 'B柜', quantity: 1, unit: '瓶', updatedAt: '2026-10-14 18:00' },
  { id: 'i-6', chemName: '过氧化氢', casNo: '7722-84-1', hazardClass: '氧化剂', labId: 'LAB-4', cabinetNo: '4号柜', quantity: 4, unit: '瓶', updatedAt: '2026-10-14 18:00' },
]

export const hazmatUses: HazmatUse[] = [
  { id: 'u-1', itemId: 'i-1', personId: '5', useTime: '2026-09-25', quantity: 6, witnessId: null, purpose: '合成实验用' },
  { id: 'u-2', itemId: 'i-1', personId: '5', useTime: '2026-09-30', quantity: 4, witnessId: null, purpose: '清洗器皿用' },
  { id: 'u-3', itemId: 'i-1', personId: '5', useTime: '2026-10-05', quantity: 2, witnessId: null, purpose: '萃取实验用' },
  { id: 'u-4', itemId: 'i-4', personId: '4', useTime: '2026-10-14', quantity: 0.1, witnessId: '5', purpose: '标准溶液配制' },
  { id: 'u-5', itemId: 'i-5', personId: '4', useTime: '2026-10-14', quantity: 1, witnessId: '5', purpose: '干燥试剂制备' },
]

export const equipment: Equipment[] = [
  { id: 'eq-1', equipId: 'EQ-0001', equipName: '高效液相色谱仪', category: '分析仪器', modelNo: 'Agilent 1260', labId: 'LAB-2', keeperId: '4', status: '在用', calibrateDue: '2027-01-13', purchaseDate: '2024-04-28', remark: '' },
  // 边界样本 6：校准已过期 20 天，状态仍为「在用」
  { id: 'eq-2', equipId: 'EQ-0002', equipName: '气相色谱质谱联用仪', category: '分析仪器', modelNo: 'Shimadzu GCMS-QP', labId: 'LAB-2', keeperId: '4', status: '在用', calibrateDue: '2026-09-25', purchaseDate: '2023-07-03', remark: '校准已到期，需送检' },
  { id: 'eq-3', equipId: 'EQ-0003', equipName: '旋转蒸发仪', category: '合成设备', modelNo: 'RE-52AA', labId: 'LAB-1', keeperId: '1', status: '在用', calibrateDue: '2027-05-03', purchaseDate: '2025-02-22', remark: '' },
  { id: 'eq-4', equipId: 'EQ-0004', equipName: '防爆试剂柜', category: '储存设施', modelNo: 'FBG-1200', labId: 'LAB-3', keeperId: '5', status: '在用', calibrateDue: null, purchaseDate: '2022-09-06', remark: '储存设施，无校准要求' },
  { id: 'eq-5', equipId: 'EQ-0005', equipName: '电子分析天平', category: '检测仪器', modelNo: 'ME204', labId: 'LAB-4', keeperId: '4', status: '维修中', calibrateDue: '2026-11-14', purchaseDate: '2023-10-11', remark: '传感器故障，维修中不可借出' },
  { id: 'eq-6', equipId: 'EQ-0006', equipName: '通风橱', category: '储存设施', modelNo: 'TF-1500', labId: 'LAB-5', keeperId: '4', status: '在用', calibrateDue: null, purchaseDate: '2021-11-10', remark: '储存设施，无校准要求' },
  // 校准 15 天后到期（30 天预警窗口内）
  { id: 'eq-7', equipId: 'EQ-0007', equipName: '便携式气体检测仪', category: '检测仪器', modelNo: 'BW-MAX XT', labId: 'LAB-5', keeperId: '4', status: '在用', calibrateDue: '2026-10-30', purchaseDate: '2024-11-14', remark: '' },
  { id: 'eq-8', equipId: 'EQ-0008', equipName: '恒温培养箱', category: '合成设备', modelNo: 'BPH-9042', labId: 'LAB-4', keeperId: '5', status: '报废', calibrateDue: '2025-09-10', purchaseDate: '2019-09-02', remark: '已报废，待资产处置' },
]

export const equipmentLoans: EquipmentLoan[] = [
  // 借出后逾期未还：returnTime 为空且已过 dueTime
  { id: 'l-1', equipId: 'EQ-0007', personId: '5', borrowTime: '2026-10-05 09:00', dueTime: '2026-10-12 18:00', returnTime: null, purpose: '剧毒品间气体浓度检测', approver: '周建国', status: '逾期' },
  { id: 'l-2', equipId: 'EQ-0001', personId: '3', borrowTime: '2026-10-13 10:30', dueTime: '2026-10-20 18:00', returnTime: null, purpose: '样品纯度分析', approver: '林晓梅', status: '借用中' },
  { id: 'l-3', equipId: 'EQ-0003', personId: '1', borrowTime: '2026-09-25 08:40', dueTime: '2026-10-05 18:00', returnTime: '2026-10-03 16:20', purpose: '减压蒸馏', approver: '陈志远', status: '已归还' },
  { id: 'l-4', equipId: 'EQ-0004', personId: '5', borrowTime: '2026-09-15 13:10', dueTime: '2026-09-25 18:00', returnTime: '2026-09-24 11:05', purpose: '试剂分装', approver: '陈志远', status: '已归还' },
]
