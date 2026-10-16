-- 设备域种子数据（含四类边界样本）
-- 日期一律相对 CURDATE() 生成，保证"校准是否过期/是否逾期"类问题随时可演示。
-- 依赖 03_seed.sql（人员 1–5）与 04_labs.sql（LAB-1 ~ LAB-5），须在其后执行。
USE lab_hazmat;

-- ============ 设备台账 ============
-- 边界样本 A：EQ-0002 校准已过期 20 天，但状态仍为"在用"（校准到期但状态未更新，
--             与王某资质"状态有效但已过期"同类，判定时必须以 calibrate_due 为准）
-- 边界样本 B：EQ-0007 校准将于 15 天后到期（30 天预警窗口内的样本）
-- 边界样本 C：EQ-0005 维修中，不可借出
-- 储存设施（防爆试剂柜、通风橱）无校准要求，calibrate_due 为空
INSERT INTO equipment (equip_id, equip_name, category, model_no, lab_id, keeper_id, status, calibrate_due, purchase_date, remark) VALUES
('EQ-0001', '高效液相色谱仪',       '分析仪器', 'Agilent 1260',     'LAB-2', 4, '在用',   DATE_ADD(CURDATE(), INTERVAL 90 DAY),  DATE_SUB(CURDATE(), INTERVAL 900 DAY), NULL),
-- 校准已过期，状态未更新（边界样本 A）
('EQ-0002', '气相色谱质谱联用仪',   '分析仪器', 'Shimadzu GCMS-QP', 'LAB-2', 4, '在用',   DATE_SUB(CURDATE(), INTERVAL 20 DAY),  DATE_SUB(CURDATE(), INTERVAL 1200 DAY), '校准已到期，需送检'),
('EQ-0003', '旋转蒸发仪',           '合成设备', 'RE-52AA',          'LAB-1', 1, '在用',   DATE_ADD(CURDATE(), INTERVAL 200 DAY), DATE_SUB(CURDATE(), INTERVAL 600 DAY), NULL),
('EQ-0004', '防爆试剂柜',           '储存设施', 'FBG-1200',         'LAB-3', 5, '在用',   NULL,                                  DATE_SUB(CURDATE(), INTERVAL 1500 DAY), '储存设施，无校准要求'),
('EQ-0005', '电子分析天平',         '检测仪器', 'ME204',            'LAB-4', 4, '维修中', DATE_ADD(CURDATE(), INTERVAL 30 DAY),  DATE_SUB(CURDATE(), INTERVAL 1100 DAY), '传感器故障，维修中不可借出'),
('EQ-0006', '通风橱',               '储存设施', 'TF-1500',          'LAB-5', 4, '在用',   NULL,                                  DATE_SUB(CURDATE(), INTERVAL 1800 DAY), '储存设施，无校准要求'),
-- 校准 15 天后到期（边界样本 B）
('EQ-0007', '便携式气体检测仪',     '检测仪器', 'BW-MAX XT',        'LAB-5', 4, '在用',   DATE_ADD(CURDATE(), INTERVAL 15 DAY),  DATE_SUB(CURDATE(), INTERVAL 700 DAY), NULL),
('EQ-0008', '恒温培养箱',           '合成设备', 'BPH-9042',         'LAB-4', 5, '报废',   DATE_SUB(CURDATE(), INTERVAL 400 DAY), DATE_SUB(CURDATE(), INTERVAL 2600 DAY), '已报废，待资产处置');

-- ============ 设备借还记录 ============
-- 边界样本 D：EQ-0007 借出后逾期未还（return_time 为空且已过 due_time）
INSERT INTO equipment_loans (equip_id, person_id, borrow_time, due_time, return_time, purpose, approver, status) VALUES
-- 借出未归还且已逾期（边界样本 D）
('EQ-0007', 5, DATE_SUB(NOW(), INTERVAL 10 DAY), DATE_SUB(NOW(), INTERVAL 3 DAY),  NULL,                          '剧毒品间气体浓度检测', '周建国', '逾期'),
-- 借出未归还，尚未到期
('EQ-0001', 3, DATE_SUB(NOW(), INTERVAL 2 DAY),  DATE_ADD(NOW(), INTERVAL 5 DAY),  NULL,                          '样品纯度分析',         '林晓梅', '借用中'),
-- 已按期归还
('EQ-0003', 1, DATE_SUB(NOW(), INTERVAL 20 DAY), DATE_SUB(NOW(), INTERVAL 10 DAY), DATE_SUB(NOW(), INTERVAL 12 DAY), '减压蒸馏',          '陈志远', '已归还'),
-- 已按期归还
('EQ-0004', 5, DATE_SUB(NOW(), INTERVAL 30 DAY), DATE_SUB(NOW(), INTERVAL 20 DAY), DATE_SUB(NOW(), INTERVAL 21 DAY), '试剂分装',          '陈志远', '已归还');
