"""认证服务单元测试 - 验证密码修改审计日志"""
import pytest
from datetime import datetime, timezone

from app.services.auth_service import AuthService, validate_password_strength
from app.schemas.auth import RegisterRequest


class TestPasswordValidation:
    """测试密码强度验证"""
    
    def test_valid_password(self):
        """测试有效密码"""
        valid, msg = validate_password_strength("Password123")
        assert valid is True
        assert msg == ""
    
    def test_password_too_short(self):
        """测试密码太短"""
        valid, msg = validate_password_strength("Pass1")
        assert valid is False
        assert "8位" in msg
    
    def test_password_no_letter(self):
        """测试密码无字母"""
        valid, msg = validate_password_strength("12345678")
        assert valid is False
        assert "字母" in msg
    
    def test_password_no_digit(self):
        """测试密码无数字"""
        valid, msg = validate_password_strength("abcdefgh")
        assert valid is False
        assert "数字" in msg


class TestAuthServiceRegister:
    """测试用户注册"""
    
    @pytest.mark.asyncio
    async def test_register_creates_user(self, db_session):
        """测试注册创建用户"""
        service = AuthService(db_session)
        req = RegisterRequest(
            username="new_user",
            password="Test1234",
            real_name="新用户",
            email="new@example.com",
        )
        
        user = await service.register(req)
        await db_session.commit()
        
        assert user is not None
        assert user.username == "new_user"
        assert user.real_name == "新用户"
        assert user.email == "new@example.com"
        assert user.is_active is True


class TestAuthServiceLogin:
    """测试用户登录"""
    
    @pytest.mark.asyncio
    async def test_login_success(self, db_session):
        """测试登录成功"""
        # 先注册
        service = AuthService(db_session)
        req = RegisterRequest(
            username="login_test_user",
            password="Test1234",
        )
        await service.register(req)
        await db_session.commit()
        
        # 登录
        token, user = await service.login("login_test_user", "Test1234", "127.0.0.1")
        
        assert token is not None
        assert user.username == "login_test_user"
    
    @pytest.mark.asyncio
    async def test_login_wrong_password(self, db_session):
        """测试密码错误"""
        service = AuthService(db_session)
        req = RegisterRequest(username="wrong_pass_user", password="Test1234")
        await service.register(req)
        await db_session.commit()
        
        with pytest.raises(ValueError) as exc_info:
            await service.login("wrong_pass_user", "WrongPassword123", "127.0.0.1")
        
        assert "错误" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, db_session):
        """测试用户不存在"""
        service = AuthService(db_session)
        
        with pytest.raises(ValueError) as exc_info:
            await service.login("nonexistent", "Test1234", "127.0.0.1")
        
        assert "错误" in str(exc_info.value)


class TestCaptchaService:
    """测试验证码服务"""
    
    def test_generate_captcha_returns_valid_data(self):
        """测试生成验证码返回有效数据"""
        from app.services.captcha_service import generate_captcha
        
        captcha_id, code, img_bytes = generate_captcha()
        
        assert captcha_id is not None
        assert len(captcha_id) > 0
        assert code is not None
        assert len(code) == 4
        assert img_bytes is not None
        assert len(img_bytes) > 0
    
    def test_verify_captcha_success(self):
        """测试验证码验证成功"""
        from app.services.captcha_service import generate_captcha, verify_captcha
        
        captcha_id, code, _ = generate_captcha()
        result = verify_captcha(captcha_id, code)
        
        assert result is True
    
    def test_verify_captcha_wrong_code(self):
        """测试验证码错误"""
        from app.services.captcha_service import generate_captcha, verify_captcha
        
        captcha_id, _, _ = generate_captcha()
        result = verify_captcha(captcha_id, "9999")
        
        assert result is False
    
    def test_verify_captcha_invalid_id(self):
        """测试无效验证码ID"""
        from app.services.captcha_service import verify_captcha
        
        result = verify_captcha("invalid-id", "1234")
        
        assert result is False
