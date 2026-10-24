"""Stores proof photos (handover / purchase / delivery) as re-encoded JPEGs with metadata stripped."""

import io
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings

UPLOAD_ROOT = Path(settings.upload_dir)


async def read_limited(upload: UploadFile) -> bytes:
    limit = settings.max_upload_mb * 1024 * 1024
    data = await upload.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"File larger than {settings.max_upload_mb} MB")
    if not data:
        raise HTTPException(400, "Empty file")
    return data


async def save_photo(upload: UploadFile, prefix: str) -> str:
    data = await read_limited(upload)
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(400, "Please upload a valid image")
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((1600, 1600))
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    name = f"{prefix}-{uuid.uuid4().hex}.jpg"
    img.save(UPLOAD_ROOT / name, "JPEG", quality=85)
    return name


def public_url(name: str | None) -> str | None:
    return f"/uploads/{name}" if name else None
