"""SQL 工具 — execute_query。"""
from langchain_core.tools import tool
import psycopg2
import os


def get_db_conn():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", 5432),
        dbname=os.getenv("DB_NAME", "vantage"),
        user=os.getenv("DB_USER", "postgres"),
    )

from decimal import Decimal

@tool
def execute_query(sql: str) -> dict:
    """执行销售数据查询。"""
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute(sql)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        cur.close()
        conn.close()

        # Decimal → float，避免序列化问题
        def convert(val):
            return float(val) if isinstance(val, Decimal) else val

        return {
            "columns": columns,
            "rows": [
                {col: convert(val) for col, val in zip(columns, row)}
                for row in rows
            ],
            "sql_executed": sql,
        }
    except Exception as e:
        return {"error": str(e), "sql_executed": sql}