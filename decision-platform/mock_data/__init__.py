"""Mock 数据注册中心。"""
from mock_data.crm_sales import SCENARIOS as CRM_SCENARIOS
from mock_data.knowledge_base import SCENARIOS as KB_SCENARIOS

AVAILABLE_SCENARIOS = ["q2_east_china"]


def validate_scenarios() -> None:
    """启动时校验 CRM 与知识库场景 key 是否一致。"""
    registered = set(AVAILABLE_SCENARIOS)
    crm_keys = set(CRM_SCENARIOS)
    kb_keys = set(KB_SCENARIOS)

    if registered != crm_keys or registered != kb_keys:
        raise ValueError(
            "Mock 场景注册不一致: "
            f"registered={registered}, crm={crm_keys}, kb={kb_keys}"
        )


if __name__ == "__main__":
    rst = validate_scenarios()
    print(rst)