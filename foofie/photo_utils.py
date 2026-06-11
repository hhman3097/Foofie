import os
import uuid
from PIL import Image
from fastapi import UploadFile

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
THUMBNAIL_SIZE = (300, 300)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
THUMBNAIL_DIR = os.path.join(BASE_DIR, "thumbnails")


def validate_photo(file: UploadFile) -> tuple[bool, str]:
    """验证照片格式和大小，返回 (是否合法, 错误信息)"""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"不支持的文件格式: {ext}，仅支持 jpg/png/webp"
    if file.content_type not in ALLOWED_MIME_TYPES:
        return False, f"不支持的 MIME 类型: {file.content_type}"
    return True, ""


async def save_photo(file: UploadFile) -> tuple[str, str]:
    """保存照片并生成缩略图，返回 (photo_filename, thumbnail_filename)"""
    ext = os.path.splitext(file.filename or "photo.jpg")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        ext = ".jpg"

    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise ValueError(f"文件过大，超过 5MB 限制")

    with open(filepath, "wb") as f:
        f.write(contents)

    # 生成缩略图
    thumb_filename = f"{uuid.uuid4().hex}{ext}"
    thumb_path = os.path.join(THUMBNAIL_DIR, thumb_filename)
    try:
        img = Image.open(filepath)
        img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
        img.save(thumb_path)
    except Exception as e:
        # 缩略图生成失败不影响原图保存
        print(f"Thumbnail generation failed: {e}")
        thumb_filename = ""

    return filename, thumb_filename


def delete_photo(photo_path: str, thumbnail_path: str):
    """删除照片和缩略图文件"""
    if photo_path:
        p = os.path.join(UPLOAD_DIR, photo_path)
        if os.path.exists(p):
            os.remove(p)
    if thumbnail_path:
        p = os.path.join(THUMBNAIL_DIR, thumbnail_path)
        if os.path.exists(p):
            os.remove(p)
