from __future__ import annotations

import sys
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

# 确保在作为脚本运行时项目根目录在sys.path中
# 从仓库根目录运行：`python scripts/create_tables.py`

try:
    from app.core.config import settings
    from app.db.models import Base  # 导入所有模型
except Exception as import_err:
    print("导入错误：请从项目根目录运行并确保依赖已安装。", file=sys.stderr)
    raise


def main() -> None:
    url = settings.DATABASE_URL
    print(f"连接到数据库：{url}")

    engine = create_engine(url, pool_pre_ping=True)
    try:
        Base.metadata.create_all(bind=engine)
        print("所有表创建成功。")
    except SQLAlchemyError as e:
        print(f"创建表时出错：{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()