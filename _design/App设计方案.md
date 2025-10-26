
### **项目名称**

**JourneyOn：基于多智能体的智能旅游APP设计与开发**

### **项目简介（中文）**

JourneyOn 是一款整合多智能体（Multi-Agent System）的智能旅游应用，旨在为用户打造一个  **“有温度与智慧”的个人旅行空间** 。

系统通过多智能体协作机制，为用户提供从 **旅行规划、行程推荐、路线导航、天气与预算提醒、旅途中交互服务** 到 **旅后回忆管理** 的全流程智能支持。

应用的核心架构基于 Python 后端与 LangGraph + LangChain 智能体框架，实现任务分工与智能协作。前端采用 **React Native + Expo** 跨平台方案，为用户提供流畅的移动端体验。JourneyOn 不仅是一个工具，更是一位随行的 AI 旅行伙伴，让每次旅程更轻松、更贴心、更智能。

# 1) 难度评估（结论先说）

* 难度： **中等偏上** （工程量大但技术难点可控）。
* 关键难点不在于“做不出来”，而在于三项：外部 API / 真正支付订票集成（法律与费用）、LLM 的一致性/幻觉（hallucination）、和数据/状态管理（保证每个行程的状态准确）。
* 适合作为本科毕设：如果你把范围限定为“ **以建议/模拟预订为主** （即不直接在系统里完成真实支付/出票）”，并且把知识库与向量检索做成可迭代模块，这个项目非常有展示力且能在有限时间内完成。

# 2) MVP（必须优先实现的最小功能集合）

做到下面这些就足够做毕业设计演示与答辩：

1. 用户注册/登录 + 每个用户 **行程空间** （CRUD）。
2. 创建行程：出发地（手填或安卓位置）、目的地、出发日期、时长、预算。
3. 行程自动分为三阶段（前/中/后），每阶段有单独聊天面板（伪多智能体）。
4. **Pre-trip agent** 能帮用户生成预备任务清单（酒店/机票/证件/行李）和给出可选方案（列表 + 理由）。
5. **On-trip agent** 能响应“附近景点”、“给我推荐餐厅并生成预约步骤”、“当前行程变更建议”等对话请求。
6. **Post-trip agent** 生成旅行总结（行程回顾、费用概览、用户偏好标签）并保存到用户画像。
7. 基础知识库：将用户对话要点/确认的事项存为文本并做 embeddings（便于后续语义检索）。
8. 前端展示行程日历/单日行程和聊天面板；后端用 FastAPI（示例会给出）。

# 3) 主要风险与缓解策略（毕业设计角度）

* LLM 幻觉：所有“执行型”建议都要标记为建议，并保存来源/证据（URL或API结果）；对关键操作 require 用户确认。
* 实时/收费 API：把真实票务/hotel 功能先 mock，或只用公开查询 API（带来源），若要做支付集成则演示流程即可，不做真实支付。
* 隐私/位置：保存精确位置需谨慎；演示时可使用模糊化（城市级）或征得用户许可。

# 4) 后端：数据模型（PostgreSQL 示例 ER 关键表）

下面给出精简表，字段可按需扩展。

```sql
-- users
User(id PK, username, email, password_hash, created_at)

-- trips (每个用户可有多个行程)
Trip(id PK, user_id FK->User.id, title, origin, origin_lat, origin_lng,
     destination, start_date, duration_days, budget, current_stage ENUM('pre','on','post'),
     created_at, updated_at)

-- trip_stages (详细阶段状态与确认时间)
TripStage(id PK, trip_id FK->Trip.id, stage_name ENUM('pre','on','post'),
          status ENUM('pending','in_progress','completed'),
          assigned_agent TEXT, confirmed_at, meta JSONB)

-- itinerary_items (行程细项：景点/交通/酒店等)
ItineraryItem(id PK, trip_id FK, day INT, start_time TIME, end_time TIME,
              kind ENUM('attraction','hotel','flight','restaurant','transport'),
              title, location TEXT, lat FLOAT, lng FLOAT, details JSONB)

-- tasks (pre-trip check list items: book hotel 等)
Task(id PK, trip_id FK, stage ENUM('pre','on','post'),
     title, description, status ENUM('todo','done','skipped'), assigned_to TEXT, meta JSONB)

-- conversations (保存用户与每个 stage-agent 的会话)
Conversation(id PK, trip_id FK, stage ENUM('pre','on','post'), role ENUM('user','agent'),
             message TEXT, message_meta JSONB, created_at)

-- kb_entries (知识库：用于向量化/检索)
KBEntry(id PK, source, content TEXT, embeddings VECTOR/bytea, created_at)

-- user_profile_tags (从后期报告里抽取的偏好标签)
UserTag(id PK, user_id FK, tag TEXT, weight FLOAT, source_trip FK->Trip.id)
```

# 5) 后端 API 设计（FastAPI 风格，关键端点）

示例路由和行为，返回 JSON。

* `POST /api/trips/` — 创建新行程（body: origin, destination, start_date, duration_days, budget） → 返回 trip 对象（并自动创建三阶段记录）。
* `GET /api/trips/{trip_id}` — 获取行程与阶段、日程。
* `PATCH /api/trips/{trip_id}/stage` — 更新 stage（例如从 pre -> on，当用户确认）。
* `GET /api/trips/{trip_id}/assistant/{stage}/chat` — 拉取会话历史。
* `POST /api/trips/{trip_id}/assistant/{stage}/chat` — 向该阶段 agent 发送消息，后端调用 LLM/Orchestrator，并返回 agent 回复（同时保存对话与 embeddings）。
* `GET /api/trips/{trip_id}/tasks` — 任务清单。
* `POST /api/trips/{trip_id}/tasks/{task_id}/complete` — 标记完成。
* `GET /api/kb/search?q=...` — 知识库语义检索（向量检索）。
* `POST /api/external/search/hotels` (或 mock) — 查询酒店建议（用于 demo）。

# 6) “伪多智能体”实现方案（建议采用）📦

> 理念：不用真实并行多个模型节点，而用**单个 Orchestrator + 每阶段专用 prompt / memory /工具链**来实现“多智能体”行为（更可靠、易实现、可解释）。

实现方式（伪代码）：

```python
# 当用户发消息到某个 stage:
def handle_stage_message(trip_id, stage, user_msg):
    # 1. 取出 trip、stage meta、用户画像（profile）、kb 上下文（相关KB条目）
    context = build_context(trip_id, stage)
    # 2. 选择 stage-specific system prompt
    system_prompt = PROMPTS[stage]  # pre/on/post 各自的职责指令
    # 3. 构建 messages: system + conversation_history + user_msg + tools_outputs
    messages = [system_prompt] + load_conversation_history(...) + [user_msg]
    # 4. 调用 LLM （可以用 OpenAI 或本地模型），带上 tool-handlers（如 hotel_search, map_search）
    agent_reply, tools_called = llm_call(messages, available_tools=TOOLS[stage])
    # 5. 保存会话 & 若有确认动作，改变 TripStage 状态
    save_conversation(...)
    return agent_reply
```

### Stage-specific system prompt（示例片段）

* Pre-trip agent system prompt（简明）：
  > “你是旅行前阶段助手。职责：生成可执行的预订/准备清单（机票、酒店、签证、行李），优先给出 3 个可选方案，每个方案附上优缺点与估算花费。若给出可订购链接，请标注来源。所有建议须基于 trip 的预算与时间。输出要分条、且在建议关键操作前要求用户确认。”
  >
* On-trip agent system prompt：
  > “你是旅行进行时的随行助手。职责：根据用户位置或日程，推荐附近景点/餐厅并给出到达方式与预计时间，能实时处理突发情况（天气、延误），并给出替代方案。避免自行执行任何真实交易，所有操作要先询问确认。”
  >
* Post-trip agent:
  > “总结旅行并提取用户偏好（喜欢/不喜欢的餐厅类型、景点类型、预算适应性），输出一份旅行总结并给出 3 条将来改进建议。”
  >

# 7) 知识库与记忆（必须实现的关键点）

* 每次用户确认的“偏好/决定”都写入 KB（文本 + metadata）并做 embeddings 存入向量库（Qdrant/Chroma）。这样后续检索能个性化回答。
* 保存 trip 级别的 conversation snippets 与任务完成记录，后续 Post-trip agent 用于抽取偏好标签（如 “偏好博物馆/喜欢经济型酒店”）。

# 8) 前端主要界面与交互（关键页面）

* Dashboard（我的行程卡片） → 进入 Trip 页面。
* Trip 页面包含三栏切换（前/中/后），每栏有：
  * 左：日程 / 任务清单 / 推荐列表
  * 右：聊天面板（与 stage-agent 聊天）、快速动作按钮（如：生成预订方案、查附近、标记完成）
* 行程日历/地图视图：单日展开、地点标记、导航到第三方地图。
* 在 Pre-trip 的“预订”建议卡上，给出“复制/打开链接/标记已完成”的按钮（不直接处理支付）。

# 9) 示例：创建行程的 JSON 请求 & 后端返回（用于前端快速对接）

请求：

```json
POST /api/trips
{
  "title": "成都周末游",
  "origin": "北京",
  "destination": "成都",
  "start_date": "2025-11-20",
  "duration_days": 3,
  "budget": 1500
}
```

返回的关键字段：

```json
{
  "id": 123,
  "user_id": 1,
  "current_stage": "pre",
  "stages": [
    {"stage_name":"pre", "status":"in_progress"},
    {"stage_name":"on", "status":"pending"},
    {"stage_name":"post", "status":"pending"}
  ]
}
```

# 10) 评价指标（用于答辩里的实验/结果）

* 功能性评估：完成预订清单的正确率（人工打标签）与任务完成率。
* 用户体验（可做小规模问卷）：满意度评分（1–5）针对推荐质量与对话自然度。
* 系统日志量化：每个行程中 agent 建议命中率（用户采纳建议的比例）。
* KB 累积效果：经过多次行程后，个性化推荐的接受率是否提升（A/B 测试：有/无 KB）。

# 11) 开发建议（技术选型与实践小贴士）

* 后端：FastAPI + SQLAlchemy + Alembic；Redis 用于 session 与临时会话上下文缓存。
* 向量库：Qdrant 或 Chroma；embeddings 用 OpenAI 或开源嵌入模型（取决于成本）。
* LLM：开始时可以只接 OpenAI 的 Chat API（成本可控，便于迭代）；生产或演示可尝试本地小模型。
* Orchestration：如果你熟悉 LangGraph / LangChain，可用它编排；否则实现一个小型 orchestrator（上面的伪代码）即可。
* 前端：微信小程序或 React Native 做移动端；管理后台建议 React + Tailwind（演示用也可做成单页 React）。
* 第三方服务：地图选高德（中国），酒店/机票用公开搜索 API（用于演示）或 mock 数据。

# 12) Demo / 展示建议（答辩加分项）

* 准备 2~3 个完整的演示场景：短城际周末（预算低）、城市深度游（预算中）、长途休闲（预算高）。展示从创建行程 → pre-agent 生成方案 → 用户确认 → on-agent 实时帮找景点 → post-agent 输出总结/标签。
* 在答辩 PPT 中展示：架构图、关键数据表、一个对话示例（用户与 pre/on/post 的对话片段）、KB 如何更新的示例。
