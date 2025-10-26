# JourneyOn 后端接口文档（2025-10 更新）

本文档整理当前版本（`0.1.0`）已实现的 REST 接口，涵盖认证、行程、任务、行程项、对话、知识库、向量检索、文件报告、用户标签、系统控制与审计日志模块。除健康检查等公开接口外，所有业务接口均需在请求头携带 `Authorization: Bearer <token>`。

## 统一响应 Envelope

- 格式：`{"code": <int>, "msg": <str>, "data": <any>}`。
- 成功：`code = 0`，`msg = "ok"`，`data` 为业务数据。
- 失败：抛出 `HTTPException` 后由统一异常处理中间件包装，`code` 为 HTTP 状态码（如 `400`/`401`/`403`/`404`/`429`/`500`），`msg` 为错误标识，`data` 为空或附带错误详情。
- 所有响应均带 `X-Request-ID` 头，便于日志追踪。客户端可自定义该值。

## 认证（Auth）

| 方法 | 路径 | 描述 | 请求体 | 响应示例 |
| ---- | ---- | ---- | ------ | -------- |
| POST | `/api/auth/register` | 注册账号并返回 JWT | `{ "username": "alice", "email": "alice@example.com", "password": "TestPass123!" }` | `{ "code":0,"msg":"ok","data":{"user":{"id":1,"username":"alice","email":"alice@example.com"},"token":"..."}}` |
| POST | `/api/auth/login` | 使用用户名或邮箱登录，返回 JWT | `{ "username_or_email": "alice", "password": "TestPass123!" }` | 同上 |

## 健康检查（Health）

| 方法 | 路径 | 描述 | 响应 |
| ---- | ---- | ---- | ---- |
| GET | `/api/health` | 检查数据库、Redis、Qdrant（若配置）可用性 | `{ "code":0,"msg":"ok","data":{"db":true,"redis":false,"qdrant":null}}` |
| GET | `/api/kb/health` | 检查知识库向量组件：Qdrant 集合、Embedding 服务、Redis 缓存 | `{ "code":0,"msg":"ok","data":{"qdrant":false,"embedding":{"provider":"ollama","ok":false,...},"redis":false}}` |

## 行程（Trips）

| 方法 | 路径 | 描述 |
| ---- | ---- | ---- |
| POST | `/api/trips` | 创建行程（自动初始化 pre/on/post 三个阶段，`pre` 默认进行中）。请求体可包含 `title`、`origin`、`destination`、`start_date`、`duration_days`、`budget`、`currency`、`preferences` 等。|
| GET | `/api/trips` | 列出当前用户的行程（按创建时间倒序）。|
| GET | `/api/trips/{trip_id}` | 获取行程详情（含偏好、上下文等字段）。|
| PATCH | `/api/trips/{trip_id}/stage` | 切换行程主阶段。`new_stage` 允许值：`pre`/`on`/`post`。写入审计日志 `trip_stage_updated`。|
| PATCH | `/api/trips/{trip_id}/stages/{stage_name}` | 更新指定阶段（`pre`/`on`/`post`）的执行状态。合法流转：`pending → in_progress → completed`，幂等更新允许，非法流转返回 `400 invalid_transition`。完成后会记录 `confirmed_at` 与审计日志。|

错误约定：行程不存在返回 `404 trip_not_found`，无权访问返回 `403`。

## 任务（Tasks）

| 方法 | 路径 | 描述 |
| ---- | ---- | ---- |
| POST | `/api/trips/{trip_id}/tasks` | 创建任务，需指定 `stage`、`title`，可选 `description`、`priority`、`assigned_to`、`due_date`、`meta`。|
| GET | `/api/trips/{trip_id}/tasks` | 查询任务，可通过查询参数 `stage` 过滤。|
| PATCH | `/api/trips/{trip_id}/tasks/{task_id}` | 更新任务字段（含状态），写入审计日志 `task_updated`。|
| DELETE | `/api/trips/{trip_id}/tasks/{task_id}` | 删除任务，写入审计日志 `task_deleted`。|

## 行程项（Itinerary Items）

| 方法 | 路径 | 描述 |
| ---- | ---- | ---- |
| POST | `/api/trips/{trip_id}/itinerary` | 新增日程项，字段含 `day`、`start_time`、`end_time`、`kind`、`title`、`location`、`lat`、`lng`、`details`。|
| GET | `/api/trips/{trip_id}/itinerary` | 列表查询，支持 `day` 查询参数。|
| PATCH | `/api/trips/{trip_id}/itinerary/{item_id}` | 更新日程项，写入审计日志 `itinerary_item_updated`。|
| DELETE | `/api/trips/{trip_id}/itinerary/{item_id}` | 删除日程项，写入审计日志 `itinerary_item_deleted`。|

## 对话记录（Conversations）

| 方法 | 路径 | 描述 |
| ---- | ---- | ---- |
| GET | `/api/trips/{trip_id}/conversations` | 读取行程下的历史消息。支持查询参数 `stage`（可选）与 `limit`（默认 20）。返回 `ConversationResponse` 列表。|

## 智能体对话（Agent）

| 方法 | 路径 | 描述 |
| ---- | ---- | ---- |
| POST | `/api/agent/chat` | 调用配置的 LLM（Ollama / 智谱）生成回复，返回 `agent.reply`、`agent.run_id`、`usage` 等信息。异常时 `agent.error` 会带错误标识。|
| POST | `/api/agent/chat/stream` | SSE 流式接口，事件序列包含 `run_started`、`message`（多段增量，`meta.delta=true`）以及最终整合的助手消息和 `run_completed`。|
| WS | `/api/agent/ws/chat` | WebSocket 版实时对话，事件结构与 SSE 相同。握手需附带 `token` 查询参数或 `Authorization` 头。|

## 知识库条目（KB Entries）

| 方法 | 路径 | 描述 |
| ---- | ---- | ---- |
| POST | `/api/trips/{trip_id}/kb_entries` | 创建知识条目，字段含 `source`、`title`、`content`、`meta`。|
| GET | `/api/trips/{trip_id}/kb_entries` | 查询条目，支持 `q`（关键词全文搜索，占位实现）、`page`、`page_size`。|
| PATCH | `/api/trips/{trip_id}/kb_entries/{entry_id}` | 更新条目。|
| DELETE | `/api/trips/{trip_id}/kb_entries/{entry_id}` | 删除条目。|

## 向量检索（KB Vector）

| 方法 | 路径 | 描述 |
| ---- | ---- | ---- |
| POST | `/api/kb/search` | RAG 语义检索接口。请求体：`{"query":"文本","top_k":10,"rerank":true,"filters":{"trip_id":1}}`，返回 `[{"id":<entry_id>,"title":...,"similarity":0.87}]`。Redis 缓存命中后直接返回，未命中则调用异步嵌入服务 + Qdrant 搜索，若启用 `rerank` 且配置了 `OLLAMA_RERANK_MODEL`，会使用精排模型优化排序。|
| GET | `/api/kb/search` | 查询参数版语义检索，`q` 为必填，其余与 POST 相同（`filters` 支持 JSON 字符串）。|
| GET | `/api/kb/health` | 返回 Qdrant 集合是否存在、Embedding 服务健康状态以及 Redis ping 结果。|

说明：若未启用嵌入或未配置 Qdrant，接口返回 `code=0`、`data=[]` 并附带 `msg` 表明不可用，便于前端降级。

## 报告文件（Reports）

| 方法 | 路径 | 描述 |
| ---- | ---- | ---- |
| POST | `/api/trips/{trip_id}/reports` | 以 Base64 上传文件。请求体：`{"filename":"report.pdf","content_type":"application/pdf","data":"...","format":"pdf"}`。成功后保存至当前存储后端（默认本地目录 `storage/`），并写入 `reports` 表与审计日志 `report_created`。|
| GET | `/api/trips/{trip_id}/reports` | 列出行程下的报告。|
| GET | `/api/trips/{trip_id}/reports/{report_id}` | 获取单个报告的元数据。|
| GET | `/api/trips/{trip_id}/reports/{report_id}/download` | 下载原始文件，返回 `FileResponse`。文件缺失返回 `404 file_missing`。|
| DELETE | `/api/trips/{trip_id}/reports/{report_id}` | 删除报告并清理存储文件，记录审计日志 `report_deleted`。|

## 用户标签（User Tags）

| 方法 | 路径 | 描述 |
| ---- | ---- | ---- |
| POST | `/api/user_tags` | 创建标签（`tag`、`weight`、`source_trip_id`）。|
| GET | `/api/user_tags` | 查询标签，支持 `tag`、`source_trip_id`、`page`、`page_size`。|
| PATCH | `/api/user_tags/{tag_id}` | 更新标签权重或来源。|
| DELETE | `/api/user_tags/{tag_id}` | 删除标签。|
| POST | `/api/user_tags/bulk_upsert` | 批量 upsert，支持数组或 `{ "items": [...] }` 格式。|

## 系统控制（System）

| 方法 | 路径 | 描述 |
| ---- | ---- | ---- |
| PATCH | `/api/system/log-level` | 动态调整应用日志级别，请求体：`{"level":"info"}`。返回当前级别。|

## 审计日志（Audit Logs）

| 方法 | 路径 | 描述 |
| ---- | ---- | ---- |
| GET | `/api/audit-logs` | 管理员查询关键操作记录。支持查询参数 `limit`（默认 100，最大 500）、`offset`、`user_id`、`trip_id`。仅 `meta.is_admin = true` 用户可访问，普通用户返回 `403 admin_required`。返回字段：`id`、`user_id`、`trip_id`、`action`、`detail`、`created_at`。|

## 错误码参考

| 场景 | HTTP 状态 | `msg` |
| ---- | ---- | ---- |
| 认证失败 | 401 | `invalid_token` / `invalid_credentials` |
| 权限不足 | 403 | `admin_required` |
| 资源不存在 | 404 | `trip_not_found` / `report_not_found` / `stage_not_found` |
| 数据校验失败 | 400 | `invalid_stage` / `invalid_status` / `invalid_transition` / `invalid_base64` |
| 频控触发 | 429 | `rate_limited` |
| 存储故障 | 500 | `storage_error` |

## 附录

- 本地文件存储目录可通过环境变量 `LOCAL_STORAGE_PATH` 配置，未来可无缝切换 MinIO 等云存储。
- Redis URL 配置后 `/api/kb/search` 将使用共享缓存与分布式限流；若 Redis 不可用则自动退化。
- 所有数据库模型及字段详见 `app/db/models.py`。
