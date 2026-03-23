import asyncio
from urllib.parse import quote

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.middleware.metrics import UPLOAD_BYTES
from app.models.file import File
from app.models.user import User
from app.services.quota_service import QuotaService
from app.services.storage_service import storage_service

logger = structlog.get_logger()
router = APIRouter(prefix="/files", tags=["files"])

MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB


class FileResponse(BaseModel):
    id: int
    name: str
    original_name: str
    content_type: str
    size_bytes: int
    folder_id: int | None
    created_at: str

    model_config = {"from_attributes": True}


class RenameRequest(BaseModel):
    name: str
    folder_id: int | None = None


@router.get("", response_model=list[FileResponse])
async def list_files(
    folder_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * limit
    q = select(File).where(File.owner_id == current_user.id)
    if folder_id is not None:
        q = q.where(File.folder_id == folder_id)
    q = q.order_by(File.created_at.desc()).offset(offset).limit(limit)
    result = await db.scalars(q)
    files = result.all()
    return [
        FileResponse(
            id=f.id,
            name=f.name,
            original_name=f.original_name,
            content_type=f.content_type,
            size_bytes=f.size_bytes,
            folder_id=f.folder_id,
            created_at=f.created_at.isoformat(),
        )
        for f in files
    ]


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile,
    folder_id: int | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await file.read()

    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large (max 500MB)")

    quota = QuotaService(db)
    try:
        quota.check(current_user, len(data))
    except ValueError as e:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))

    key = storage_service.generate_key(current_user.id, file.filename or "upload")
    storage_service.upload(key, data, file.content_type or "application/octet-stream")

    db_file = File(
        name=file.filename or "upload",
        original_name=file.filename or "upload",
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(data),
        storage_key=key,
        owner_id=current_user.id,
        folder_id=folder_id,
    )
    db.add(db_file)
    await quota.add(current_user, len(data))
    await db.commit()
    await db.refresh(db_file)

    UPLOAD_BYTES.inc(len(data))
    logger.info("file.upload", user_id=current_user.id, file_id=db_file.id, size_bytes=len(data))

    return {"id": db_file.id, "name": db_file.name, "size_bytes": db_file.size_bytes}


@router.get("/{file_id}/download")
async def download_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    file = await db.scalar(
        select(File).where(File.id == file_id, File.owner_id == current_user.id)
    )
    if not file:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="File not found")

    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, storage_service.get_object_bytes, file.storage_key)
    logger.info("file.download", user_id=current_user.id, file_id=file_id)
    encoded_name = quote(file.original_name, safe="")
    return Response(
        content=data,
        media_type=file.content_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}"},
    )


@router.get("/{file_id}/meta", response_model=FileResponse)
async def file_meta(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    file = await db.scalar(
        select(File).where(File.id == file_id, File.owner_id == current_user.id)
    )
    if not file:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="File not found")
    return FileResponse(
        id=file.id,
        name=file.name,
        original_name=file.original_name,
        content_type=file.content_type,
        size_bytes=file.size_bytes,
        folder_id=file.folder_id,
        created_at=file.created_at.isoformat(),
    )


@router.patch("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def rename_file(
    file_id: int,
    body: RenameRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    file = await db.scalar(
        select(File).where(File.id == file_id, File.owner_id == current_user.id)
    )
    if not file:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="File not found")

    file.name = body.name
    if body.folder_id is not None:
        file.folder_id = body.folder_id
    await db.commit()
    logger.info("file.rename", user_id=current_user.id, file_id=file_id, new_name=body.name)


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    file = await db.scalar(
        select(File).where(File.id == file_id, File.owner_id == current_user.id)
    )
    if not file:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="File not found")

    storage_service.delete(file.storage_key)
    size = file.size_bytes
    await db.delete(file)
    await QuotaService(db).subtract(current_user, size)
    await db.commit()
    logger.info("file.delete", user_id=current_user.id, file_id=file_id)
