from fastapi import APIRouter
from app.api.v1.chat import router as chat_router
from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.roles import router as roles_router
from app.api.v1.upload import router as upload_router
from app.api.v1.facilities import router as facilities_router
from app.api.v1.devices import router as devices_router
from app.api.v1.sensors import router as sensors_router
from app.api.v1.alerts import router as alerts_router
from app.api.v1.systems import router as systems_router
from app.api.v1.audit_logs import router as audit_logs_router
from app.api.v1.work_orders import router as work_orders_router
from app.api.v1.inspection import router as inspection_router
from app.api.v1.data import router as data_router

router = APIRouter(prefix="/api/v1")
router.include_router(chat_router)
router.include_router(auth_router)
router.include_router(users_router)
router.include_router(roles_router)
router.include_router(upload_router)
router.include_router(facilities_router)
router.include_router(devices_router)
router.include_router(sensors_router)
router.include_router(alerts_router)
router.include_router(systems_router)
router.include_router(audit_logs_router)
router.include_router(work_orders_router)
router.include_router(inspection_router)
router.include_router(data_router)

