-- 只读账号（四层护栏第 1 层：数据库层兜底）
USE lab_hazmat;

CREATE USER IF NOT EXISTS 'lab_readonly'@'%' IDENTIFIED BY 'change_me';
GRANT SELECT ON lab_hazmat.* TO 'lab_readonly'@'%';
REVOKE ALL PRIVILEGES ON lab_hazmat.* FROM 'lab_readonly'@'%';
GRANT SELECT ON lab_hazmat.* TO 'lab_readonly'@'%';
FLUSH PRIVILEGES;
