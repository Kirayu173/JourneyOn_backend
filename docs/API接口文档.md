# JourneyOn API 接口文档

> 版本：v0.1.0（根据 `app/main.py` 注册的路由整理）。所有响应均使用统一结构 `Envelope`，格式为：
>
> ```json
> {
>   "code": 0,
>   "msg": "ok",
>   "data": {...}
> }
> ```
>
> 若请求失败，`code` 将返回 HTTP 状态码或业务错误码，`msg` 为错误描述，`data` 包含详细信息或为 `null`。【F:app/main.py†L1-L67】【F:app/schemas/common.py†L1-L14】【F:app/middleware/errors.py†L1-L37】

## 1. 通用说明
- **基础路径**：所有 REST 接口均位于 `/api` 前缀下，WebSocket 位于 `/api/agent/ws/chat`。【F:app/main.py†L45-L67】【F:app/api/routes/agent.py†L1-L116】
- **认证方式**：除登录/注册、健康检查、向量检索健康检查外，接口默认需要携带 `Authorization: Bearer <JWT>` 头部。JWT 通过 `/api/auth/login` 或 `/api/auth/register` 获取。【F:app/api/deps.py†L1-L35】【F:app/api/routes/auth.py†L1-L53】
- **内容类型**：请求体使用 `application/json`，文件上传采用 Base64 编码字段 `data`。【F:app/api/routes/reports.py†L1-L59】
- **错误码约定**：常见业务错误包括 `invalid_*`, `*_not_found`, `user_already_exists`, `rate_limited`, `storage_error` 等，详见各接口说明。【F:app/api/routes/auth.py†L24-L52】【F:app/api/routes/trips.py†L87-L147】【F:app/api/routes/kb_vector.py†L88-L170】

## 2. 认证模块
### 2.1 用户注册
- **方法与路径**：`POST /api/auth/register`
- **功能**：创建用户并返回 JWT。
- **请求体参数**：
  | 字段 | 类型 | 必填 | 约束 |
  | --- | --- | --- | --- |
  | username | string | 是 | 非空 |
  | email | string(Email) | 是 | Pydantic 邮箱校验 |
  | password | string | 是 | 非空 |
- **成功响应**：`data` 包含 `user`（`id/username/email`）与 `token`。【F:app/api/routes/auth.py†L24-L44】
- **错误响应**：
  - `400 invalid_registration_payload`：字段为空。
  - `409 user_already_exists`：邮箱或用户名重复。【F:app/api/routes/auth.py†L24-L36】【F:app/services/user_service.py†L19-L37】
- **示例**：
  - 请求头：`Content-Type: application/json`
  - 请求体：
    ```json
    {"username": "user_123", "email": "user_123@example.com", "password": "Secret123!"}
    ```
  - 成功响应：
    ```json
    {
      "code": 0,
      "msg": "ok",
      "data": {
        "user": {"id": 1, "username": "user_123", "email": "user_123@example.com"},
        "token": "<JWT>"
      }
    }
    ```【F:tests/test_phase_one.py†L11-L37】

### 2.2 用户登录
- **方法与路径**：`POST /api/auth/login`
- **功能**：通过用户名或邮箱 + 密码获取 JWT。
- **请求体**：
  | 字段 | 类型 | 必填 | 说明 |
  | --- | --- | --- | --- |
  | username_or_email | string | 是 | 支持用户名或邮箱 |
  | password | string | 是 | | 
- **错误响应**：
  - `400 invalid_login_payload`：缺失字段。
  - `401 invalid_credentials`：认证失败。【F:app/api/routes/auth.py†L36-L52】
- **示例响应**：与注册成功响应结构一致。【F:tests/test_phase_one.py†L23-L34】

## 3. 健康检查
### 3.1 综合健康检查
- **方法与路径**：`GET /api/health`
- **功能**：检查数据库、Redis、Qdrant 可用性。
- **响应数据**：`data` 包含 `db`, `redis`, `qdrant` 布尔状态；若未配置 Qdrant 返回 `null`。【F:app/api/routes/health.py†L1-L42】
- **错误响应**：当数据库或 Redis 异常时 `code=0` 但 `msg=degraded`。【F:app/api/routes/health.py†L33-L42】
- **示例响应**：
  ```json
  {"code":0,"msg":"ok","data":{"db":true,"redis":true,"qdrant":null}}
  ```

## 4. 行程管理模块
### 4.1 创建行程
- **方法与路径**：`POST /api/trips`
- **认证**：需要。
- **请求体关键字段**（全部可选除 `currency` 默认 `CNY`）：`title`,`origin`,`destination`,`start_date`,`duration_days`,`budget`,`preferences`,`agent_context` 等。【F:app/api/routes/trips.py†L17-L50】
- **成功响应**：返回行程概要（`id/title/destination/start_date/current_stage/status` 等）。【F:app/api/routes/trips.py†L51-L69】
- **错误响应**：权限不足时返回 `401` 或 `403`（JWT 校验失败）。
- **示例**：见测试 `test_trips_crud_flow`。【F:tests/test_phase_one.py†L38-L77】

### 4.2 查询与详情
- `GET /api/trips`：返回当前用户所有行程列表。
- `GET /api/trips/{trip_id}`：返回指定行程详细信息，未找到返回 `404 trip_not_found`。【F:app/api/routes/trips.py†L70-L108】

### 4.3 更新行程阶段
- `PATCH /api/trips/{trip_id}/stage`
  - 请求体：`{ "new_stage": "pre"|"on"|"post" }`
  - 错误：`400 invalid_stage`（非法阶段）、`404 trip_not_found`。【F:app/api/routes/trips.py†L109-L135】
- `PATCH /api/trips/{trip_id}/stages/{stage_name}`
  - 请求体：`{ "new_status": "pending|in_progress|completed" }`
  - 错误：`400 invalid_status|invalid_transition|invalid_stage`、`404 stage_not_found`。【F:app/api/routes/trips.py†L137-L176】

## 5. 任务管理
- **路径前缀**：`/api/trips/{trip_id}/tasks`
- **请求模型**：`TaskCreate`、`TaskUpdate`。【F:app/api/routes/tasks.py†L1-L69】【F:app/schemas/task_schemas.py†L1-L36】

| 操作 | 方法 | 说明 | 成功响应 | 主要错误 |
| --- | --- | --- | --- | --- |
| 创建任务 | POST `/api/trips/{trip_id}/tasks` | 新建任务并记录审计日志 | `data` 为任务详情 | `404 trip_not_found`（行程不存在） |
| 列出任务 | GET `/api/trips/{trip_id}/tasks` | 支持 `stage` 筛选 | `data` 为任务数组 | 同上 |
| 更新任务 | PATCH `/api/trips/{trip_id}/tasks/{task_id}` | 支持部分字段更新 | 返回更新后任务 | `404 task_not_found` |
| 删除任务 | DELETE `/api/trips/{trip_id}/tasks/{task_id}` | 删除后返回 `data=null` | `404 task_not_found` |

示例场景参见测试 `test_phase_two_tasks`。【F:tests/test_phase_two_tasks.py†L1-L116】

## 6. 行程日程管理
- **路径前缀**：`/api/trips/{trip_id}/itinerary`
- **模型**：`ItineraryItemCreate/Update/Response`。【F:app/api/routes/itinerary_items.py†L1-L83】【F:app/schemas/itinerary_schemas.py†L1-L48】
- **操作**：POST 创建、GET 按 `day` 过滤、PATCH 更新、DELETE 删除；错误同样返回 `trip_not_found` 或 `item_not_found`（通过服务层抛出）。

## 7. 会话历史
- **路径**：`GET /api/trips/{trip_id}/conversations`
- **参数**：`stage`（可选），`limit`（默认 20）。
- **响应**：会话记录列表，包含 `id/stage/role/message/message_meta/created_at`。【F:app/api/routes/conversations.py†L1-L24】【F:app/schemas/conversation_schemas.py†L1-L18】

## 8. 报告与文件
- **路径前缀**：`/api/trips/{trip_id}/reports`
- **操作**：
  | 操作 | 方法 | 说明 |
  | --- | --- | --- |
  | 上传报告 | POST | Base64 文件写入本地存储，返回报告元数据 |
  | 列出报告 | GET | 返回报告数组 |
  | 获取报告 | GET `/{report_id}` | 返回报告详情 |
  | 下载文件 | GET `/{report_id}/download` | 以文件流返回 |
  | 删除报告 | DELETE `/{report_id}` | 删除数据库记录并移除文件 |
- **错误**：`400 invalid_base64`、`404 trip_not_found/report_not_found/file_missing`、`500 storage_error`。【F:app/api/routes/reports.py†L1-L129】【F:app/services/report_service.py†L1-L84】
- **示例**：参见 `tests/test_reports.py`。【F:tests/test_reports.py†L1-L128】

## 9. 知识库管理
### 9.1 条目 CRUD
- **前缀**：`/api/trips/{trip_id}/kb_entries`
- **模型**：`KBEntryCreate/Update/Response`。
- **特点**：创建/更新/删除后异步触发嵌入生成与向量删除任务（`asyncio.create_task`）。【F:app/api/routes/kb_entries.py†L18-L67】
- **错误**：`404 trip_not_found/entry_not_found`、`401` 未授权。

### 9.2 知识库向量检索
- **路径**：`POST /api/kb/search`、`GET /api/kb/search`
- **请求体**：
  | 字段 | 类型 | 必填 | 说明 |
  | --- | --- | --- | --- |
  | query | string | 是 | 检索查询 |
  | top_k | int | 否 | 默认 10 |
  | rerank | bool | 否 | 是否启用重排 |
  | filters | object | 否 | 字段匹配或数组匹配 |
- **响应**：`data` 数组，包含 `id/title/similarity`；若嵌入或 Qdrant 不可用，`msg` 返回 `embedding_disabled` 或 `kb_unavailable`。【F:app/api/routes/kb_vector.py†L88-L170】
- **错误**：`429 rate_limited`、`400 invalid_filters`。
- **缓存**：检索结果缓存 30 秒，命中缓存直接返回。【F:app/api/routes/kb_vector.py†L44-L87】
- **健康检查**：`GET /api/kb/health` 返回 Qdrant、嵌入、Redis 状态。【F:app/api/routes/kb_vector.py†L73-L87】

## 10. 用户标签
- **路径前缀**：`/api/user_tags`
- **模型**：`UserTagCreate/Update/Upsert/Response`。【F:app/api/routes/user_tags.py†L1-L71】【F:app/schemas/tag_schemas.py†L1-L60】
- **操作**：创建、查询（支持 `tag`、`source_trip_id`、`limit/offset`）、更新、删除、批量 UPSERT。
- **错误**：`404 tag_not_found`（服务层抛出），输入非法时返回 `422`。
- **示例**：`tests/test_user_tags.py`。【F:tests/test_user_tags.py†L1-L120】

## 11. 系统运维
### 11.1 日志级别调整
- **方法**：`PATCH /api/system/log-level`
- **请求体**：`{ "level": "debug|info|warning|error|critical" }`
- **响应**：返回更新后的级别；非法级别返回 `code=400`、`data.accepted` 列举合法值。【F:app/api/routes/system.py†L1-L24】

## 12. 审计日志
- **路径**：`GET /api/audit-logs`
- **权限**：需要管理员（`user.meta.is_admin=true`）。
- **参数**：`limit`(1-500)、`offset`、`user_id`、`trip_id`。
- **响应**：审计日志数组（`id/user_id/trip_id/action/detail/created_at`）。【F:app/api/routes/audit_logs.py†L1-L27】【F:app/schemas/audit.py†L1-L38】

## 13. 智能体接口（参考）
> 智能体模块仍在扩展中，以下接口涉及 LLM 调用与实时流式输出，使用时请确认部署环境已配置相应模型和权限。【F:app/api/routes/agent.py†L1-L116】

### 13.1 同步对话
- **方法**：`POST /api/agent/chat`
- **请求体**：
  | 字段 | 类型 | 必填 | 说明 |
  | --- | --- | --- | --- |
  | trip_id | int | 是 | 行程 ID |
  | stage | string | 是 | 所属阶段 |
  | message | string | 是 | 用户消息 |
  | client_ctx | object | 否 | 终端上下文 |
- **响应**：`data.conversation` 为保存的用户消息元数据，`data.agent` 为编排器返回的回答结构。【F:app/api/routes/agent.py†L17-L60】

### 13.2 SSE 流式对话
- **方法**：`POST /api/agent/chat/stream`
- **说明**：以 `text/event-stream` 返回事件流，每个事件包含 `event/id/data`，`data` 为 `AgentEvent` JSON。【F:app/api/routes/agent.py†L62-L104】【F:app/schemas/agent_schemas.py†L1-L72】

### 13.3 WebSocket 对话
- **路径**：`GET /api/agent/ws/chat?token=<JWT>` 或在头部传 `Authorization: Bearer <JWT>`。
- **握手消息**：首次消息需包含 `{trip_id, stage, message, client_ctx?}`。
- **关闭码**：
  - `4401`：鉴权失败。
  - `4400`：握手消息格式错误。
  - `1000`：正常关闭。【F:app/api/routes/agent.py†L106-L176】

## 14. 标准错误码汇总
| 错误码/描述 | 出现场景 |
| --- | --- |
| `invalid_registration_payload` | 注册缺失字段【F:app/api/routes/auth.py†L24-L33】 |
| `user_already_exists` | 注册重复【F:app/services/user_service.py†L19-L37】 |
| `invalid_login_payload` / `invalid_credentials` | 登录校验失败【F:app/api/routes/auth.py†L36-L52】 |
| `trip_not_found` | 行程/任务/报告等所属实体不存在【F:app/api/routes/trips.py†L74-L147】【F:app/services/report_service.py†L1-L84】 |
| `invalid_stage` / `invalid_status` / `invalid_transition` | 行程阶段或状态非法【F:app/api/routes/trips.py†L109-L176】 |
| `task_not_found` | 任务不存在【F:app/services/task_service.py†L56-L112】 |
| `invalid_base64` / `storage_error` / `file_missing` | 报告上传/存储失败【F:app/api/routes/reports.py†L22-L124】 |
| `rate_limited` | 知识库检索超过速率限制【F:app/api/routes/kb_vector.py†L88-L119】 |
| `invalid_filters` | GET 搜索 filters 解析失败【F:app/api/routes/kb_vector.py†L130-L143】 |
| `admin_required` | 非管理员访问审计日志【F:app/api/deps.py†L37-L45】 |

## 15. 示例调用流程
1. 注册并登录获取 JWT。
2. 调用 `/api/trips` 创建行程并保存 `trip_id`。
3. 根据业务需要调用任务、日程、知识库、报告等接口。
4. 若需要与智能体交互，使用相同 JWT 调用 `/api/agent/*` 系列接口。

> 如需补充新的接口，请按照以上格式提供路径、参数、响应和错误说明，并更新标准错误码表。
