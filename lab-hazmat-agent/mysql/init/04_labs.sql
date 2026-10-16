-- 实验室清单与双人要求配置
USE lab_hazmat;

INSERT INTO labs (lab_id, lab_name, hazmat_class, needs_double, mgr_name) VALUES
('LAB-1', '有机合成实验室',   '易燃液体',              0, '陈志远'),
('LAB-2', '分析测试实验室',   '一般化学品',              0, '林晓梅'),
('LAB-3', '3号危化品暂存间',  '易燃液体/腐蚀品',         0, '陈志远'),
('LAB-4', '无机材料实验室',   '氧化剂/一般化学品',       0, '林晓梅'),
('LAB-5', '剧毒品间',         '剧毒品/易制爆',           1, '周建国');
