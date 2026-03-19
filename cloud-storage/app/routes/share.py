import secrets
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.file import File
from app.models.user import User
from app.services.storage_service import storage_service

logger = structlog.get_logger()
router = APIRouter(prefix="/share", tags=["share"])


class ShareRequest(BaseModel):
    ttl_hours: int = 24


class ShareResponse(BaseModel):
    token: str
    expires_at: str
    url: str


@router.post("/{file_id}", response_model=ShareResponse)
async def create_share_link(
    file_id: int,
    body: ShareRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    file = await db.scalar(
        select(File).where(File.id == file_id, File.owner_id == current_user.id)
    )
    if not file:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="File not found")

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=body.ttl_hours)

    file.share_token = token
    file.share_expires_at = expires_at
    await db.commit()

    logger.info("share.created", user_id=current_user.id, file_id=file_id, ttl_hours=body.ttl_hours)
    return ShareResponse(
        token=token,
        expires_at=expires_at.isoformat(),
        url=f"/share/{token}",
    )


@router.get("/{token}")
async def download_shared_file(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    file = await db.scalar(select(File).where(File.share_token == token))

    if not file:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Link not found")

    if file.share_expires_at and datetime.now(timezone.utc) > file.share_expires_at:
        raise HTTPException(status.HTTP_410_GONE, detail="Link expired")

    logger.info("share.accessed", file_id=file.id, token=token)
    url = storage_service.get_download_url(file.storage_key)
    return RedirectResponse(url)
