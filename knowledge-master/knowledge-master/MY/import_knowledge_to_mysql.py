"""Import generated local knowledge-tree files into MySQL study_resource.

This script keeps the database design intentionally simple for the demo:

* one row with resource_type='knowledge_tree' stores the whole tree JSON and
  Mermaid preview.
* one row per knowledge point with resource_type='knowledge_point' stores the
  chunk text and metadata.

It reads database settings from A3_Learning_Agent/backend/.env by default.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

try:
    import pymysql
    from pymysql.cursors import DictCursor
except ImportError as exc:
    raise SystemExit("Missing dependency: PyMySQL. Run: pip install PyMySQL") from exc


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def connect(env: dict[str, str], *, with_database: bool = True):
    options: dict[str, Any] = {
        "host": env.get("MYSQL_HOST", "127.0.0.1"),
        "port": int(env.get("MYSQL_PORT", "3306")),
        "user": env.get("MYSQL_USER", "root"),
        "password": env.get("MYSQL_PASSWORD", ""),
        "charset": env.get("MYSQL_CHARSET", "utf8mb4"),
        "cursorclass": DictCursor,
        "autocommit": False,
    }
    if with_database:
        options["database"] = env.get("MYSQL_DATABASE", "a3_learning_agent")
    return pymysql.connect(**options)


def ensure_database(env: dict[str, str]) -> None:
    database = env.get("MYSQL_DATABASE", "a3_learning_agent")
    with connect(env, with_database=False) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{database}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()


def column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*) AS count
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
        """,
        (table, column),
    )
    return bool(cursor.fetchone()["count"])


def index_exists(cursor, table: str, index_name: str) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*) AS count
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND INDEX_NAME = %s
        """,
        (table, index_name),
    )
    return bool(cursor.fetchone()["count"])


def ensure_study_resource_extension(conn) -> None:
    with conn.cursor() as cursor:
        if not column_exists(cursor, "study_resource", "course"):
            cursor.execute(
                "ALTER TABLE study_resource "
                "ADD COLUMN course VARCHAR(128) NOT NULL DEFAULT '软件工程' COMMENT '课程名称' AFTER user_id"
            )
        if not column_exists(cursor, "study_resource", "source_id"):
            cursor.execute(
                "ALTER TABLE study_resource "
                "ADD COLUMN source_id VARCHAR(128) NULL COMMENT '来源ID，如知识点chunk_id或任务ID' AFTER resource_type"
            )
        if not column_exists(cursor, "study_resource", "metadata"):
            cursor.execute(
                "ALTER TABLE study_resource "
                "ADD COLUMN metadata JSON NULL COMMENT '资源元数据：页码、知识点类型、关系、审核结果等' AFTER content"
            )
        if not column_exists(cursor, "study_resource", "update_time"):
            cursor.execute(
                "ALTER TABLE study_resource "
                "ADD COLUMN update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP "
                "ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间' AFTER create_time"
            )
        if not index_exists(cursor, "study_resource", "idx_study_resource_course"):
            cursor.execute("CREATE INDEX idx_study_resource_course ON study_resource(course)")
        if not index_exists(cursor, "study_resource", "idx_study_resource_source_id"):
            cursor.execute("CREATE INDEX idx_study_resource_source_id ON study_resource(source_id)")
        if not index_exists(cursor, "study_resource", "idx_study_resource_course_type"):
            cursor.execute("CREATE INDEX idx_study_resource_course_type ON study_resource(course, resource_type)")
    conn.commit()


def ensure_import_user(conn, username: str) -> int:
    with conn.cursor() as cursor:
        cursor.execute("SELECT id FROM `user` WHERE username=%s", (username,))
        row = cursor.fetchone()
        if row:
            return int(row["id"])
        cursor.execute(
            "INSERT INTO `user` (username, password) VALUES (%s, %s)",
            (username, "local_knowledge_import_no_login"),
        )
        user_id = int(cursor.lastrowid)
    conn.commit()
    return user_id


def upsert_resource(
    conn,
    *,
    user_id: int,
    course: str,
    resource_type: str,
    source_id: str,
    title: str,
    content: str,
    metadata: dict[str, Any],
) -> int:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT id FROM study_resource
            WHERE user_id=%s AND course=%s AND resource_type=%s AND source_id=%s
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id, course, resource_type, source_id),
        )
        row = cursor.fetchone()
        payload = json.dumps(metadata, ensure_ascii=False)
        if row:
            cursor.execute(
                """
                UPDATE study_resource
                SET title=%s, content=%s, metadata=%s
                WHERE id=%s
                """,
                (title, content, payload, row["id"]),
            )
            resource_id = int(row["id"])
        else:
            cursor.execute(
                """
                INSERT INTO study_resource
                  (user_id, course, resource_type, source_id, title, content, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (user_id, course, resource_type, source_id, title, content, payload),
            )
            resource_id = int(cursor.lastrowid)
    conn.commit()
    return resource_id


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def import_knowledge(conn, args: argparse.Namespace) -> dict[str, int]:
    tree = load_json(Path(args.tree_json))
    semantic = load_json(Path(args.semantic_json))
    mermaid = Path(args.mermaid).read_text(encoding="utf-8") if args.mermaid else ""
    course = args.course or tree.get("course") or semantic.get("course") or "软件工程"
    chunks = {chunk["chunk_id"]: chunk for chunk in semantic.get("knowledge_chunks", [])}

    tree_content = json.dumps(
        {
            "tree": tree,
            "mermaid": mermaid,
            "semantic_stats": semantic.get("stats", {}),
        },
        ensure_ascii=False,
        indent=2,
    )
    tree_id = upsert_resource(
        conn,
        user_id=args.user_id,
        course=course,
        resource_type="knowledge_tree",
        source_id=f"{course}:knowledge_tree",
        title=f"{course}知识树",
        content=tree_content,
        metadata={
            "source": "MY/optimized_outputs",
            "tree_stats": tree.get("stats", {}),
            "semantic_stats": semantic.get("stats", {}),
        },
    )

    point_count = 0
    for point in tree.get("knowledge_points", []):
        chunk_id = point.get("chunk_id")
        chunk = chunks.get(chunk_id, {})
        metadata = {
            **point,
            "chunk_metadata": chunk.get("metadata", {}),
            "relations": {
                "prerequisite": chunk.get("metadata", {}).get("prerequisite_node_ids", []),
                "next": chunk.get("metadata", {}).get("next_node_ids", []),
            },
        }
        upsert_resource(
            conn,
            user_id=args.user_id,
            course=course,
            resource_type="knowledge_point",
            source_id=str(chunk_id),
            title=str(point.get("title") or "知识点"),
            content=str(chunk.get("content_text") or ""),
            metadata=metadata,
        )
        point_count += 1

    return {"knowledge_tree": 1 if tree_id else 0, "knowledge_point": point_count}


def parse_args() -> argparse.Namespace:
    default_root = Path(__file__).resolve().parents[1]
    default_backend = default_root / "A3_Learning_Agent" / "backend"
    default_outputs = default_root / "MY" / "optimized_outputs"
    parser = argparse.ArgumentParser(description="Import local knowledge-tree JSON into MySQL study_resource.")
    parser.add_argument("--env", default=str(default_backend / ".env"))
    parser.add_argument("--tree-json", default=str(default_outputs / "rule_chunks_knowledge_tree.json"))
    parser.add_argument("--semantic-json", default=str(default_outputs / "rule_chunks_semantic.json"))
    parser.add_argument("--mermaid", default=str(default_outputs / "rule_chunks_knowledge_tree.mmd"))
    parser.add_argument("--course", default="软件工程")
    parser.add_argument("--username", default="knowledge_admin")
    parser.add_argument("--user-id", type=int, default=0, help="Existing user id. If omitted, creates/uses --username.")
    parser.add_argument("--create-database", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    env = load_env(Path(args.env))
    for key, value in os.environ.items():
        if key.startswith("MYSQL_"):
            env[key] = value

    if args.create_database:
        ensure_database(env)

    with connect(env) as conn:
        ensure_study_resource_extension(conn)
        if not args.user_id:
            args.user_id = ensure_import_user(conn, args.username)
        result = import_knowledge(conn, args)
        print(
            "Imported local knowledge resources into MySQL study_resource:\n"
            f"  database: {env.get('MYSQL_DATABASE', 'a3_learning_agent')}\n"
            f"  user_id: {args.user_id}\n"
            f"  knowledge_tree rows: {result['knowledge_tree']}\n"
            f"  knowledge_point rows: {result['knowledge_point']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
