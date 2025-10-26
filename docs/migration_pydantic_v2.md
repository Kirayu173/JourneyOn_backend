# Pydantic v2 迁移说明（from_orm → model_validate）

本次迁移目标：将项目中所有使用 `from_orm` 的位置迁移到 Pydantic v2 的 `model_validate`，并确保响应模型开启 `from_attributes` 以支持从 ORM/属性对象进行转换。同时保证行为与接口响应结构不变。

## 背景与动机
- Pydantic v2 移除了 v1 的 `BaseModel.from_orm`；推荐使用 `BaseModel.model_validate(obj)` 并通过 `ConfigDict(from_attributes=True)` 来支持属性读取。
- 降低弃用警告与未来版本的破坏性变更风险。

## 迁移范围与清单
- 路由层：
  - `app/api/routes/tasks.py` → 使用 `TaskResponse.model_validate(...)`
  - `app/api/routes/itinerary_items.py` → 使用 `ItineraryItemResponse.model_validate(...)`
  - `app/api/routes/conversations.py` → 使用 `ConversationResponse.model_validate(...)`
- 模型层：
  - `app/schemas/task_schemas.py` → `TaskResponse` 配置 `model_config = ConfigDict(from_attributes=True)`
  - `app/schemas/itinerary_schemas.py` → `ItineraryItemResponse` 配置 `model_config = ConfigDict(from_attributes=True)`
  - `app/schemas/conversation_schemas.py` → `ConversationResponse` 配置 `model_config = ConfigDict(from_attributes=True)`；字段 `created_at: Optional[datetime]`

## 具体变更
- 将 `XxxResponse.from_orm(obj)` 替换为 `XxxResponse.model_validate(obj)`（Xxx ∈ {Task, ItineraryItem, Conversation}）。
- 为响应模型添加：
  ```python
  from pydantic import ConfigDict
  class XxxResponse(BaseModel):
      # ... fields ...
      model_config = ConfigDict(from_attributes=True)
  ```
- 会话模型时间字段类型与 ORM 对齐：`created_at: Optional[datetime]`。

## 行为一致性说明
- API 返回的 Envelope 结构保持不变：`{"code": 0, "msg": "ok", "data": ...}`。
- 列表接口返回的数据结构与字段不变，仅内部转换方式更换为 v2 推荐方式。

## 测试与验证
- 新增测试：`tests/test_model_validate_migration.py`
  - 验证 `TaskResponse.model_validate` 能从属性对象生成有效数据
  - 验证 `ItineraryItemResponse.model_validate` 能从属性对象生成有效数据
  - 验证 `ConversationResponse.model_validate` 能从属性对象生成有效数据
- 全量测试通过（含若干第三方库的 DeprecationWarning，不影响功能）：
  - `pytest -q` 绿灯。

## 已知告警与后续建议
- Pydantic 提示 `GenericModel` 迁移（用于 Envelope）：v2 建议使用 `BaseModel` 搭配 `Generic`。当前仍可用，后续可按需迁移。
- `python-jose` 使用 `datetime.utcnow()` 的弃用提示：源于第三方库，暂不影响功能；如需消除告警需等待上游修复或替换库。

## 回滚与兼容
- 若需回滚，可将 `model_validate` 恢复为 `from_orm` 并在模型中改回 `Config.orm_mode = True`（不建议）。
- 当前版本以 v2 为基准，功能及响应保持一致，无需前端改动。