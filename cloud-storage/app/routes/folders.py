import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.file import File
from app.models.folder import Folder
from app.models.user import User
from app.services.storage_service import storage_service

logger = structlog.get_logger()
router = APIRouter(prefix="/folders", tags=["folders"])


class FolderCreate(BaseModel):
    name: str
    parent_id: int | None = None


class FolderResponse(BaseModel):
    id: int
    name: str
    parent_id: int | None
    created_at: str


@router.get("", response_model=list[FolderResponse])
async def list_folders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.scalars(
        select(Folder).where(Folder.owner_id == current_user.id).order_by(Folder.name)
    )
    return [
        FolderResponse(id=f.id, name=f.name, parent_id=f.parent_id, created_at=f.created_at.isoformat())
        for f in result.all()
    ]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=FolderResponse)
async def create_folder(
    body: FolderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    folder = Folder(name=body.name, owner_id=current_user.id, parent_id=body.parent_id)
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    logger.info("folder.create", user_id=current_user.id, folder_id=folder.id)
    return FolderResponse(id=folder.id, name=folder.name, parent_id=folder.parent_id, created_at=folder.created_at.isoformat())


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    folder_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    folder = await db.scalar(
        select(Folder).where(Folder.id == folder_id, Folder.owner_id == current_user.id)
    )
    if not folder:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Folder not found")

    # delete all files in folder from storage
    files = await db.scalars(select(File).where(File.folder_id == folder_id))
    for f in files.all():
        storage_service.delete(f.storage_key)

    await db.delete(folder)
    await db.commit()
    logger.info("folder.delete", user_id=current_user.id, folder_id=folder_id)
