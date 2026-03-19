import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.metrics import QUOTA_EXCEEDED
from app.models.user import User

logger = structlog.get_logger()


class QuotaService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def check(self, user: User, file_size: int):
        if user.used_bytes + file_size > user.quota_bytes:
            QUOTA_EXCEEDED.inc()
            logger.warning(
                "quota.exceeded",
                user_id=user.id,
                used_bytes=user.used_bytes,
                quota_bytes=user.quota_bytes,
                requested_bytes=file_size,
            )
            raise ValueError(
                f"Quota exceeded. Used: {user.used_bytes}, "
                f"Quota: {user.quota_bytes}, "
                f"Requested: {file_size}"
            )

    async def add(self, user: User, size: int):
        user.used_bytes += size
        await self.db.commit()

    async def subtract(self, user: User, size: int):
        user.used_bytes = max(0, user.used_bytes - size)
        await self.db.commit()
