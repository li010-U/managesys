"""验证码生成与验证服务"""
import io
import random
import string
import uuid
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw, ImageFont

# 简单的内存缓存（生产环境应使用Redis）
_captcha_cache: dict[str, dict] = {}
_CAPTCHA_EXPIRE_SECONDS = 300  # 5分钟


def _generate_code(length: int = 4) -> str:
    """生成随机数字验证码"""
    return ''.join(random.choices(string.digits, k=length))


def _create_captcha_image(code: str) -> bytes:
    """生成验证码图片"""
    width, height = 120, 40
    img = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    # 绘制干扰点
    for _ in range(random.randint(50, 100)):
        x = random.randint(0, width)
        y = random.randint(0, height)
        draw.point((x, y), fill=(random.randint(100, 200), random.randint(100, 200), random.randint(100, 200)))

    # 绘制干扰线
    for _ in range(random.randint(2, 4)):
        x1 = random.randint(0, width // 2)
        y1 = random.randint(0, height)
        x2 = random.randint(width // 2, width)
        y2 = random.randint(0, height)
        draw.line((x1, y1, x2, y2), fill=(random.randint(150, 220),)*3, width=1)

    # 绘制验证码文字
    font_size = 24
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except (IOError, OSError):
        font = ImageFont.load_default()

    x_offset = 10
    for char in code:
        y_offset = random.randint(2, 8)
        color = (random.randint(0, 80), random.randint(0, 80), random.randint(0, 80))
        draw.text((x_offset, y_offset), char, fill=color, font=font)
        x_offset += 25

    # 保存到 bytes
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_captcha() -> tuple[str, str, bytes]:
    """生成验证码，返回 (captcha_id, code_text, image_bytes)"""
    code = _generate_code()
    captcha_id = str(uuid.uuid4())
    img_bytes = _create_captcha_image(code)
    _captcha_cache[captcha_id] = {
        "code": code,
        "expires_at": datetime.now(timezone.utc) + timedelta(seconds=_CAPTCHA_EXPIRE_SECONDS),
    }
    return captcha_id, code, img_bytes


def verify_captcha(captcha_id: str, captcha_code: str) -> bool:
    """验证验证码"""
    if not captcha_id or not captcha_code:
        return False
    record = _captcha_cache.pop(captcha_id, None)
    if not record:
        return False
    if datetime.now(timezone.utc) > record["expires_at"]:
        return False
    return record["code"] == captcha_code
