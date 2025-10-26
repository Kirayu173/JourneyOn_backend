# JourneyOn 后端接口文档（2025-10 更新）

本文档整理当前版本（`0.1.0`）已实现的 REST 接口，涵盖认证、行程、任务、行程项、对话、知识库、向量检索、文件报告、用户标签、系统控制与审计日志模块。除健康检查等公开接口外，所有业务接口均需在请求头携带 `Authorization: Bearer <token>`。

## 概述

JourneyOn 是一个智能旅行规划系统，提供完整的旅行规划、知识库管理、智能对话等功能。

**基础信息**
- **API 根路径**: `/api`
- **认证方式**: JWT Bearer Token
- **响应格式**: 统一使用 `Envelope` 包装格式

## 统一响应 Envelope

- 格式：`{"code": <int>, "msg": <str>, "data": <any>}`。
- 成功：`code = 0`，`msg = "ok"`，`data` 为业务数据。
- 失败：抛出 `HTTPException` 后由统一异常处理中间件包装，`code` 为 HTTP 状态码（如 `400`/`401`/`403`/`404`/`429`/`500`），`msg` 为错误标识，`data` 为空或附带错误详情。
- 所有响应均带 `X-Request-ID` 头，便于日志追踪。客户端可自定义该值。

## 认证接口（Auth）

### 用户注册

**POST** `/api/auth/register`

注册新用户并返回JWT令牌。

**请求体**:
```json
{
  "username": "string",
  "email": "string", 
  "password": "string"
}
```

**响应**:
```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "user": {
      "id": 1,
      "username": "string",
      "email": "string"
    },
    "token": "jwt_token_string"
  }
}
```

### 用户登录

**POST** `/api/auth/login`

使用用户名/邮箱和密码登录，返回JWT令牌。

**请求体**:
```json
{
  "username_or_email": "string",
  "password": "string"
}
```

**响应**: 同注册接口

## 健康检查接口（Health）

### 系统健康检查

**GET** `/api/health`

检查系统各组件健康状态（数据库、Redis、Qdrant）。

**响应**:
```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "db": true,
    "redis": true,
    "qdrant": true
  }
}
```

### 知识库健康检查

**GET** `/api/kb/health`

检查向量知识库服务状态（Qdrant集合、Embedding服务、Redis缓存）。

**响应**:
```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "qdrant": true,
    "embedding": {
      "provider": "ollama",
      "ok": true
    },
    "redis": true
  }
}
```

## 旅行管理接口（Trips）

### 创建旅行

**POST** `/api/trips`

创建新的旅行计划。

**请求体**:
```json
{
  "title": "string",
  "origin": "string",
  "origin_lat": 0.0,
  "origin_lng": 0.0,
  "destination": "string",
  "destination_lat": 0.0,
  "destination_lng": 0.0,
  "start_date": "2024-01-01",
  "duration_days": 7,
  "budget": 5000.0,
  "currency": "CNY",
  "preferences": {},
  "agent_context": {}
}
```

### 获取用户旅行列表

**GET** `/api/trips`

获取当前用户的所有旅行列表。

**响应**:
```json
{
  "code": 0,
  "msg": "ok",
  "data": [
    {
      "id": 1,
      "title": "string",
      "destination": "string",
      "start_date": "2024-01-01",
      "current_stage": "planning",
      "status": "active"
    }
  ]
}
```

### 获取旅行详情

**GET** `/api/trips/{trip_id}`

获取指定旅行的详细信息。

### 更新旅行阶段

**PATCH** `/api/trips/{trip_id}/stage`

更新旅行的当前阶段。

**请求体**:
```json
{
  "new_stage": "planning"
}
```

### 更新阶段状态

**PATCH** `/api/trips/{trip_id}/stages/{stage_name}`

更新特定阶段的状态。

**请求体**:
```json
{
  "new_status": "completed"
}
```

**错误约定**: 行程不存在返回 `404 trip_not_found`，无权访问返回 `403`。

## 任务管理接口（Tasks）

### 创建任务

**POST** `/api/trips/{trip_id}/tasks`

为旅行创建任务。

**请求体**:
```json
{
  "stage": "planning",
  "title": "预订机票",
  "description": "预订北京往返机票",
  "priority": "high",
  "assigned_to": "user@example.com",
  "due_date": "2024-01-15",
  "meta": {}
}
```

### 获取任务列表

**GET** `/api/trips/{trip_id}/tasks`

获取旅行的任务列表。

**查询参数**:
- `stage`: 按阶段过滤

### 更新任务

**PATCH** `/api/trips/{trip_id}/tasks/{task_id}`

更新指定的任务。

### 删除任务

**DELETE** `/api/trips/{trip_id}/tasks/{task_id}`

删除指定的任务。

## 行程管理接口（Itinerary Items）

### 创建行程项

**POST** `/api/trips/{trip_id}/itinerary`

为旅行创建行程安排项。

**请求体**:
```json
{
  "day": 1,
  "start_time": "09:00",
  "end_time": "12:00",
  "kind": "sightseeing",
  "title": "故宫参观",
  "location": "北京市东城区",
  "lat": 39.9163,
  "lng": 116.3972,
  "details": "参观故宫博物院"
}
```

### 获取行程项列表

**GET** `/api/trips/{trip_id}/itinerary`

获取旅行的行程安排列表。

**查询参数**:
- `day`: 按天数过滤

### 更新行程项

**PATCH** `/api/trips/{trip_id}/itinerary/{item_id}`

更新指定的行程项。

### 删除行程项

**DELETE** `/api/trips/{trip_id}/itinerary/{item_id}`

删除指定的行程项。

## 对话历史接口（Conversations）

### 获取对话历史

**GET** `/api/trips/{trip_id}/conversations`

获取旅行的对话历史记录。

**查询参数**:
- `stage`: 按阶段过滤
- `limit`: 返回数量限制（默认20）

## 智能体对话接口（Agent）

### 同步对话

**POST** `/api/agent/chat`

与智能体进行同步对话。

**请求体**:
```json
{
  "trip_id": 1,
  "stage": "planning",
  "message": "我想去北京旅游",
  "client_ctx": {}
}
```

### 流式对话

**POST** `/api/agent/chat/stream`

与智能体进行流式对话（Server-Sent Events）。

### WebSocket 对话

**WebSocket** `/api/agent/ws/chat`

通过WebSocket与智能体进行实时对话。

**连接参数**: `token` (JWT令牌)

**消息格式**:
```json
{
  "trip_id": 1,
  "stage": "planning",
  "message": "我想去北京旅游",
  "client_ctx": {}
}
```

## 知识库管理接口（KB Entries）

### 创建知识库条目

**POST** `/api/trips/{trip_id}/kb_entries`

为指定旅行创建知识库条目。

**请求体**:
```json
{
  "source": "string",
  "title": "string",
  "content": "string",
  "meta": {}
}
```

### 获取知识库条目列表

**GET** `/api/trips/{trip_id}/kb_entries`

获取指定旅行的知识库条目列表。

**查询参数**:
- `q`: 搜索关键词
- `source`: 来源过滤
- `limit`: 分页大小（默认20）
- `offset`: 分页偏移（默认0）

### 更新知识库条目

**PATCH** `/api/trips/{trip_id}/kb_entries/{entry_id}`

更新指定的知识库条目。

### 删除知识库条目

**DELETE** `/api/trips/{trip_id}/kb_entries/{entry_id}`

删除指定的知识库条目。

## 向量知识库搜索接口（KB Vector）

### 向量搜索

**POST** `/api/kb/search`

使用向量相似度搜索知识库内容。

**请求体**:
```json
{
  "query": "搜索关键词",
  "top_k": 10,
  "rerank": false,
  "filters": {
    "trip_id": 1
  }
}
```

**GET** `/api/kb/search`

GET方式的向量搜索。

**查询参数**:
- `q`: 搜索关键词
- `top_k`: 返回结果数量（默认10）

### 知识库健康检查

**GET** `/api/kb/health`

检查向量知识库服务状态。

**说明**: 若未启用嵌入或未配置 Qdrant，接口返回 `code=0`、`data=[]` 并附带 `msg` 表明不可用，便于前端降级。

## 报告管理接口（Reports）

### 上传报告

**POST** `/api/trips/{trip_id}/reports`

为旅行上传报告文件（Base64编码）。

**请求体**:
```json
{
  "filename": "report.pdf",
  "content_type": "application/pdf",
  "data": "base64_encoded_file_content",
  "format": "pdf"
}
```

### 获取报告列表

**GET** `/api/trips/{trip_id}/reports`

获取旅行的报告列表。

### 获取报告详情

**GET** `/api/trips/{trip_id}/reports/{report_id}`

获取指定报告的详细信息。

### 下载报告文件

**GET** `/api/trips/{trip_id}/reports/{report_id}/download`

下载报告文件内容。

### 删除报告

**DELETE** `/api/trips/{trip_id}/reports/{report_id}`

删除指定的报告。

## 用户标签接口（User Tags）

### 创建用户标签

**POST** `/api/user_tags`

为用户创建个性化标签。

**请求体**:
```json
{
  "tag": "美食爱好者",
  "weight": 0.8,
  "source_trip_id": 1
}
```

### 获取用户标签列表

**GET** `/api/user_tags`

获取用户的标签列表。

**查询参数**:
- `tag`: 标签名称过滤
- `source_trip_id`: 来源旅行ID过滤
- `limit`: 分页大小（默认50）
- `offset`: 分页偏移（默认0）

### 批量更新用户标签

**POST** `/api/user_tags/bulk_upsert`

批量创建或更新用户标签。

**请求体**:
```json
[
  {
    "tag": "美食爱好者",
    "weight": 0.8,
    "source_trip_id": 1
  }
]
```

### 更新用户标签

**PATCH** `/api/user_tags/{tag_id}`

更新指定的用户标签。

### 删除用户标签

**DELETE** `/api/user_tags/{tag_id}`

删除指定的用户标签。

## 系统管理接口（System）

### 调整日志级别

**PATCH** `/api/system/log-level`

动态调整应用日志级别。

**请求体**:
```json
{
  "level": "debug"
}
```

## 审计日志接口（Audit Logs）

### 获取审计日志

**GET** `/api/audit-logs`

获取系统审计日志（需要管理员权限）。

**查询参数**:
- `limit`: 返回数量限制（默认100，最大500）
- `offset`: 分页偏移
- `user_id`: 按用户ID过滤
- `trip_id`: 按旅行ID过滤

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
