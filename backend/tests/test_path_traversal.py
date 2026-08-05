"""?????????????

???
- get_file_path ? .. / ??????????? None?
- delete_file ???????????? False?
- save_upload ??? sub_dir ?? ValueError?
"""
import asyncio
import os
import tempfile

import pytest

from app.services.file_service import FileService


@pytest.fixture
def fs(tmp_path):
    return FileService(str(tmp_path))


def _write(service, rel: str, data=b"x"):
    """? service ??????????????????"""
    base = service.upload_dir
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


def test_get_file_path_normal(tmp_path):
    fs = FileService(str(tmp_path))
    _write(fs, "2025/01/abc.txt")
    assert fs.get_file_path("2025/01/abc.txt") is not None


def test_get_file_path_blocks_parent_navigation(tmp_path):
    fs = FileService(str(tmp_path))
    assert fs.get_file_path("../../etc/passwd") is None
    assert fs.get_file_path("a/../../../.env") is None


def test_get_file_path_blocks_absolute(tmp_path):
    fs = FileService(str(tmp_path))
    assert fs.get_file_path("/etc/passwd") is None


def test_get_file_path_blocks_direct_escape(tmp_path):
    fs = FileService(str(tmp_path))
    # ?????????????????????????
    outside = tmp_path.parent / "secret.txt"
    outside.write_text("secret")
    # ??????????????????????
    assert fs.get_file_path("../../secret.txt") is None
    os.path.exists(outside)


def test_delete_file_blocks_navigation(tmp_path):
    fs = FileService(str(tmp_path))
    assert fs.delete_file("../../.env") is False
    assert fs.delete_file("a/../../x") is False


def test_delete_file_works_for_inside_file(tmp_path):
    fs = FileService(str(tmp_path))
    p = _write(fs, "docs/a.txt")
    assert p.exists()
    assert fs.delete_file("docs/a.txt") is True
    assert not p.exists()


def test_save_upload_rejects_malicious_subdir(tmp_path):
    fs = FileService(str(tmp_path))

    class F:
        filename = "a.txt"
        content_type = "text/plain"

        async def read(self):
            return b"hello"

    for bad in ["../evil", "a/../b", "/abs", "..", "..\\win"]:
        with pytest.raises(ValueError):
            asyncio.run(fs.save_upload(F(), bad))


def test_save_upload_accepts_safe_subdir(tmp_path):
    fs = FileService(str(tmp_path))

    class F:
        filename = "a.txt"
        content_type = "text/plain"

        async def read(self):
            return b"hello"

    info = asyncio.run(fs.save_upload(F(), "docs"))
    assert "docs/" in info["relative_path"]
    # ??????????????
    full = (fs.upload_dir / info["relative_path"]).resolve()
    assert full.is_relative_to(fs.upload_dir.resolve())
