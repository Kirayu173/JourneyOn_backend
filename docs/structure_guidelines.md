# 项目文件整理规范（模块化与命名约定）

## 目录结构（模块划分）
- `app/`
  - `api/`
    - `routes/` 按业务模块拆分路由文件（`auth.py`, `trips.py`, `tasks.py`, `itinerary_items.py`, `conversations.py`, `agent.py`, `health.py`）
    - `deps.py` 统一依赖（如 `get_current_user`）
  - `core/` 核心配置与安全（`config.py`, `security.py`, `logging.py`）
  - `db/` ORM 与会话（`models.py`, `session.py`）
  - `schemas/` Pydantic 模型（`common.py`, `task_schemas.py`, `itinerary_schemas.py`, `conversation_schemas.py`）
  - `services/` 业务服务层（`trip_service.py`, `task_service.py`, `itinerary_service.py`, `conversation_service.py`, `user_service.py`）
  - `agents/` 智能体编排（`orchestrator.py`，后续可加 `prompts.py`、`llm/`）
  - `middleware/` 中间件与异常（`errors.py`）
  - `providers/` 外部服务与工具封装（如 `mock_tools.py`）
- `tests/` 测试用例与夹具
- `scripts/` 数据库脚本与辅助工具
- `docs/` 文档（接口、迁移、结构规范）

## 命名规范
- 模块与文件：使用小写下划线风格（如 `task_service.py`）。
- 类名：首字母大写驼峰（如 `TaskResponse`）。
- 函数与变量：小写下划线（如 `create_item`, `get_items`）。
- 路由前缀：以资源命名，必要时嵌套层级（如 `/trips/{trip_id}/tasks`）。
- 响应包：统一使用 `Envelope[T]` 泛型形式。

## 代码组织原则
- 路由层仅做参数校验与调用服务层，模型转换使用 `model_validate`。
- 服务层负责业务逻辑与归属校验（如 `trip_not_found`）。
- 模型层仅定义数据结构与验证规则，不含业务逻辑。
- 中间件统一异常输出，保证错误响应结构一致。

## 清理与冗余处理
- 移除未引用的模块与函数；避免在路由层书写大量业务逻辑。
- 合并重复工具函数至 `providers/` 或 `services/` 下统一管理。
- 对临时或模拟逻辑（如 `orchestrator` 的 mock 调用）保留明确注释与后续替换计划。

## 导入路径更新建议
- 跨模块引用优先使用绝对导入（如 `from app.services.task_service import create_task`）。
- 路由中引用响应模型只从 `schemas/` 获取，避免循环依赖。
- 若有文件移动，统一在一次 PR 中完成并更新所有导入；提交前运行 `pytest -q` 验证。

## 后续改进建议
- Envelope 迁移到 Pydantic v2 的 BaseModel-Generic 方案以消除 GenericModel 告警。
- 为 `core/config.py` 添加类型注解与 `pydantic-settings` 的更严格校验。
- 引入自动化格式化工具（`ruff`/`black`）与 CI 检查。