"""API 中间件。

- auth.py:     JWT Bearer token 验证 → Depends(get_current_user)（Day 32 新增）
- tracing.py:  trace_id 注入 + 请求日志 contextvars（Day 38 新增）
"""