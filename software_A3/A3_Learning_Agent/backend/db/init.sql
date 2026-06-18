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
    resource_type VARCHAR(64) NOT NULL COMMENT '资源类型，如 text、mindmap、quiz、case、chart、video',
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
    path_content MEDIUMTEXT NOT NULL COMMENT '学习路径内容，建议存储JSON字符串',
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
