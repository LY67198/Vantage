"""SQL Agent Mock 数据源。"""
SCENARIOS = {
    "q2_east_china": {
        "region": "华东",
        "period": "2025-Q2",
        "revenue": 2340,
        "yoy_change": -12.3,
        "raw_rows": [
            {"city": "上海", "q2_2024": 1480, "q2_2025": 1280, "yoy_change": -13.5},
            {"city": "杭州", "q2_2024": 680, "q2_2025": 610, "yoy_change": -10.3},
            {"city": "南京", "q2_2024": 510, "q2_2025": 450, "yoy_change": -11.8},
        ],
        "sql_executed": (
            "SELECT city, q2_2024, q2_2025, "
            "ROUND((q2_2025 - q2_2024) / q2_2024 * 100, 1) AS yoy_change "
            "FROM sales_records WHERE region = '华东' AND period = 'Q2';"
        ),
    },
}

