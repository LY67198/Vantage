"""SQL 工具 — execute_query。"""
import redis
from decimal import Decimal
import json
from decimal import Decimal
from langchain_core.tools import tool
import psycopg2
import os


r = redis.Redis(
    host=os.getenv("REDIS_HOST","localhost"),
    port=int(os.getenv("REDIS_PORT",6379)),
    decode_responses= True
)


def get_db_conn():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", 5432),
        dbname=os.getenv("DB_NAME", "vantage"),
        user=os.getenv("DB_USER", "postgres"),
    )



@tool
def execute_query(sql: str) -> dict:
    """执行销售数据查询，优先读缓存"""
    cache_key = f"sql:{hash(sql)}"

    cached = r.get(cache_key)
    if cached:
        print("命中缓存")
        return json.loads(cached)

    # redis 未命中查 DB  
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

        result =  {
            "columns": columns,
            "rows": [
                {col: convert(val) for col, val in zip(columns, row)}
                for row in rows
            ],
            "sql_executed": sql,
        }
    
        r.set(cache_key,json.dumps(result,ensure_ascii=False),ex=3600)
        return result
    except Exception as e:
        return {"error": str(e), "sql_executed": sql}