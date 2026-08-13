"""机房管理 API 路由"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user, require_permission
from app.models.user import User
from app.services.facility_service import DataCenterService, RoomService, RackService
from app.schemas.facility import (
    DataCenterCreate, DataCenterUpdate, DataCenterResponse, DataCenterPageResponse,
    RoomCreate, RoomUpdate, RoomResponse, RoomPageResponse,
    RackCreate, RackUpdate, RackResponse, RackPageResponse,
)

router = APIRouter(prefix="/facilities", tags=["机房管理"])


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


# ==================== DataCenter ====================

@router.get("/data-centers", response_model=DataCenterPageResponse)
async def list_data_centers(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    keyword: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("room:view")),
):
    service = DataCenterService(db)
    items, total = await service.get_list(page, page_size, keyword)
    resp = []
    for dc in items:
        r = DataCenterResponse.model_validate(dc)
        r.room_count = len(dc.rooms or [])
        resp.append(r)
    return DataCenterPageResponse(items=resp, total=total, page=page, page_size=page_size)


@router.get("/data-centers/all", response_model=list[DataCenterResponse])
async def list_all_data_centers(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("room:view")),
):
    service = DataCenterService(db)
    items, _ = await service.get_list(page=1, page_size=1000)
    resp = []
    for dc in items:
        r = DataCenterResponse.model_validate(dc)
        r.room_count = len(dc.rooms or [])
        resp.append(r)
    return resp


@router.get("/data-centers/{dc_id}", response_model=DataCenterResponse)
async def get_data_center(
    dc_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("room:view")),
):
    service = DataCenterService(db)
    dc = await service.get_by_id(dc_id)
    if not dc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据中心不存在")
    r = DataCenterResponse.model_validate(dc)
    r.room_count = len(dc.rooms or [])
    return r


@router.post("/data-centers", response_model=DataCenterResponse, status_code=status.HTTP_201_CREATED)
async def create_data_center(
    req: DataCenterCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("room:create"))
):
    service = DataCenterService(db)
    try:
        dc = await service.create(req, current_user.username, get_client_ip(request))
        r = DataCenterResponse.model_validate(dc)
        r.room_count = 0
        return r
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/data-centers/{dc_id}", response_model=DataCenterResponse)
async def update_data_center(
    dc_id: int,
    req: DataCenterUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("room:edit"))
):
    service = DataCenterService(db)
    dc = await service.update(dc_id, req, current_user.username, get_client_ip(request))
    if not dc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据中心不存在")
    r = DataCenterResponse.model_validate(dc)
    r.room_count = len(dc.rooms or [])
    return r


@router.delete("/data-centers/{dc_id}")
async def delete_data_center(
    dc_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("room:delete"))
):
    service = DataCenterService(db)
    if not await service.delete(dc_id, current_user.username, get_client_ip(request)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据中心不存在")
    return {"message": "数据中心已删除"}


# ==================== Room ====================

@router.get("/rooms", response_model=RoomPageResponse)
async def list_rooms(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    keyword: str = Query(None),
    data_center_id: int = Query(None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("room:view")),
):
    service = RoomService(db)
    items, total = await service.get_list(page, page_size, keyword, data_center_id)
    resp = []
    for room in items:
        r = RoomResponse.model_validate(room)
        r.rack_count = len(room.racks or [])
        r.data_center_name = room.data_center.name if room.data_center else ""
        resp.append(r)
    return RoomPageResponse(items=resp, total=total, page=page, page_size=page_size)


@router.get("/rooms/all", response_model=list[RoomResponse])
async def list_all_rooms(
    data_center_id: int = Query(None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("room:view")),
):
    service = RoomService(db)
    items, _ = await service.get_list(page=1, page_size=1000, data_center_id=data_center_id)
    resp = []
    for room in items:
        r = RoomResponse.model_validate(room)
        r.rack_count = len(room.racks or [])
        r.data_center_name = room.data_center.name if room.data_center else ""
        resp.append(r)
    return resp


@router.get("/rooms/{room_id}", response_model=RoomResponse)
async def get_room(
    room_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("room:view")),
):
    service = RoomService(db)
    room = await service.get_by_id(room_id)
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="机房不存在")
    r = RoomResponse.model_validate(room)
    r.rack_count = len(room.racks or [])
    r.data_center_name = room.data_center.name if room.data_center else ""
    return r


@router.post("/rooms", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
async def create_room(
    req: RoomCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("room:create"))
):
    service = RoomService(db)
    try:
        room = await service.create(req, current_user.username, get_client_ip(request))
        r = RoomResponse.model_validate(room)
        r.rack_count = 0
        if room.data_center:
            r.data_center_name = room.data_center.name
        return r
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/rooms/{room_id}", response_model=RoomResponse)
async def update_room(
    room_id: int,
    req: RoomUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("room:edit"))
):
    service = RoomService(db)
    room = await service.update(room_id, req, current_user.username, get_client_ip(request))
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="机房不存在")
    r = RoomResponse.model_validate(room)
    r.rack_count = len(room.racks or [])
    r.data_center_name = room.data_center.name if room.data_center else ""
    return r


@router.delete("/rooms/{room_id}")
async def delete_room(
    room_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("room:delete"))
):
    service = RoomService(db)
    if not await service.delete(room_id, current_user.username, get_client_ip(request)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="机房不存在")
    return {"message": "机房已删除"}


# ==================== Rack ====================

@router.get("/racks", response_model=RackPageResponse)
async def list_racks(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    keyword: str = Query(None),
    room_id: int = Query(None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("rack:view")),
):
    service = RackService(db)
    items, total = await service.get_list(page, page_size, keyword, room_id)
    resp = []
    for rack in items:
        r = RackResponse.model_validate(rack)
        r.device_count = len(rack.devices or [])
        r.room_name = rack.room.name if rack.room else ""
        resp.append(r)
    return RackPageResponse(items=resp, total=total, page=page, page_size=page_size)


@router.get("/racks/all", response_model=list[RackResponse])
async def list_all_racks(
    room_id: int = Query(None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("rack:view")),
):
    service = RackService(db)
    items, _ = await service.get_list(page=1, page_size=1000, room_id=room_id)
    resp = []
    for rack in items:
        r = RackResponse.model_validate(rack)
        r.device_count = len(rack.devices or [])
        r.room_name = rack.room.name if rack.room else ""
        resp.append(r)
    return resp


@router.get("/racks/{rack_id}", response_model=RackResponse)
async def get_rack(
    rack_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("rack:view")),
):
    service = RackService(db)
    rack = await service.get_by_id(rack_id)
    if not rack:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="机柜不存在")
    r = RackResponse.model_validate(rack)
    r.device_count = len(rack.devices or [])
    r.room_name = rack.room.name if rack.room else ""
    return r


@router.get("/racks/{rack_id}/environment")
async def rack_environment(
    rack_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("rack:view")),
):
    """机柜环境覆盖：返回该机柜所在机房的传感器当前值 + 活跃告警数。

    用于在前端机柜面上叠加温度/湿度/门磁等环境状态与告警标记。
    """
    from sqlalchemy import select, func
    service = RackService(db)
    rack = await service.get_by_id(rack_id)
    if not rack:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="机柜不存在")

    room_id = rack.room_id

    # 该机房下的传感器
    from app.models.sensor import Sensor
    rows = (await db.execute(
        select(Sensor).where(Sensor.room_id == room_id)
    )).scalars().all()
    sensors = []
    for s in rows:
        sensors.append({
            "id": s.id,
            "name": s.name,
            "code": s.code,
            "sensor_type": s.sensor_type,
            "install_position": s.install_position,
            "status": s.status,
            "current_value": s.current_value or {},
            "threshold_min": s.threshold_min,
            "threshold_max": s.threshold_max,
            "alert_level": s.alert_level,
        })

    # 该机房的活跃告警数（对应当机房设备/传感器）+ 各机柜告警数
    from app.models.facility import Rack
    from app.models.device import Device
    from app.models.alert import Alert
    rack_id_to_alerts = {}
    active = 0
    try:
        rack_ids = list((await db.execute(
            select(Rack.id).where(Rack.room_id == room_id)
        )).scalars().all())
        dev_ids = list((await db.execute(
            select(Device.id).where(Device.rack_id.in_(rack_ids) if rack_ids else Device.id < 0)
        )).scalars().all())
        if dev_ids:
            alerts = (await db.execute(
                select(Alert.device_id).where(
                    Alert.status.in_(["new", "acknowledged"]),
                    Alert.device_id.in_(dev_ids),
                )
            )).scalars().all()
            active = len(alerts)
            # 按设备所属机柜聚合告警数
            if alerts:
                dev_rack = dict((await db.execute(
                    select(Device.id, Device.rack_id).where(Device.rack_id.in_(rack_ids))
                )).all())
                for did in alerts:
                    rid = dev_rack.get(did)
                    if rid:
                        rack_id_to_alerts[rid] = rack_id_to_alerts.get(rid, 0) + 1
    except Exception:
        active = 0

    return {
        "rack_id": rack_id,
        "room_id": room_id,
        "sensors": sensors,
        "active_alerts": int(active),
        "rack_alerts": rack_id_to_alerts,
    }


@router.get("/rooms/{room_id}/rack3d")
async def room_rack3d(
    room_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("rack:view")),
):
    """机房 3D 场景聚合数据：机房 + 机柜 + 设备 + 环境覆盖，供前端 Three.js 一次性渲染。

    避免 3D 场景反复多次请求，减少首屏加载。
    """
    from fastapi import HTTPException
    from sqlalchemy import select, func
    from app.models.facility import Room, Rack
    from app.models.device import Device
    from app.models.sensor import Sensor
    from app.models.alert import Alert

    room = (await db.execute(select(Room).where(Room.id == room_id))).scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="机房不存在")

    racks = (await db.execute(
        select(Rack).where(Rack.room_id == room_id).order_by(Rack.row_pos, Rack.col_pos)
    )).scalars().all()

    rack_ids = [r.id for r in racks]
    devices_by_rack = {}
    if rack_ids:
        devs = (await db.execute(
            select(Device).where(Device.rack_id.in_(rack_ids))
        )).scalars().all()
        for d in devs:
            devices_by_rack.setdefault(d.rack_id, []).append({
                "id": d.id,
                "name": d.name,
                "asset_number": d.asset_number,
                "device_type_name": d.device_type.name if d.device_type else "",
                "device_type_category": d.device_type.category if d.device_type else "",
                "start_u": d.start_u,
                "end_u": d.end_u,
                "power_rating": d.power_rating,
                "status": d.status,
                "management_ip": d.management_ip,
            })

    # 环境：机房传感器 + 各机柜告警数
    sensors = (await db.execute(
        select(Sensor).where(Sensor.room_id == room_id)
    )).scalars().all()
    env_sensors = [{
        "id": s.id, "name": s.name, "sensor_type": s.sensor_type,
        "install_position": s.install_position, "status": s.status,
        "current_value": s.current_value or {},
    } for s in sensors]

    rack_alerts = {}
    if rack_ids:
        dev_ids = list((await db.execute(
            select(Device.id).where(Device.rack_id.in_(rack_ids))
        )).scalars().all())
        if dev_ids:
            active_devices = list((await db.execute(
                select(Alert.device_id).where(
                    Alert.status.in_(["new", "acknowledged"]),
                    Alert.device_id.in_(dev_ids),
                )
            )).scalars().all())
            if active_devices:
                dev_rack = dict((await db.execute(
                    select(Device.id, Device.rack_id).where(Device.rack_id.in_(rack_ids))
                )).all())
                for did in active_devices:
                    rid = dev_rack.get(did)
                    if rid:
                        rack_alerts[rid] = rack_alerts.get(rid, 0) + 1

    # 按机柜代号匹配安装于该机柜的温度传感器；未匹配则用机房平均温度兜底（用于 3D 温度热力层）
    temp_sensors_by_rack = {}
    for s in sensors:
        if s.sensor_type != "temperature":
            continue
        cv = s.current_value or {}
        v = cv.get("value")
        if not isinstance(v, (int, float)):
            continue
        pos = (s.install_position or "").lower()
        for r in racks:
            if r.code and r.code.lower() in pos:
                temp_sensors_by_rack.setdefault(r.id, []).append(float(v))

    room_temp_list = [float(s.current_value.get("value")) for s in sensors
                      if s.sensor_type == "temperature" and isinstance((s.current_value or {}).get("value"), (int, float))]
    temp_avg = round(sum(room_temp_list) / len(room_temp_list), 1) if room_temp_list else None

    rack_list = []
    for r in racks:
        util = 0
        if r.total_units:
            util = round((r.total_units - r.available_units) / r.total_units * 100)
        devs = devices_by_rack.get(r.id, [])
        power_load = round(sum((d.get("power_rating") or 0) for d in devs), 3)
        power_load_pct = 0
        if r.rated_power:
            power_load_pct = round(power_load / r.rated_power * 100)
        rack_temps = temp_sensors_by_rack.get(r.id)
        rack_temp = round(sum(rack_temps) / len(rack_temps), 1) if rack_temps else temp_avg
        rack_list.append({
            "id": r.id,
            "code": r.code,
            "name": r.name,
            "row_pos": r.row_pos,
            "col_pos": r.col_pos,
            "total_units": r.total_units,
            "available_units": r.available_units,
            "rated_power": r.rated_power,
            "power_load": power_load,
            "power_load_pct": power_load_pct,
            "pos_x_m": r.pos_x_m,
            "pos_z_m": r.pos_z_m,
            "width_m": r.width_m,
            "depth_m": r.depth_m,
            "facing_deg": r.facing_deg,
            "device_count": len(devs),
            "utilization": util,
            "alerts": rack_alerts.get(r.id, 0),
            "temperature": rack_temp,
            "devices": devs,
        })

    temp_min = round(min(room_temp_list), 1) if room_temp_list else None
    temp_max = round(max(room_temp_list), 1) if room_temp_list else None

    return {
        "room": {"id": room.id, "name": room.name, "code": room.code, "floor": room.floor, "area": room.area, "status": room.status},
        "racks": rack_list,
        "sensors": env_sensors,
        "rack_alerts": rack_alerts,
        "temperature": {"avg": temp_avg, "min": temp_min, "max": temp_max},
    }


@router.post("/racks", response_model=RackResponse, status_code=status.HTTP_201_CREATED)
async def create_rack(
    req: RackCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("rack:create"))
):
    service = RackService(db)
    try:
        rack = await service.create(req, current_user.username, get_client_ip(request))
        r = RackResponse.model_validate(rack)
        r.device_count = 0
        if rack.room:
            r.room_name = rack.room.name
        return r
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/racks/{rack_id}", response_model=RackResponse)
async def update_rack(
    rack_id: int,
    req: RackUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("rack:edit"))
):
    service = RackService(db)
    rack = await service.update(rack_id, req, current_user.username, get_client_ip(request))
    if not rack:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="机柜不存在")
    r = RackResponse.model_validate(rack)
    r.device_count = len(rack.devices or [])
    r.room_name = rack.room.name if rack.room else ""
    return r


@router.delete("/racks/{rack_id}")
async def delete_rack(
    rack_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("rack:delete"))
):
    service = RackService(db)
    if not await service.delete(rack_id, current_user.username, get_client_ip(request)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="机柜不存在")
    return {"message": "机柜已删除"}
