from fastapi import APIRouter
from app.routers.auth import router as auth_router
from app.routers.vehicles import router as vehicles_router
from app.routers.routes import router as routes_router
from app.routers.monitoring import router as monitoring_router
from app.routers.accidents import router as accidents_router
from app.routers.completion import router as completion_router
from app.routers.devices import router as devices_router
from app.routers.data import router as data_router
from app.routers.reports import router as reports_router
from app.routers.companies import router as companies_router
from app.routers.maintenance import router as maintenance_router

api_router = APIRouter(prefix="/api")

api_router.include_router(auth_router, prefix="/auth", tags=["认证管理"])
api_router.include_router(vehicles_router, prefix="/vehicles", tags=["测试车辆管理"])
api_router.include_router(routes_router, prefix="/routes", tags=["测试路线管理"])
api_router.include_router(monitoring_router, prefix="/monitoring", tags=["实时监控与告警"])
api_router.include_router(accidents_router, prefix="/accidents", tags=["事故处理"])
api_router.include_router(completion_router, prefix="/completion", tags=["测试结题管理"])
api_router.include_router(devices_router, prefix="/devices", tags=["路侧设备管理"])
api_router.include_router(data_router, prefix="/data", tags=["数据管理"])
api_router.include_router(reports_router, prefix="/reports", tags=["运营报表"])
api_router.include_router(companies_router, prefix="/companies", tags=["企业管理"])
api_router.include_router(maintenance_router, prefix="/maintenance-staff", tags=["维护人员管理"])
