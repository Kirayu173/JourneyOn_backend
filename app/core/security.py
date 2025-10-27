from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, cast

from passlib.context import CryptContext
from jose import JWTError, jwt

from app.core.config import settings

# 密码哈希
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """使用bcrypt对明文密码进行哈希处理。"""
    hashed = _pwd_context.hash(password)
    return cast(str, hashed)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码与存储的bcrypt哈希是否匹配。"""
    try:
        return bool(_pwd_context.verify(plain_password, hashed_password))
    except Exception:
        return False


# JWT工具
_ALGORITHM = "HS256"
_DEFAULT_EXPIRES_MINUTES = 60


def create_access_token(data: Dict[str, Any], expires_minutes: int = _DEFAULT_EXPIRES_MINUTES) -> str:
    """创建带有过期时间的JWT访问令牌。"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=_ALGORITHM)
    return cast(str, token)


def verify_token(token: str) -> Dict[str, Any]:
    """解码并验证JWT令牌，返回其载荷。

    在无效签名/过期令牌时抛出JWTError。
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[_ALGORITHM])
        return cast(Dict[str, Any], payload)
    except JWTError as e:
        # 向上冒泡由调用者处理（例如，依赖项抛出401错误）
        raise