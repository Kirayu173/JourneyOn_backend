# ✅ JourneyOn 智能体框架开发任务清单（可交付 Codex）

## 🎯 总体目标
实现一个基于 **LangGraph** 的线性多智能体框架（Pre → On → Post）。  
当前任务仅构建**框架与阶段流转逻辑**，暂不实现每个阶段的内部推理逻辑。

---

## 🧱 任务结构与优先级

| 编号 | 模块路径 | 任务内容 | 优先级 | 预期产出 |
|------|-----------|-----------|----------|-----------|
| T1 | `app/agents/graph.py` | 构建主图 `AgentOrchestratorGraph`，定义阶段流转关系（Pre → On → Post）。 | ⭐⭐⭐⭐ | 线性流转 LangGraph 主图 |
| T2 | `app/agents/base_agent.py` | 编写基础智能体类 `BaseAgent`，定义标准接口（`run(context)` / `to_dict()`）。 | ⭐⭐ | 可被各阶段继承的统一基类 |
| T3 | `app/agents/pre_agent/graph.py` | 创建占位子图 `PreTripAgentGraph`（简单返回固定消息）。 | ⭐⭐⭐ | 可执行的PreTrip阶段节点 |
| T4 | `app/agents/on_agent/graph.py` | 创建占位子图 `OnTripAgentGraph`。 | ⭐⭐⭐ | 可执行的OnTrip阶段节点 |
| T5 | `app/agents/post_agent/graph.py` | 创建占位子图 `PostTripAgentGraph`。 | ⭐⭐⭐ | 可执行的PostTrip阶段节点 |
| T6 | `app/agents/orchestrator.py` | 编写 `Orchestrator` 类，实例化主图、传递上下文并执行 `.run()`。 | ⭐⭐⭐⭐ | 与API连接的执行入口 |
| T7 | `app/services/stage_service.py` | 实现阶段确认与推进函数 `advance_stage(trip_id, to_stage)`，写入数据库。 | ⭐⭐ | 可更新 `trips.current_stage` |
| T8 | `app/api/agent_routes.py` | 修改 `/api/agent/chat` 路由，接入 `Orchestrator` 并返回执行结果。 | ⭐⭐⭐⭐ | 可完整调用 LangGraph 流程 |
| T9 | `tests/test_agent_linear_flow.py` | 编写测试用例：模拟 pre→on→post 流程及用户确认逻辑。 | ⭐⭐⭐ | 确保流转正确 |
| T10 | `docs/langgraph_flow.svg` | 绘制 LangGraph 主图结构图（Pre→On→Post） | ⭐ | 图文说明，可用于文档/PPT |

---

## ⚙️ 验收标准

| 指标 | 验收条件 |
|------|-----------|
| 流程完整性 | 用户可依次通过 pre → on → post 阶段 |
| 状态控制 | `trips.current_stage` 正确更新 |
| 输出内容 | 每个阶段返回独立的 JSON 响应 |
| 扩展性 | 每个阶段子图可替换为后续复杂逻辑 |
| 测试通过 | pytest 集成测试全部通过 |

---

## ✅ 集成进度补充（Memory 层）
- mem0 集成：已完成封装（`app/services/memory_service.py`）与 REST 路由（`/api/memories/*`）。
- 环境：Docker Compose 已默认启用（`MEMORY_ENABLED=true`），矢量库为 Qdrant，嵌入走本机 Ollama。
- 一键测试：
  - 依赖连通性：`docker-compose exec -T web python scripts/check_dependencies.py --json`
  - 流式：`docker-compose exec -T web python scripts/test_streaming.py`
  - KB：`docker-compose exec -T web python scripts/integration_test.py --base http://web:8000`
  - Memory：`docker-compose exec -T web python scripts/test_memories.py`
- 文档：
  - README 增加 Memory 说明
  - `docs/智能体逻辑开发指南.md`、`docs/自定义工具开发指南.md` 增加 Memory 使用说明

---

## 📅 建议执行顺序

1. **T1–T3**（基础结构，LangGraph主图与节点）  
2. **T4–T6**（接入API与Orchestrator）  
3. **T7–T8**（状态推进逻辑）  
4. **T9–T10**（测试与文档）  

预计总开发周期：**5–7天（单人可完成）**
