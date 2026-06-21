"""API 路由模块。

每个文件对应一组端点：
- query.py: POST /query (SSE 流式) + GET /health
- auth.py: POST /auth/register, /auth/login, /auth/refresh（Day 32 新增）
- export.py: POST /export/pdf, /export/excel, GET /export/{task_id}, GET /export/download/{filename}（Day 34 新增）
"""
