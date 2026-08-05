"""模型导入 - 所有模型集中导入以使 SQLAlchemy 正确注册"""

from app.db.base import Base

# ===== 账号管理 (Week 1) =====
from app.models.user import User, user_roles
from app.models.role import Role, role_permissions
from app.models.permission import Permission
from app.models.audit_log import AuditLog
from app.models.login_log import LoginLog

# ===== 机房管理 (Week 2) =====
from app.models.facility import DataCenter, Room, Rack

# ===== 设备管理 (Week 2) =====
from app.models.device_type import DeviceType
from app.models.device import Device, DeviceLifecycle
from app.models.sensor import Sensor, SensorData

# ===== 监控告警 (Week 3) =====
from app.models.alert import AlertRule, Alert, AlertAction

# ===== 业务系统管理 (Week 3) =====
from app.models.business_system import BusinessSystem, DeploymentRelation, SystemDocument

# ===== AI 对话 (Week 4) =====
from app.models.chat import ChatConversation, ChatMessage

# ===== 工单管理 =====
from app.models.work_order import WorkOrderCategory, WorkOrder, WorkOrderComment, WorkOrderAttachment

# ===== 设备巡检 =====
from app.models.inspection import InspectionTemplate, InspectionPlan, InspectionTask, InspectionRecord, InspectionIssue

__all__ = [
    # Base
    "Base",

    # 账号管理
    "User", "user_roles",
    "Role", "role_permissions",
    "Permission",
    "AuditLog",
    "LoginLog",

    # 机房管理
    "DataCenter", "Room", "Rack",

    # 设备管理
    "DeviceType",
    "Device", "DeviceLifecycle",
    "Sensor", "SensorData",

    # 监控告警
    "AlertRule", "Alert", "AlertAction",

    # 业务系统管理
    "BusinessSystem", "DeploymentRelation", "SystemDocument",

    # AI 对话
    "ChatConversation", "ChatMessage",

    # 工单管理
    "WorkOrderCategory", "WorkOrder", "WorkOrderComment", "WorkOrderAttachment",

    # 设备巡检
    "InspectionTemplate", "InspectionPlan", "InspectionTask", "InspectionRecord", "InspectionIssue",
]
