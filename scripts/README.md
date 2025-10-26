# JourneyOn 数据库脚本

本目录提供 PostgreSQL 数据库的建库与建表脚本，以及使用 SQLAlchemy 的 Python 辅助脚本。默认与项目配置 `DATABASE_URL` 保持一致：

```
postgresql+psycopg2://app:secret@localhost:5432/journeyon
```

## 前置条件
- 已安装并启动 PostgreSQL（本地或远程）。
- 已安装 `psql` 命令行工具并在 PATH 中可用。
- 如使用 Python 辅助脚本，确保安装依赖：
  - `pip install psycopg2-binary sqlalchemy pydantic-settings`

## 建库与建表流程（SQL 方式）
1. 以超级用户执行角色与数据库创建：
   - Windows PowerShell：
     ```powershell
     psql -U postgres -h localhost -f scripts/01_create_database.sql
     ```
   - Linux/macOS：
     ```bash
     psql -U postgres -h localhost -f scripts/01_create_database.sql
     ```

2. 切换到刚创建的数据库，创建枚举类型：
   ```bash
   psql -U app -h localhost -d journeyon -f scripts/02_create_types.sql
   ```

3. 创建所有业务表：
   ```bash
   psql -U app -h localhost -d journeyon -f scripts/03_create_tables.sql
   ```

> 注：`02_create_types.sql` 中定义的 `trip_stage_enum` 与 ORM 中 `Enum(TripStageEnum, name="trip_stage_enum")` 保持一致。

## 建表流程（Python 方式）
该方式通过 SQLAlchemy 元数据自动创建所有表。数据库需已存在。

1. 确认 `.env` 或环境变量中 `DATABASE_URL` 正确（默认使用上述连接串）。
2. 在项目根目录执行：
   ```bash
   python scripts/create_tables.py
   ```
3. 看到 `All tables created successfully.` 即创建完成。

## 验证
- 使用 `psql` 检查：
  ```bash
  psql -U app -h localhost -d journeyon -c "\dt"
  psql -U app -h localhost -d journeyon -c "\d+ users"
  ```

## 常见问题
- 权限问题：确保执行 `01_create_database.sql` 时使用具有创建角色/数据库权限的用户（如 `postgres`）。
- 连接失败：检查 PostgreSQL 是否启动、端口是否为 `5432`、凭据是否与脚本一致。
- Windows 提示找不到 `psql`：将 PostgreSQL 安装目录下的 `bin` 添加到系统 PATH。

## 设计对齐说明
- `users.email` 设置为 `NOT NULL` 且唯一，并建立索引。
- `trips.current_stage` 使用 PostgreSQL `trip_stage_enum`。
- `tasks.priority` 为 `INTEGER DEFAULT 1`。
- `preferences`、`agent_context`、`meta` 使用 `JSONB`，默认空对象或可空。
- 约束与关系与 ORM 模型一致（外键、级联规则、唯一约束）。