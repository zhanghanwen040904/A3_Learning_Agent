from db import mysql_db


def ensure_extended_tables() -> None:
    statements = [
        """
        CREATE TABLE IF NOT EXISTS learning_event (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            user_id BIGINT UNSIGNED NOT NULL,
            event_type VARCHAR(64) NOT NULL,
            knowledge_point VARCHAR(255),
            detail JSON,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            KEY idx_learning_event_user_id (user_id),
            KEY idx_learning_event_type (event_type)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS quiz_result (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            user_id BIGINT UNSIGNED NOT NULL,
            question TEXT NOT NULL,
            answer TEXT,
            reference_answer TEXT,
            score INT NOT NULL DEFAULT 0,
            feedback TEXT,
            knowledge_point VARCHAR(255),
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            KEY idx_quiz_result_user_id (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS mastery_record (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            user_id BIGINT UNSIGNED NOT NULL,
            knowledge_point VARCHAR(255) NOT NULL,
            mastery_score INT NOT NULL DEFAULT 0,
            weak_reason TEXT,
            update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            UNIQUE KEY uk_mastery_user_point (user_id, knowledge_point)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS resource_feedback (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            user_id BIGINT UNSIGNED NOT NULL,
            resource_id BIGINT UNSIGNED,
            rating INT NOT NULL DEFAULT 0,
            comment TEXT,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            KEY idx_resource_feedback_user_id (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
    ]
    for statement in statements:
        mysql_db.execute(statement)
