from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pymysql
from pymysql.cursors import DictCursor

from config import config


class MySQLDB:
    def __init__(self):
        self.connection_options = {
            "host": config.MYSQL_HOST,
            "port": config.MYSQL_PORT,
            "user": config.MYSQL_USER,
            "password": config.MYSQL_PASSWORD,
            "database": config.MYSQL_DATABASE,
            "charset": config.MYSQL_CHARSET,
            "cursorclass": DictCursor,
            "autocommit": False,
        }

    @contextmanager
    def get_connection(self):
        conn = pymysql.connect(**self.connection_options)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def query_one(self, sql: str, params: Optional[Sequence[Any]] = None) -> Optional[Dict[str, Any]]:
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, params)
                    return cursor.fetchone()
        except pymysql.err.OperationalError as exc:
            if exc.args and exc.args[0] in (2006, 2013):
                with self.get_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(sql, params)
                        return cursor.fetchone()
            raise

    def query_all(self, sql: str, params: Optional[Sequence[Any]] = None) -> List[Dict[str, Any]]:
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, params)
                    return list(cursor.fetchall())
        except pymysql.err.OperationalError as exc:
            if exc.args and exc.args[0] in (2006, 2013):
                with self.get_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(sql, params)
                        return list(cursor.fetchall())
            raise

    def execute(self, sql: str, params: Optional[Sequence[Any]] = None) -> int:
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                return cursor.execute(sql, params)

    def execute_many(self, sql: str, params_list: Iterable[Sequence[Any]]) -> int:
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                return cursor.executemany(sql, params_list)

    def insert(self, table: str, data: Dict[str, Any]) -> int:
        if not data:
            raise ValueError("insert data cannot be empty")

        columns = ", ".join(f"`{column}`" for column in data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        sql = f"INSERT INTO `{table}` ({columns}) VALUES ({placeholders})"

        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, tuple(data.values()))
                return int(cursor.lastrowid)

    def update(
        self,
        table: str,
        data: Dict[str, Any],
        where: str,
        where_params: Optional[Sequence[Any]] = None,
    ) -> int:
        if not data:
            raise ValueError("update data cannot be empty")
        if not where:
            raise ValueError("where condition is required")

        assignments = ", ".join(f"`{column}` = %s" for column in data.keys())
        sql = f"UPDATE `{table}` SET {assignments} WHERE {where}"
        params: Tuple[Any, ...] = tuple(data.values()) + tuple(where_params or ())
        return self.execute(sql, params)

    def delete(self, table: str, where: str, where_params: Optional[Sequence[Any]] = None) -> int:
        if not where:
            raise ValueError("where condition is required")

        sql = f"DELETE FROM `{table}` WHERE {where}"
        return self.execute(sql, where_params)

    def upsert_by_unique_key(
        self,
        table: str,
        data: Dict[str, Any],
        update_fields: Optional[Sequence[str]] = None,
    ) -> int:
        if not data:
            raise ValueError("upsert data cannot be empty")

        columns = ", ".join(f"`{column}`" for column in data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        fields = update_fields or tuple(data.keys())
        update_clause = ", ".join(f"`{field}` = VALUES(`{field}`)" for field in fields)
        sql = f"INSERT INTO `{table}` ({columns}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {update_clause}"
        return self.execute(sql, tuple(data.values()))

    fetch_one = query_one
    fetch_all = query_all


mysql_db = MySQLDB()
