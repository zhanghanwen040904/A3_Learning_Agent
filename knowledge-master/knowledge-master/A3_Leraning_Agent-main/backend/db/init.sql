CREATE DATABASE IF NOT EXISTS a3_learning_agent
    DEFAULT CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE a3_learning_agent;

CREATE TABLE IF NOT EXISTS `user` (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '用户ID',
    username VARCHAR(64) NOT NULL COMMENT '登录用户名',
    password VARCHAR(255) NOT NULL COMMENT '登录密码哈希',
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_user_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户登录表';

CREATE TABLE IF NOT EXISTS student_profile (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '画像ID',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    knowledge_level TEXT COMMENT '知识基础水平',
    study_style TEXT COMMENT '学习风格偏好',
    weak_points TEXT COMMENT '薄弱知识点',
    study_goal TEXT COMMENT '学习目标',
    study_time_prefer TEXT COMMENT '学习时间偏好',
    course_progress TEXT COMMENT '课程学习进度',
    update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_student_profile_user_id (user_id),
    CONSTRAINT fk_student_profile_user_id
        FOREIGN KEY (user_id) REFERENCES `user` (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='六维动态学生画像表';

CREATE TABLE IF NOT EXISTS study_resource (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '资源ID',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    resource_type VARCHAR(64) NOT NULL COMMENT '资源类型，如 doc、quiz、reading、mindmap、code、video',
    title VARCHAR(255) NOT NULL COMMENT '资源标题',
    content MEDIUMTEXT COMMENT '资源内容或资源地址',
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (id),
    KEY idx_study_resource_user_id (user_id),
    KEY idx_study_resource_type (resource_type),
    CONSTRAINT fk_study_resource_user_id
        FOREIGN KEY (user_id) REFERENCES `user` (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='多模态学习资源表';

CREATE TABLE IF NOT EXISTS study_path (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '学习路径ID',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    path_content MEDIUMTEXT NOT NULL COMMENT '学习路径内容，建议存储Markdown或JSON字符串',
    status VARCHAR(32) NOT NULL DEFAULT 'active' COMMENT '状态：active、completed、archived',
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (id),
    KEY idx_study_path_user_id (user_id),
    KEY idx_study_path_status (status),
    CONSTRAINT fk_study_path_user_id
        FOREIGN KEY (user_id) REFERENCES `user` (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='个性化学习路径表';

CREATE TABLE IF NOT EXISTS learning_event (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '学习行为ID',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    event_type VARCHAR(64) NOT NULL COMMENT '行为类型：view_resource、ask_question、finish_quiz等',
    knowledge_point VARCHAR(255) COMMENT '关联知识点',
    detail JSON COMMENT '行为详情',
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (id),
    KEY idx_learning_event_user_id (user_id),
    KEY idx_learning_event_type (event_type),
    CONSTRAINT fk_learning_event_user_id
        FOREIGN KEY (user_id) REFERENCES `user` (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='学习行为记录表';

CREATE TABLE IF NOT EXISTS quiz_result (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '练习结果ID',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    question TEXT NOT NULL COMMENT '题目',
    answer TEXT COMMENT '学生答案',
    reference_answer TEXT COMMENT '参考答案',
    score INT NOT NULL DEFAULT 0 COMMENT '得分，0-100',
    feedback TEXT COMMENT '反馈建议',
    knowledge_point VARCHAR(255) COMMENT '知识点',
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (id),
    KEY idx_quiz_result_user_id (user_id),
    CONSTRAINT fk_quiz_result_user_id
        FOREIGN KEY (user_id) REFERENCES `user` (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='练习测试结果表';

CREATE TABLE IF NOT EXISTS mastery_record (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '掌握度ID',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    knowledge_point VARCHAR(255) NOT NULL COMMENT '知识点',
    mastery_score INT NOT NULL DEFAULT 0 COMMENT '掌握度，0-100',
    weak_reason TEXT COMMENT '薄弱原因',
    update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_mastery_user_point (user_id, knowledge_point),
    CONSTRAINT fk_mastery_record_user_id
        FOREIGN KEY (user_id) REFERENCES `user` (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识点掌握度表';

CREATE TABLE IF NOT EXISTS resource_feedback (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '资源反馈ID',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    resource_id BIGINT UNSIGNED COMMENT '资源ID',
    rating INT NOT NULL DEFAULT 0 COMMENT '评分，1-5',
    comment TEXT COMMENT '反馈内容',
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (id),
    KEY idx_resource_feedback_user_id (user_id),
    CONSTRAINT fk_resource_feedback_user_id
        FOREIGN KEY (user_id) REFERENCES `user` (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT fk_resource_feedback_resource_id
        FOREIGN KEY (resource_id) REFERENCES study_resource (id)
        ON DELETE SET NULL
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='资源使用反馈表';
