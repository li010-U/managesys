"""文件存储与处理服务"""
import os
import uuid
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import UploadFile
import logging

logger = logging.getLogger("managesys.file_service")

# 允许的文件类型
ALLOWED_EXTENSIONS = {
    # 文档
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".pdf", ".txt", ".md", ".csv",
    # 图片
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".ico", ".svg",
    # 压缩包
    ".zip", ".rar", ".7z", ".tar", ".gz",
    # 其他
    ".json", ".xml", ".yaml", ".yml",
}

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB


class FileService:
    """文件存储服务"""

    def __init__(self, upload_dir: str = None):
        self.upload_dir = Path(upload_dir or "data/uploads")
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def _get_date_path(self) -> str:
        """按日期分类存储"""
        now = datetime.now()
        return f"{now.year}/{now.month:02d}"

    def _generate_filename(self, original: str) -> tuple[str, str]:
        """生成唯一文件名，返回 (safe_name, ext)"""
        ext = Path(original).suffix.lower()
        safe_name = f"{uuid.uuid4().hex}{ext}"
        return safe_name, ext

    async def save_upload(self, file: UploadFile, sub_dir: str = "") -> dict:
        """保存上传文件，返回文件信息"""
        # 验证扩展名
        ext = Path(file.filename or "unknown").suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(f"不支持的文件类型: {ext}")

        # 验证文件大小（读取内容后检查）
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise ValueError(f"文件过大，最大支持 {MAX_FILE_SIZE // 1024 // 1024}MB")

        # 生成存储路径
        date_path = self._get_date_path()
        safe_name, ext = self._generate_filename(file.filename or "file")
        relative_path = f"{sub_dir}/{date_path}/{safe_name}" if sub_dir else f"{date_path}/{safe_name}"
        full_path = self.upload_dir / relative_path

        # 确保目录存在
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # 写入文件
        with open(full_path, "wb") as f:
            f.write(content)

        file_info = {
            "original_name": file.filename,
            "stored_name": safe_name,
            "relative_path": relative_path.replace("\\", "/"),
            "absolute_path": str(full_path.resolve()),
            "size": len(content),
            "size_display": self._format_size(len(content)),
            "extension": ext,
            "mime_type": file.content_type,
        }

        logger.info("文件已保存: %s (%s)", file.filename, file_info["size_display"])
        return file_info

    async def save_avatar(self, file: UploadFile, user_id: int) -> dict:
        """保存用户头像"""
        ext = Path(file.filename or "image.png").suffix.lower()
        if ext not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
            raise ValueError("头像仅支持图片格式(jpg/png/gif/webp)")

        content = await file.read()
        if len(content) > 5 * 1024 * 1024:  # 5MB
            raise ValueError("头像文件不能超过5MB")

        safe_name = f"avatar_{user_id}{ext}"
        relative_path = f"avatars/{safe_name}"
        full_path = self.upload_dir / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        with open(full_path, "wb") as f:
            f.write(content)

        return {
            "url": f"/api/v1/files/avatars/{safe_name}",
            "path": relative_path.replace("\\", "/"),
        }

    def get_file_path(self, relative_path: str) -> Optional[Path]:
        """根据相对路径获取完整路径"""
        full_path = self.upload_dir / relative_path
        return full_path if full_path.exists() else None

    def delete_file(self, relative_path: str) -> bool:
        """删除文件"""
        full_path = self.upload_dir / relative_path
        if full_path.exists():
            full_path.unlink()
            logger.info("文件已删除: %s", relative_path)
            return True
        return False

    @staticmethod
    def _format_size(size: int) -> str:
        if size < 1024:
            return f"{size}B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f}KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / 1024 / 1024:.1f}MB"
        return f"{size / 1024 / 1024 / 1024:.1f}GB"


# 全局单例
file_service = FileService()
