import psycopg2
import os

def get_schema() -> str:
    """从数据库自动提取表结构，注入给 LLM。"""
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", 5432),
        dbname=os.getenv("DB_NAME", "vantage"),
        user=os.getenv("DB_USER", "postgres"),
    )
    cur = conn.cursor()

    cur.execute("""
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position;
    """)

    rows = cur.fetchall()
    cur.close()
    conn.close()

    # 按表名分组，拼成可读字符串
    tables = {}
    for table, column, dtype in rows:
        tables.setdefault(table, []).append(f"{column}({dtype})")

    schema_str = ""
    for table, columns in tables.items():
        schema_str += f"{table}: {', '.join(columns)}\n"
        schema_str += "\n\n字段枚举值说明："
        schema_str += "\n  sales_records.region 的实际值：华东、华南、华北、华中"
        schema_str += "\n  sales_records.city 的实际值：上海、杭州、南京、广州、深圳、厦门、北京、天津、济南、武汉、长沙、郑州"
        schema_str += "\n  sales_records.year 的实际值：2024、2025"
        schema_str += "\n  查询时请注意按年份过滤，默认使用 2025 年数据"
    return schema_str.strip()