from db import mysql_db


def _columns(table: str) -> set[str]:
    return {row["Field"] for row in mysql_db.query_all(f"SHOW COLUMNS FROM `{table}`")}


def _indexes(table: str) -> set[str]:
    return {row["Key_name"] for row in mysql_db.query_all(f"SHOW INDEX FROM `{table}`")}


def _add_column(table: str, column: str, definition: str) -> None:
    if column not in _columns(table):
        mysql_db.execute(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {definition}")


def _add_index(table: str, index_name: str, columns: str, unique: bool = False) -> None:
    if index_name not in _indexes(table):
        prefix = "UNIQUE KEY" if unique else "KEY"
        mysql_db.execute(f"ALTER TABLE `{table}` ADD {prefix} `{index_name}` ({columns})")


def _drop_index_if_exists(table: str, index_name: str) -> None:
    if index_name in _indexes(table):
        mysql_db.execute(f"ALTER TABLE `{table}` DROP INDEX `{index_name}`")


def ensure_extended_tables() -> None:
    statements = [
        """
        CREATE TABLE IF NOT EXISTS knowledge_documents (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            file_name VARCHAR(255) NOT NULL,
            file_path TEXT NULL,
            course VARCHAR(255) NOT NULL,
            type VARCHAR(32) NOT NULL DEFAULT 'JSON',
            size BIGINT UNSIGNED NOT NULL DEFAULT 0,
            section_count INT NOT NULL DEFAULT 0,
            chunk_count INT NOT NULL DEFAULT 0,
            status VARCHAR(32) NOT NULL DEFAULT 'imported',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            UNIQUE KEY uk_knowledge_documents_course_file (course, file_name),
            KEY idx_knowledge_documents_course (course),
            KEY idx_knowledge_documents_status (status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS knowledge_sections (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            document_id BIGINT UNSIGNED NULL,
            node_id VARCHAR(255) NOT NULL,
            parent_id VARCHAR(255) NULL,
            title VARCHAR(255) NOT NULL,
            level INT NOT NULL DEFAULT 0,
            chapter_id VARCHAR(255) NULL,
            start_page INT NULL,
            path_json JSON NULL,
            path_text TEXT NULL,
            course VARCHAR(255) NOT NULL,
            source_file VARCHAR(255) NOT NULL,
            sort_order INT NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            UNIQUE KEY uk_knowledge_sections_node_source (node_id, source_file),
            KEY idx_knowledge_sections_document_id (document_id),
            KEY idx_knowledge_sections_parent_id (parent_id),
            KEY idx_knowledge_sections_course (course),
            KEY idx_knowledge_sections_sort_order (sort_order)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS knowledge_chunks (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            document_id BIGINT UNSIGNED NULL,
            section_id BIGINT UNSIGNED NULL,
            section_node_id VARCHAR(255) NOT NULL,
            chapter_id VARCHAR(255) NULL,
            section_title VARCHAR(255) NOT NULL,
            path_json JSON NULL,
            path_text TEXT NULL,
            page VARCHAR(32) NULL,
            content MEDIUMTEXT NOT NULL,
            chunk_index INT NOT NULL DEFAULT 0,
            course VARCHAR(255) NOT NULL,
            source_file VARCHAR(255) NOT NULL,
            embedding_id VARCHAR(255) NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            UNIQUE KEY uk_knowledge_chunks_section_page_idx (section_node_id, source_file, page, chunk_index),
            KEY idx_knowledge_chunks_document_id (document_id),
            KEY idx_knowledge_chunks_section_id (section_id),
            KEY idx_knowledge_chunks_section_node_id (section_node_id),
            KEY idx_knowledge_chunks_course (course)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
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
        CREATE TABLE IF NOT EXISTS quiz_wrong_book (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            user_id BIGINT UNSIGNED NOT NULL,
            quiz_result_id BIGINT UNSIGNED NULL,
            question TEXT NOT NULL,
            question_type VARCHAR(64) NULL,
            options_json JSON NULL,
            answer TEXT NULL,
            reference_answer TEXT NULL,
            explanation TEXT NULL,
            common_mistake TEXT NULL,
            scoring_points JSON NULL,
            knowledge_point VARCHAR(255) NULL,
            knowledge_path VARCHAR(255) NULL,
            chapter VARCHAR(255) NULL,
            difficulty VARCHAR(64) NULL,
            score INT NOT NULL DEFAULT 0,
            feedback TEXT NULL,
            last_result JSON NULL,
            review_count INT NOT NULL DEFAULT 0,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            KEY idx_quiz_wrong_book_user_id (user_id),
            KEY idx_quiz_wrong_book_knowledge_point (knowledge_point),
            KEY idx_quiz_wrong_book_chapter (chapter)
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
        """
        CREATE TABLE IF NOT EXISTS profile_session (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            user_id BIGINT UNSIGNED NOT NULL,
            title VARCHAR(120) NOT NULL DEFAULT '新画像',
            is_active TINYINT(1) NOT NULL DEFAULT 0,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            KEY idx_profile_session_user_active (user_id, is_active),
            KEY idx_profile_session_update_time (update_time)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS generation_batch (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            trace_id VARCHAR(80) NOT NULL,
            user_id BIGINT UNSIGNED NOT NULL,
            profile_session_id BIGINT UNSIGNED NULL,
            profile_snapshot JSON,
            plan JSON,
            status VARCHAR(32) NOT NULL DEFAULT 'running',
            error_summary TEXT,
            start_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            finish_time DATETIME NULL,
            PRIMARY KEY (id),
            UNIQUE KEY uk_generation_batch_trace_id (trace_id),
            KEY idx_generation_batch_user_id (user_id),
            KEY idx_generation_batch_session_id (profile_session_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS agent_execution (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            batch_id BIGINT UNSIGNED NOT NULL,
            agent_name VARCHAR(80) NOT NULL,
            status VARCHAR(32) NOT NULL,
            message TEXT,
            score INT,
            retry_count INT NOT NULL DEFAULT 0,
            duration_ms INT NOT NULL DEFAULT 0,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            KEY idx_agent_execution_batch_id (batch_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS resource_source (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            resource_id BIGINT UNSIGNED NOT NULL,
            source_name VARCHAR(255) NOT NULL,
            chunk_index INT,
            relevance_score DOUBLE,
            retrieval_mode VARCHAR(32),
            PRIMARY KEY (id),
            KEY idx_resource_source_resource_id (resource_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS profile_conversation (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            user_id BIGINT UNSIGNED NOT NULL,
            profile_session_id BIGINT UNSIGNED NULL,
            messages JSON NOT NULL,
            answer_map JSON,
            extra_notes JSON,
            current_index INT NOT NULL DEFAULT 0,
            update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            KEY idx_profile_conversation_user_id (user_id),
            KEY idx_profile_conversation_session_id (profile_session_id),
            KEY idx_profile_conversation_update_time (update_time)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS tutor_conversation (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            user_id BIGINT UNSIGNED NOT NULL,
            profile_session_id BIGINT UNSIGNED NULL,
            messages JSON NOT NULL,
            update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            UNIQUE KEY uk_tutor_conversation_user_session (user_id, profile_session_id),
            KEY idx_tutor_conversation_user_id (user_id),
            KEY idx_tutor_conversation_session_id (profile_session_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS portrait_snapshot (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            user_id BIGINT UNSIGNED NOT NULL,
            profile_session_id BIGINT UNSIGNED NULL,
            trigger_source VARCHAR(64) NOT NULL DEFAULT 'profile_update',
            profile_summary TEXT NULL,
            portrait_scoring JSON NULL,
            profile_snapshot JSON NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            KEY idx_portrait_snapshot_user_id (user_id),
            KEY idx_portrait_snapshot_session_id (profile_session_id),
            KEY idx_portrait_snapshot_create_time (create_time)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
    ]
    for statement in statements:
        mysql_db.execute(statement)

    for table in ("student_profile", "study_resource", "study_path", "generation_batch", "profile_conversation", "learning_event", "quiz_result", "mastery_record", "quiz_wrong_book", "resource_feedback"):
        _add_column(table, "profile_session_id", "BIGINT UNSIGNED NULL")
        _add_index(table, f"idx_{table}_session_id", "`profile_session_id`")

    study_resource_extra_columns = {
        "batch_id": "BIGINT UNSIGNED NULL",
        "agent_name": "VARCHAR(80) NULL",
        "knowledge_points": "JSON NULL",
        "personalization": "TEXT NULL",
        "quality_score": "INT NULL",
        "audit_status": "VARCHAR(32) NULL",
        "metadata": "JSON NULL",
    }
    for column, definition in study_resource_extra_columns.items():
        _add_column("study_resource", column, definition)

    user_extra_columns = {
        "major": "VARCHAR(120) NULL",
        "target_course": "VARCHAR(120) NULL",
        "education_level": "VARCHAR(80) NULL",
        "school": "VARCHAR(160) NULL",
        "personal_info": "JSON NULL",
    }
    for column, definition in user_extra_columns.items():
        _add_column("user", column, definition)

    profile_extra_columns = {
        "major": "VARCHAR(120) NULL",
        "target_course": "VARCHAR(120) NULL",
        "current_topic": "TEXT NULL",
        "mastery_level": "TEXT NULL",
        "current_difficulty": "TEXT NULL",
        "task_goal": "TEXT NULL",
        "support_preference": "TEXT NULL",
        "engagement_level": "TEXT NULL",
        "learning_background": "TEXT NULL",
        "recent_progress": "TEXT NULL",
        "schedule_pattern": "TEXT NULL",
        "weak_knowledge_points": "TEXT NULL",
        "recommended_next_step": "TEXT NULL",
        "portrait_confidence": "VARCHAR(16) NULL",
        "knowledge_base": "TEXT NULL",
        "cognitive_style": "TEXT NULL",
        "error_prone_points": "TEXT NULL",
        "learning_history": "TEXT NULL",
        "course_progress": "TEXT NULL",
        "study_goal": "TEXT NULL",
        "study_time_prefer": "TEXT NULL",
        "knowledge_level": "TEXT NULL",
        "study_style": "TEXT NULL",
        "weak_points": "TEXT NULL",
        "challenge_scene": "TEXT NULL",
        "preferred_resource": "TEXT NULL",
        "profile_summary": "TEXT NULL",
    }
    for column, definition in profile_extra_columns.items():
        _add_column("student_profile", column, definition)

    _add_index("student_profile", "uk_student_profile_user_session", "`user_id`, `profile_session_id`", unique=True)
    _drop_index_if_exists("student_profile", "uk_student_profile_user_id")
    _add_index("profile_conversation", "uk_profile_conversation_user_session", "`user_id`, `profile_session_id`", unique=True)
    _drop_index_if_exists("profile_conversation", "uk_profile_conversation_user_id")
