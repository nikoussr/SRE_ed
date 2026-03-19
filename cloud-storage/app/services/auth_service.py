import structlog
from passlib.context import CryptContext
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.utils.jwt import create_access_token, create_refresh_token, decode_token

logger = structlog.get_logger()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

REFRESH_TOKEN_PREFIX = "refresh:"


class AuthService:
    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.redis = redis

    async def register(self, email: str, password: str) -> User:
        existing = await self.db.scalar(select(User).where(User.email == email))
        if existing:
            raise ValueError("Email already registered")

        user = User(
            email=email,
            hashed_password=pwd_context.hash(password),
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        logger.info("auth.register", user_id=user.id, email=email)
        return user

    async def login(self, email: str, password: str) -> tuple[str, str]:
        user = await self.db.scalar(select(User).where(User.email == email))

        if not user or not pwd_context.verify(password, user.hashed_password):
            logger.warning("auth.login_failed", email=email)
            raise ValueError("Invalid credentials")

        if not user.is_active:
            raise ValueError("Account disabled")

        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)

        # store refresh token in Redis
        from app.config import settings
        await self.redis.setex(
            f"{REFRESH_TOKEN_PREFIX}{refresh_token}",
            settings.refresh_token_expire_days * 86400,
            str(user.id),
        )

        logger.info("auth.login_success", user_id=user.id)
        return access_token, refresh_token

    async def refresh(self, refresh_token: str) -> tuple[str, str]:
        stored = await self.redis.get(f"{REFRESH_TOKEN_PREFIX}{refresh_token}")
        if not stored:
            raise ValueError("Invalid or expired refresh token")

        try:
            user_id = decode_token(refresh_token, "refresh")
        except ValueError:
            raise ValueError("Invalid refresh token")

        # rotate refresh token
        await self.redis.delete(f"{REFRESH_TOKEN_PREFIX}{refresh_token}")
        new_access = create_access_token(user_id)
        new_refresh = create_refresh_token(user_id)

        from app.config import settings
        await self.redis.setex(
            f"{REFRESH_TOKEN_PREFIX}{new_refresh}",
            settings.refresh_token_expire_days * 86400,
            str(user_id),
        )

        logger.info("auth.token_refresh", user_id=user_id)
        return new_access, new_refresh

    async def logout(self, refresh_token: str):
        await self.redis.delete(f"{REFRESH_TOKEN_PREFIX}{refresh_token}")
        logger.info("auth.logout")

    async def change_password(self, user: User, old_password: str, new_password: str):
        if not pwd_context.verify(old_password, user.hashed_password):
            raise ValueError("Wrong current password")

        user.hashed_password = pwd_context.hash(new_password)
        await self.db.commit()
        logger.info("auth.password_changed", user_id=user.id)
