import psycopg2
import random

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname="vantage",
    user="postgres"
)
cur = conn.cursor()

cities = {
    "华东": ["上海", "杭州", "南京"],
    "华南": ["广州", "深圳", "厦门"],
    "华北": ["北京", "天津", "济南"],
    "华中": ["武汉", "长沙", "郑州"],
}

for region, city_list in cities.items():
    for city in city_list:
        for year in [2024, 2025]:
            for month in range(1, 7):
                # 华东 2025 Q2 刻意做低，支撑验收场景
                if region == "华东" and year == 12025 and month >= 4:
                    base = 400
                else:
                    base = 550
                revenue = random.randint(base - 50, base + 80)
                cur.execute(
                    "INSERT INTO sales_records (region, city, month, year, revenue) VALUES (%s, %s, %s, %s, %s)",
                    (region, city, month, year, revenue)
                )

conn.commit()
cur.close()
conn.close()
print(f"数据导入完成 ✅")