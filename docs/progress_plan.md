# 项目进度与下一阶段计划（依据设计文档）

## 当前进度概览

- **核心接口完成度高**：按照《阶段性开发计划_调整后.md》的阶段一、阶段二目标，认证、行程、任务、行程项、会话等 CRUD 接口全部上线，并通过 `pytest` 自动化测试覆盖主要业务流程。
- **知识库与向量检索**：根据《后端设计方案.md》第 7 章要求，已实现 KB 条目的增删改查、向量检索端点 `/api/kb/search`，并加入 Redis 缓存与限流机制，为后续多实例部署打好基础。
- **文件存储与报告管理**：结合《后端设计方案.md》中对文件存储模块的描述，实现本地文件存储抽象、报告模型与 CRUD API，可为 Post-trip Agent 生成 PDF/图片报告做好准备。
- **审计日志闭环**：`audit_logs` 表、统一 `log_action` 服务与管理员查询端点 `/api/audit-logs` 均已就绪，关键业务写操作均记录审计轨迹，满足《后端设计方案.md》第 12 章的安全与合规要求。
- **可配置化 Embedding Provider**：Embedding 服务支持 Ollama 与 OpenAI 切换，健康检查汇报状态，为将来的模型策略扩展铺路。

## 待完善 / 风险点

- **LangGraph 智能体编排尚未落地**：当前 `/api/agent/chat` 仍为 Mock，尚未接入设计文档中“伪多智能体”流程，也未实现工具调用（天气、酒店等）。
- **会话上下文缓存**：虽然已引入 Redis 包装，但对话上下文及阶段性记忆尚未完整接入缓存层，与《后端设计方案.md》提出的“缓存会话上下文”仍有差距。
- **WebSocket 实时推送**：设计文档要求支持流式对话，目前后端仅提供 REST 接口，缺少 WebSocket 服务与前端协议定义。
- **监控与运维**：尚未实现 Prometheus 指标、结构化日志外的监控告警，部署流程仍停留在 docker-compose 草案阶段。

## 下一阶段详细计划

1. **完成阶段三目标：Mock 工具与智能体编排**（参考《阶段性开发计划_调整后.md》阶段三）：
   - 实现 `app/providers/mock_tools.py`，补齐天气、酒店、航班、POI 模拟接口。
   - 将 `app/agents/orchestrator.py` 接入 FastAPI 服务，至少完成同步版 LangGraph 流程，能按阶段调用不同 Mock 工具并写入对话历史。
   - 扩展 `/api/agent/chat` 请求/响应结构，携带工具调用结果与后续任务建议。

2. **引入 WebSocket 与流式对话支持**（《后端设计方案.md》1.3 节）：
   - 基于 FastAPI WebSocket/Starlette，实现 `/ws/agent` 连接，与 REST 保持一致的鉴权与请求 ID。
   - 规划消息协议（start/partial/final），并在 Mock 阶段返回分段响应，方便前端联调。

3. **完善缓存与会话状态管理**：
   - 将对话历史与阶段上下文同步到 Redis，设计键结构（如 `conversation:{trip_id}`）。
   - 为高频读取接口（行程详情、任务列表）增加只读缓存策略，结合失效策略与审计日志保持一致性。

4. **向量管线与异步任务**：
   - 按《后端设计方案.md》第 7 章建议，引入后台任务（Celery/RQ 或 FastAPI BackgroundTasks），在创建 KB 条目时异步写入 Qdrant，支持批量向量化与重试机制。
   - 扩展 `/api/kb/search` rerank 流程，当配置了 `OLLAMA_RERANK_MODEL` 或 OpenAI ReRank 时调用真实模型。

5. **运维与监控体系**：
   - 增加 Prometheus 指标导出端点（请求计数、错误率、依赖服务健康等）。
   - 在 docker-compose 中补齐 Redis、Qdrant、MinIO 依赖的默认配置，编写部署手册与健康检查脚本。
   - 考虑引入 Sentry/OpenTelemetry，满足《后端设计方案.md》第 12 章的监控要求。

6. **安全与多租户增强**：
   - 审计日志查询增加分页游标与时间范围过滤。
   - 在《技术选型方案.md》建议下，评估 JWT 刷新机制与密码找回流程。

按以上计划推进，可在保持现有 API 稳定性的同时，逐步实现设计文档中关于智能体、多模态报告与高可用部署的目标。
