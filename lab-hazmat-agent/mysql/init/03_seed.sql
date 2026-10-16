-- 测试种子数据（含六类边界样本，见开发文档 §4.5）
-- 日期一律相对 CURDATE() 生成，保证"上周/上月"类问题随时可演示。
USE lab_hazmat;

-- ============ 人员 ============
-- 1 王某：资质过期但授权仍在（边界样本 1）
-- 2 李某（硕）：授权已撤销（边界样本 2）
-- 3 李某（本）：与 2 重名（边界样本 5）
-- 4 张某（教师）：正常，剧毒品间负责人之一
-- 5 赵某（硕）：正常
INSERT INTO persons (id, name, emp_no, dept, role) VALUES
(1, '王某', 'T2023001', '化学系·有机化学课题组', '博士生'),
(2, '李某', 'S2024001', '化学系·分析化学课题组', '硕士生'),
(3, '李某', 'U2023002', '材料学院·功能材料课题组', '本科生'),
(4, '张某', 'T2021001', '化学系', '教师'),
(5, '赵某', 'S2024002', '化学系·有机化学课题组', '硕士生');

-- ============ 资质 ============
INSERT INTO qualifications (person_id, cert_type, cert_no, issue_date, expire_date, status) VALUES
-- 王某：安全考试合格证已过期 10 天（状态未更新，判定时必须以 expire_date 为准）
(1, '安全考试合格证', 'AQ-2023-0001', DATE_SUB(CURDATE(), INTERVAL 375 DAY), DATE_SUB(CURDATE(), INTERVAL 10 DAY), '有效'),
(1, '危化品操作证',   'WH-2023-0110', DATE_SUB(CURDATE(), INTERVAL 300 DAY), DATE_ADD(CURDATE(), INTERVAL 65 DAY), '有效'),
-- 李某（硕）：资质正常
(2, '安全考试合格证', 'AQ-2024-0201', DATE_SUB(CURDATE(), INTERVAL 200 DAY), DATE_ADD(CURDATE(), INTERVAL 165 DAY), '有效'),
-- 李某（本）：资质正常
(3, '安全考试合格证', 'AQ-2023-0330', DATE_SUB(CURDATE(), INTERVAL 320 DAY), DATE_ADD(CURDATE(), INTERVAL 45 DAY), '有效'),
-- 张某（教师）：资质齐全
(4, '安全考试合格证', 'AQ-2021-0007', DATE_SUB(CURDATE(), INTERVAL 100 DAY), DATE_ADD(CURDATE(), INTERVAL 265 DAY), '有效'),
(4, '危化品操作证',   'WH-2021-0007', DATE_SUB(CURDATE(), INTERVAL 100 DAY), DATE_ADD(CURDATE(), INTERVAL 265 DAY), '有效'),
(4, '特种作业证',     'TZ-2022-0015', DATE_SUB(CURDATE(), INTERVAL 400 DAY), DATE_ADD(CURDATE(), INTERVAL 700 DAY), '有效'),
-- 赵某：资质正常
(5, '安全考试合格证', 'AQ-2024-0218', DATE_SUB(CURDATE(), INTERVAL 180 DAY), DATE_ADD(CURDATE(), INTERVAL 185 DAY), '有效');

-- ============ 授权 ============
INSERT INTO lab_authorizations (person_id, lab_id, auth_from, auth_to, grantor, status) VALUES
-- 王某：LAB-3 授权仍在有效期（与过期资质叠加，构成"授权过、资质不过"的拦截场景）
(1, 'LAB-3', DATE_SUB(CURDATE(), INTERVAL 300 DAY), DATE_ADD(CURDATE(), INTERVAL 65 DAY), '陈某导师', '有效'),
-- 李某（硕）：LAB-3 授权已撤销（边界样本 2）
(2, 'LAB-3', DATE_SUB(CURDATE(), INTERVAL 200 DAY), DATE_ADD(CURDATE(), INTERVAL 165 DAY), '陈某导师', '已撤销'),
-- 李某（本）：LAB-1 授权有效
(3, 'LAB-1', DATE_SUB(CURDATE(), INTERVAL 100 DAY), DATE_ADD(CURDATE(), INTERVAL 265 DAY), '刘某导师', '有效'),
-- 张某：LAB-3 / LAB-5 均有效
(4, 'LAB-3', DATE_SUB(CURDATE(), INTERVAL 400 DAY), DATE_ADD(CURDATE(), INTERVAL 330 DAY), '周建国', '有效'),
(4, 'LAB-5', DATE_SUB(CURDATE(), INTERVAL 400 DAY), DATE_ADD(CURDATE(), INTERVAL 330 DAY), '周建国', '有效'),
-- 赵某：LAB-1 授权有效
(5, 'LAB-1', DATE_SUB(CURDATE(), INTERVAL 150 DAY), DATE_ADD(CURDATE(), INTERVAL 215 DAY), '陈某导师', '有效');

-- ============ 台账 ============
-- 丙酮（易燃液体）：3号柜结存 8 瓶，但领用记录 12 瓶（边界样本 3：台账与领用差异）
-- 硝酸（腐蚀品）
-- 高锰酸钾（氧化剂，一般使用量）
-- 氰化钾（剧毒品，双人领用）
-- 金属钠（易制爆，双人领用）
-- 过氧化氢（别名样本：台账写"过氧化氢"，问题可能问"双氧水"）
INSERT INTO hazmat_inventory (item_id, chem_name, cas_no, hazard_class, lab_id, cabinet_no, quantity, unit, updated_at) VALUES
(1, '丙酮',     '67-64-1',  '易燃液体', 'LAB-3', '3号柜', 8.00,   '瓶', NOW()),
(2, '硝酸',     '7697-37-2','腐蚀品',   'LAB-3', '2号柜', 5.50,   '瓶', NOW()),
(3, '高锰酸钾', '7722-64-7','氧化剂',   'LAB-4', '3号柜', 2.00,   '克', NOW()),
(4, '氰化钾',   '151-50-8', '剧毒品',   'LAB-5', 'A柜',   0.80,   '克', NOW()),
(5, '金属钠',   '7440-23-5','易制爆',   'LAB-5', 'B柜',   1.00,   '瓶', NOW()),
(6, '过氧化氢', '7722-84-1','氧化剂',   'LAB-4', '4号柜', 4.00,   '瓶', NOW());

-- ============ 门禁事件 ============
INSERT INTO access_events (person_id, lab_id, event_time, direction, auth_type, auth_result, companion_no) VALUES
(1, 'LAB-3', DATE_SUB(NOW(), INTERVAL 3 DAY), '进', '工卡', '通过', 0),
(4, 'LAB-3', DATE_SUB(NOW(), INTERVAL 2 DAY), '进', '人脸', '通过', 0),
-- 张某单人进入剧毒品间（companion_no=0，违反双人准入，边界样本 4）
(4, 'LAB-5', DATE_SUB(NOW(), INTERVAL 1 DAY), '进', '人脸', '通过', 0);

-- ============ 领用记录 ============
INSERT INTO hazmat_uses (item_id, person_id, use_time, quantity, witness_id, purpose) VALUES
-- 丙酮：上月累计领用 12 瓶（与台账结存 8 瓶形成账物差异，边界样本 3）
(1, 5, DATE_SUB(NOW(), INTERVAL 20 DAY), 6.00, NULL, '合成实验用'),
(1, 5, DATE_SUB(NOW(), INTERVAL 15 DAY), 4.00, NULL, '清洗器皿用'),
(1, 5, DATE_SUB(NOW(), INTERVAL 10 DAY), 2.00, NULL, '萃取实验用'),
-- 氰化钾领用：见证人非空（符合剧毒品双人规则）
(4, 4, DATE_SUB(NOW(), INTERVAL 1 DAY), 0.10, 5,    '标准溶液配制'),
-- 金属钠领用：见证人非空
(5, 4, DATE_SUB(NOW(), INTERVAL 1 DAY), 1.00, 5,    '干燥试剂制备');
