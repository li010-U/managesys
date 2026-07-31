"""机房管理 API 路由"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user
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
    _current_user: User = Depends(get_current_user),
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
    _current_user: User = Depends(get_current_user),
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
    _current_user: User = Depends(get_current_user),
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
    _current_user: User = Depends(get_current_user),
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
    _current_user: User = Depends(get_current_user),
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
    _current_user: User = Depends(get_current_user),
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
    _current_user: User = Depends(get_current_user),
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
    _current_user: User = Depends(get_current_user),
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
    _current_user: User = Depends(get_current_user),
):
    service = RackService(db)
    rack = await service.get_by_id(rack_id)
    if not rack:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="机柜不存在")
    r = RackResponse.model_validate(rack)
    r.device_count = len(rack.devices or [])
    r.room_name = rack.room.name if rack.room else ""
    return r


@router.post("/racks", response_model=RackResponse, status_code=status.HTTP_201_CREATED)
async def create_rack(
    req: RackCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
):
    service = RackService(db)
    if not await service.delete(rack_id, current_user.username, get_client_ip(request)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="机柜不存在")
    return {"message": "机柜已删除"}
