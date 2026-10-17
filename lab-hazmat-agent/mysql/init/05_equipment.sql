-- 实验室安全与资产治理平台 · 设备域库表结构
-- 库名 lab_hazmat。字段英文、中文含义写 COMMENT（COMMENT 会注入 NL2SQL 提示词）。
--
-- 说明：本系统是只读问答系统，借还记录由线下流程产生，库表只做查询。
-- 不建真实外键约束，与 01_schema.sql 保持一致（外键关系写在 COMMENT 里）。
USE lab_hazmat;

CREATE TABLE equipment (
    equip_id      VARCHAR(32)  PRIMARY KEY COMMENT '设备编号，如EQ-0001',
    equip_name    VARCHAR(64)  NOT NULL    COMMENT '设备名称，如高效液相色谱仪',
    category      VARCHAR(32)  NOT NULL    COMMENT '设备类别：分析仪器/合成设备/检测仪器/储存设施/其他',
    model_no      VARCHAR(64)  NULL        COMMENT '规格型号',
    lab_id        VARCHAR(32)  NOT NULL    COMMENT '所在实验室编号，对应 labs.lab_id',
    keeper_id     INT          NULL        COMMENT '保管人id，对应 persons.id',
    status        VARCHAR(16)  NOT NULL DEFAULT '在用' COMMENT '设备状态：在用/维修中/停用/报废',
    calibrate_due DATE         NULL        COMMENT '校准或检定有效期至，判定是否需停用的关键字段，储存设施可为空',
    purchase_date DATE         NULL        COMMENT '购置日期',
    remark        VARCHAR(200) NULL        COMMENT '备注',
    KEY idx_lab (lab_id),
    KEY idx_status (status),
    KEY idx_category (category),
    KEY idx_calibrate (calibrate_due)
) ENGINE=InnoDB COMMENT='实验室设备台账表';

CREATE TABLE equipment_loans (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '借还记录唯一标识',
    equip_id    VARCHAR(32) NOT NULL COMMENT '设备编号，对应 equipment.equip_id',
    person_id   INT         NOT NULL COMMENT '借用人id，对应 persons.id',
    borrow_time DATETIME    NOT NULL COMMENT '借出时间',
    due_time    DATETIME    NOT NULL COMMENT '应归还时间，用于逾期判定',
    return_time DATETIME    NULL     COMMENT '实际归还时间，为空表示尚未归还',
    purpose     VARCHAR(200) NULL    COMMENT '借用用途',
    approver    VARCHAR(32) NULL     COMMENT '批准人姓名（导师或实验室负责人）',
    status      VARCHAR(16) NOT NULL DEFAULT '借用中' COMMENT '借还状态：借用中/已归还/逾期',
    KEY idx_equip_time (equip_id, borrow_time),
    KEY idx_person (person_id),
    KEY idx_status (status)
) ENGINE=InnoDB COMMENT='设备借还记录表';
