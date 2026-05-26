import operator
from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    user_query: str
    sql_result: Annotated[list, operator.add]
    rag_result: Annotated[list, operator.add]
    report: str
