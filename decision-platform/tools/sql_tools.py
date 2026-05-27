"""SQL 工具 — execute_query。"""
from langchain_core.tools import tool
from mock_data.crm_sales import SCENARIOS


@tool
def execute_query(sql:str)->dict:
    """执行销售数据查询。"""
    scenario = "q2_east_china"
    data = SCENARIOS.get(scenario)

    if not data:
        return {"error":f"未找到场景:{scenario}","sql_executed":sql}
    
    return {
        **data,
        "sql_executed":sql or data.get("sql_executed","")
    }