-- 实验室安全与资产治理平台 · 库表结构（业务域：环境/人员/物料）
-- 库名 lab_hazmat。字段英文、中文含义写 COMMENT（COMMENT 会注入 NL2SQL 提示词）。
CREATE DATABASE IF NOT EXISTS lab_hazmat
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE lab_hazmat;

CREATE TABLE labs (
    lab_id       VARCHAR(32)  PRIMARY KEY COMMENT '实验室编号，如LAB-3',
    lab_name     VARCHAR(64)  NOT NULL    COMMENT '实验室名称',
    hazmat_class VARCHAR(64)  NULL        COMMENT '可存放危化品类别：易燃液体/腐蚀品/氧化剂/剧毒品/易制爆/一般化学品',
    needs_double TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '是否要求双人准入，1是0否，剧毒品间必须为1',
    mgr_name     VARCHAR(32)  NULL        COMMENT '实验室安全负责人姓名',
    category_id  VARCHAR(32)  NULL        COMMENT '学科方向分类id，对应 lab_categories.category_id，如CAT-CHEM',
    KEY idx_class (hazmat_class),
    KEY idx_category (category_id)
) ENGINE=InnoDB COMMENT='实验室信息表';

CREATE TABLE persons (
    id     INT AUTO_INCREMENT PRIMARY KEY COMMENT '人员唯一标识',
    name   VARCHAR(32) NOT NULL COMMENT '姓名，可能重名',
    emp_no VARCHAR(20) NOT NULL COMMENT '工号或学号',
    dept   VARCHAR(64) NULL     COMMENT '所属院系或课题组',
    role   VARCHAR(32) NULL     COMMENT '身份：教师/博士生/硕士生/本科生/外协',
    UNIQUE KEY uk_emp (emp_no)
) ENGINE=InnoDB COMMENT='实验室人员表';

CREATE TABLE qualifications (
    person_id   INT         NOT NULL COMMENT '人员id，对应 persons.id',
    cert_type   VARCHAR(32) NOT NULL COMMENT '资质类型：安全考试合格证/危化品操作证/特种作业证/导师授权书',
    cert_no     VARCHAR(64) NULL     COMMENT '证书编号',
    issue_date  DATE        NOT NULL COMMENT '发证日期',
    expire_date DATE        NOT NULL COMMENT '失效日期，判定准入资格的关键字段',
    status      VARCHAR(16) NOT NULL DEFAULT '有效' COMMENT '资质状态：有效/已过期/已注销',
    PRIMARY KEY (person_id, cert_type, issue_date),
    KEY idx_expire (expire_date),
    KEY idx_status (status)
) ENGINE=InnoDB COMMENT='人员准入资质表';

CREATE TABLE lab_authorizations (
    person_id INT         NOT NULL COMMENT '人员id，对应 persons.id',
    lab_id    VARCHAR(32) NOT NULL COMMENT '实验室编号，对应 labs.lab_id',
    auth_from DATE        NOT NULL COMMENT '授权生效日期',
    auth_to   DATE        NOT NULL COMMENT '授权失效日期',
    grantor   VARCHAR(32) NULL     COMMENT '授权人（导师或实验室负责人）姓名',
    status    VARCHAR(16) NOT NULL DEFAULT '有效' COMMENT '授权状态：有效/已撤销/已过期',
    PRIMARY KEY (person_id, lab_id),
    KEY idx_lab (lab_id)
) ENGINE=InnoDB COMMENT='实验室准入授权表';

CREATE TABLE access_events (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '事件唯一标识',
    person_id    INT         NOT NULL COMMENT '人员id，对应 persons.id',
    lab_id       VARCHAR(32) NOT NULL COMMENT '实验室编号，对应 labs.lab_id',
    event_time   DATETIME    NOT NULL COMMENT '刷卡时间',
    direction    VARCHAR(8)  NOT NULL COMMENT '通行方向：进/出',
    auth_type    VARCHAR(16) NOT NULL COMMENT '验证方式：人脸/工卡/密码/人工放行',
    auth_result  VARCHAR(16) NOT NULL DEFAULT '通过' COMMENT '验证结果：通过/拒绝/超时',
    companion_no INT         NULL     COMMENT '同行人数，剧毒品间要求双人准入时用于核查',
    KEY idx_person_time (person_id, event_time),
    KEY idx_lab_time (lab_id, event_time)
) ENGINE=InnoDB COMMENT='实验室门禁通行事件表';

CREATE TABLE hazmat_inventory (
    item_id      INT AUTO_INCREMENT PRIMARY KEY COMMENT '台账条目唯一标识',
    chem_name    VARCHAR(64) NOT NULL COMMENT '化学品名称，如丙酮、硝酸',
    cas_no       VARCHAR(32) NULL     COMMENT 'CAS 登记号，匹配主键',
    hazard_class VARCHAR(32) NOT NULL COMMENT '危险类别：易燃液体/腐蚀品/氧化剂/剧毒品/易制爆/一般化学品',
    lab_id       VARCHAR(32) NOT NULL COMMENT '所在实验室编号',
    cabinet_no   VARCHAR(32) NULL     COMMENT '存放柜编号，如3号柜',
    quantity     DECIMAL(10,2) NOT NULL COMMENT '当前结存数量（内部精确值，对外需按类别脱敏）',
    unit         VARCHAR(16) NOT NULL COMMENT '计量单位：瓶/克/毫升',
    updated_at   DATETIME    NOT NULL COMMENT '最近更新时间',
    KEY idx_lab (lab_id),
    KEY idx_chem (chem_name),
    KEY idx_cas (cas_no),
    KEY idx_class (hazard_class)
) ENGINE=InnoDB COMMENT='危化品台账表';

CREATE TABLE hazmat_uses (
    id         BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '领用记录唯一标识',
    item_id    INT           NOT NULL COMMENT '台账条目id，对应 hazmat_inventory.item_id',
    person_id  INT           NOT NULL COMMENT '领用人id，对应 persons.id',
    use_time   DATETIME      NOT NULL COMMENT '领用时间',
    quantity   DECIMAL(10,2) NOT NULL COMMENT '领用数量',
    witness_id INT           NULL     COMMENT '见证人id，剧毒品与易制爆必须非空',
    purpose    VARCHAR(200)  NULL     COMMENT '用途说明',
    KEY idx_item_time (item_id, use_time),
    KEY idx_person (person_id)
) ENGINE=InnoDB COMMENT='危化品领用记录表';

-- ============================================================================
-- 实验室学科方向分类 + 标准配置模板（该方向实验室应配哪些设备/试剂）
-- 说明：labs.category_id 关联 lab_categories；模板表定义"该配什么"，
--       equipment / hazmat_inventory 记录"实际配了什么"，两者可做差异比对。
-- ============================================================================
CREATE TABLE lab_categories (
    category_id   VARCHAR(32)  PRIMARY KEY COMMENT '实验室分类编号，如CAT-CHEM',
    category_name VARCHAR(64)  NOT NULL    COMMENT '分类名称：物理实验室/化学实验室/生物实验室/材料实验室/分析测试实验室',
    direction     VARCHAR(32)  NOT NULL    COMMENT '学科方向：物理/化学/生物/材料/分析测试',
    description   VARCHAR(200) NULL        COMMENT '方向说明与该类实验室典型用途',
    KEY idx_direction (direction)
) ENGINE=InnoDB COMMENT='实验室学科方向分类表';

CREATE TABLE category_equipment (
    id             INT AUTO_INCREMENT PRIMARY KEY COMMENT '标准配置条目唯一标识',
    category_id    VARCHAR(32)  NOT NULL COMMENT '所属实验室分类id，对应 lab_categories.category_id',
    equip_name     VARCHAR(64)  NOT NULL COMMENT '应配设备名称，如通风橱、高效液相色谱仪',
    equip_category VARCHAR(32)  NOT NULL COMMENT '设备类别：分析仪器/合成设备/检测仪器/储存设施/物理设备/生物设备/其他',
    quantity       INT          NOT NULL DEFAULT 1 COMMENT '建议配置数量',
    necessity      VARCHAR(8)   NOT NULL DEFAULT '必备' COMMENT '配置要求：必备/选配',
    remark         VARCHAR(200) NULL     COMMENT '备注，如用途或选型提示',
    KEY idx_category (category_id),
    KEY idx_equip_name (equip_name)
) ENGINE=InnoDB COMMENT='实验室分类标准设备配置表（模板：该类实验室应配哪些设备）';

CREATE TABLE category_reagents (
    id           INT AUTO_INCREMENT PRIMARY KEY COMMENT '标准配置条目唯一标识',
    category_id  VARCHAR(32)   NOT NULL COMMENT '所属实验室分类id，对应 lab_categories.category_id',
    chem_name    VARCHAR(64)   NOT NULL COMMENT '应配试剂名称，如丙酮、硫酸',
    cas_no       VARCHAR(32)   NULL     COMMENT 'CAS 登记号',
    hazard_class VARCHAR(32)   NOT NULL COMMENT '危险类别：易燃液体/腐蚀品/氧化剂/剧毒品/易制爆/一般化学品',
    quantity     DECIMAL(10,2) NOT NULL COMMENT '建议配置数量',
    unit         VARCHAR(16)   NOT NULL COMMENT '计量单位：瓶/克/毫升',
    necessity    VARCHAR(8)    NOT NULL DEFAULT '必备' COMMENT '配置要求：必备/选配',
    remark       VARCHAR(200)  NULL     COMMENT '备注，如用途或储存要求',
    KEY idx_category (category_id),
    KEY idx_chem (chem_name),
    KEY idx_class (hazard_class)
) ENGINE=InnoDB COMMENT='实验室分类标准试剂配置表（模板：该类实验室应配哪些试剂）';
