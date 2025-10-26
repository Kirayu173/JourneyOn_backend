# 接口文档（当前开发阶段）

本阶段涵盖认证、行程、任务、行程项、会话与智能体相关接口；新增知识库条目（KB Entries）、用户标签（User Tags）、系统日志级别调整与请求追踪。所有业务接口均要求认证（`Authorization: Bearer <token>`）。

## 通用响应包 Envelope
- 结构：`{"code": <int>, "msg": <str>, "data": <any>}`
- 成功：`code=0, msg="ok"`
- 失败：使用 HTTP 状态码作为 `code`（401/404/422/500），`msg` 为错误标识或描述，`data` 可能为错误详情。

## 请求追踪（Request ID）
- 客户端可在请求头中携带 `X-Request-ID`，用于端到端请求关联；若未提供，服务端会自动生成并在响应头返回。
- 所有路由统一返回 `X-Request-ID` 响应头；服务端日志以 JSON 格式记录，并包含 `request_id` 字段，便于检索与排错。
- 示例：
  - 请求：`GET /api/health`，头部可选 `X-Request-ID: 123e4567-e89b-12d3-a456-426614174000`
  - 响应头：`X-Request-ID: <同值或服务端生成的新值>`

## 认证（Auth）
- `POST /api/auth/register`
  - 请求：`{"email": "a@b.com", "password": "..."}`
  - 响应：`{"code":0,"msg":"ok","data":{"user_id":1}}`
- `POST /api/auth/login`
  - 请求：`{"email": "a@b.com", "password": "..."}`
  - 响应：`{"code":0,"msg":"ok","data":{"access_token":"...","token_type":"bearer"}}`

## 健康检查（Health）
- `GET /api/health`
  - 响应：`{"code":0,"msg":"ok","data":{"db":true,"redis":true,"qdrant":null}}`

## 行程（Trips）
- `POST /api/trips`
  - 描述：创建行程
  - 请求示例：`{"destination":"成都","start_date":"2025-11-01","end_date":"2025-11-05","budget":2000}`
  - 响应示例：`{"code":0,"msg":"ok","data":{"id":7,"destination":"成都","current_stage":"pre"}}`
- `GET /api/trips`
  - 描述：我的行程列表
  - 响应：`{"code":0,"msg":"ok","data":[...]}`
- `PATCH /api/trips/{trip_id}/stage`
  - 描述：更新行程阶段（如 `pre`→`on_trip`）
  - 请求：`{"stage":"on_trip"}`
  - 响应：`{"code":0,"msg":"ok","data":{"id":7,"current_stage":"on_trip"}}`
- `PATCH /api/trips/{trip_id}/stages/{stage_name}`
  - 描述：更新指定阶段的状态（`pending`→`in_progress`→`completed`）
  - 请求：`{"new_status":"in_progress"}` 或 `{"new_status":"completed"}`
  - 响应：`{"code":0,"msg":"ok","data":{"trip_id":7,"stage_name":"on","status":"completed","confirmed_at":"2025-10-26T12:00:00Z"}}`
  - 规则：
    - 合法状态：`pending`、`in_progress`、`completed`
    - 允许幂等（状态不变）
    - `pending` 仅可转为 `in_progress`；`in_progress` 仅可转为 `completed`；`completed` 为终态
  - 错误：`400 invalid_stage` / `400 invalid_status` / `400 invalid_transition` / `404 trip_not_found`

## 任务（Tasks）
- `POST /api/trips/{trip_id}/tasks`
  - 描述：创建任务
  - 请求示例：`{"stage":"pre","title":"预订机票","description":"周五前完成","priority":1,"assigned_to":null,"due_date":null,"meta":{}}`
  - 响应：`{"code":0,"msg":"ok","data":{"id":1,"trip_id":7,"title":"预订机票","status":"todo",...}}`
- `GET /api/trips/{trip_id}/tasks`
  - 描述：列出任务（可选按 `stage` 过滤）
  - 查询参数：`stage`（可选）
  - 响应：`{"code":0,"msg":"ok","data":[...]}`
- `PATCH /api/trips/{trip_id}/tasks/{task_id}`
  - 描述：更新任务（如状态、标题等）
  - 请求示例：`{"status":"done"}`
  - 响应：`{"code":0,"msg":"ok","data":{"id":1,"status":"done",...}}`
- `DELETE /api/trips/{trip_id}/tasks/{task_id}`
  - 描述：删除任务
  - 响应：`{"code":0,"msg":"ok","data":null}`

## 行程项（Itinerary Items）
- `POST /api/trips/{trip_id}/itinerary`
  - 描述：创建行程项
  - 请求示例：`{"day":1,"start_time":"09:00","end_time":"10:00","kind":"poi","title":"博物馆","location":"市中心","lat":30.0,"lng":120.0,"details":"需要预约"}`
  - 响应：`{"code":0,"msg":"ok","data":{"id":2,"trip_id":7,"day":1,...}}`
- `GET /api/trips/{trip_id}/itinerary`
  - 描述：列出行程项（可选按 `day` 过滤）
  - 查询参数：`day`（可选）
  - 响应：`{"code":0,"msg":"ok","data":[...]}`
- `PATCH /api/trips/{trip_id}/itinerary/{item_id}`
  - 描述：更新行程项
  - 请求示例：`{"title":"科技馆","start_time":"10:00"}`
  - 响应：`{"code":0,"msg":"ok","data":{"id":2,"title":"科技馆","start_time":"10:00",...}}`
- `DELETE /api/trips/{trip_id}/itinerary/{item_id}`
  - 描述：删除行程项
  - 响应：`{"code":0,"msg":"ok","data":null}`

## 知识库（KB Entries）
- `POST /api/trips/{trip_id}/kb_entries`
  - 描述：创建行程知识库条目
  - 请求示例：`{"source":"web","title":"出入境要求","content":"携带护照与签证","meta":{"lang":"zh"}}`
  - 响应：`{"code":0,"msg":"ok","data":{"id":10,"trip_id":7,"source":"web","title":"出入境要求","content":"携带护照与签证","meta":{},"embedding_id":null,"created_at":"2025-10-26T12:00:00Z"}}`
- `GET /api/trips/{trip_id}/kb_entries`
  - 描述：检索知识库条目（支持搜索与分页）
  - 查询参数：`q`（可选，全文搜索关键词）、`page`（默认 1）、`page_size`（默认 20）
  - 响应：`{"code":0,"msg":"ok","data":[{"id":10,"title":"出入境要求",...}]}`
- `PATCH /api/trips/{trip_id}/kb_entries/{entry_id}`
  - 描述：更新知识库条目
  - 请求示例：`{"title":"最新入境要求","meta":{"lang":"zh-CN"}}`
  - 响应：`{"code":0,"msg":"ok","data":{"id":10,"title":"最新入境要求",...}}`
- `DELETE /api/trips/{trip_id}/kb_entries/{entry_id}`
  - 描述：删除知识库条目
  - 响应：`{"code":0,"msg":"ok","data":null}`
- 说明：所有与行程关联的资源均做归属校验；行程不存在或无权限时返回 `404 trip_not_found`。

## 会话（Conversations）
- `GET /api/trips/{trip_id}/conversations`
  - 描述：读取会话历史（按行程归属校验）
  - 查询参数：`stage`（可选）、`limit`（默认 20）
  - 响应：`{"code":0,"msg":"ok","data":[{"id":3,"role":"user","stage":"pre","message":"...","created_at":"2025-10-25T12:00:00Z"}]}`

## 智能体（Agent）
- `POST /api/agent/chat`
  - 描述：发送用户消息，返回模拟回复与可能的工具调用（当前阶段为 stub）
  - 请求示例：`{"trip_id":7,"stage":"pre","message":"帮我规划一下","client_ctx":{}}`
  - 响应：`{"code":0,"msg":"ok","data":{"conversation":{...},"agent":{"reply":"...","tools":[],"task_updates":[]}}}`

## 用户标签（User Tags）
- `POST /api/user_tags`
  - 描述：创建用户标签
  - 请求示例：`{"tag":"徒步","weight":0.8,"source_trip_id":7}`
  - 响应：`{"code":0,"msg":"ok","data":{"id":1,"tag":"徒步","weight":0.8,"source_trip_id":7}}`
- `GET /api/user_tags`
  - 描述：查询用户标签（支持过滤与分页）
  - 查询参数：`tag`（可选，精确匹配）、`source_trip_id`（可选）、`page`（默认 1）、`page_size`（默认 20）
  - 响应：`{"code":0,"msg":"ok","data":[{"id":1,"tag":"徒步","weight":0.8}]}`
- `PATCH /api/user_tags/{tag_id}`
  - 描述：更新用户标签
  - 请求示例：`{"weight":0.9}`
  - 响应：`{"code":0,"msg":"ok","data":{"id":1,"tag":"徒步","weight":0.9}}`
- `DELETE /api/user_tags/{tag_id}`
  - 描述：删除用户标签
  - 响应：`{"code":0,"msg":"ok","data":null}`
- `POST /api/user_tags/bulk_upsert`
  - 描述：批量 upsert 标签（按 `tag` 合并，已存在则更新权重/来源）
  - 请求示例：`{"items":[{"tag":"徒步","weight":0.9},{"tag":"美食","source_trip_id":7}]}` 或直接数组 `[{"tag":"徒步","weight":0.9},{"tag":"美食","source_trip_id":7}]`
  - 响应：`{"code":0,"msg":"ok","data":[{"id":1,"tag":"徒步","weight":0.9},{"id":2,"tag":"美食","source_trip_id":7}]}`
- 说明：所有操作均限定在当前用户的数据范围内。

## 系统（System）
- `PATCH /api/system/log-level`
  - 描述：动态调整应用根日志级别
  - 请求示例：`{"level":"info"}`
  - 响应：`{"code":0,"msg":"ok","data":{"level":"info"}}`
  - 支持级别：`debug`、`info`、`warning`、`error`
  - 认证要求：需携带有效的 `Authorization` 头

## 错误码与异常格式
- 401 `invalid_token` / `invalid_token_subject` / `user_not_found`
- 404 `trip_not_found`（所有与行程关联的资源均做归属校验）
- 422 `validation_error`（参数校验失败，`data` 为错误详情列表）
- 500 `internal_error`
- 说明：通过统一异常处理中间件返回 Envelope 格式（`code` 为 HTTP 状态码）。

## 版本与变更历史
- v0.2.0：完成 Pydantic v2 迁移（`from_orm` → `model_validate`）；更新响应模型配置；新增迁移测试；接口行为保持一致。
- v0.3.0：新增 `kb_entries` 与 `user_tags` 模块（含 CRUD 与批量 upsert）；引入请求 ID 中间件与日志轮转；新增系统端点用于动态调整日志级别；同步更新接口文档与测试。