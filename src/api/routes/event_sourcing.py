"""
事件溯源 API 路由
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ...core.event_sourcing import EventType, get_event_store

router = APIRouter(prefix="/events", tags=["事件溯源"])


@router.get("")
async def get_events(
    aggregate_type: str | None = Query(None),
    aggregate_id: str | None = Query(None),
    event_type: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
) -> dict[str, Any]:
    """获取事件列表"""
    event_store = get_event_store()

    try:
        et = EventType(event_type) if event_type else None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid event type: {event_type}") from e

    events = event_store.get_events(
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_type=et,
        limit=limit,
    )

    return {
        "events": [e.to_dict() for e in events],
        "count": len(events),
    }


@router.get("/stats")
async def get_event_stats() -> dict[str, Any]:
    """获取事件统计"""
    event_store = get_event_store()
    return event_store.get_stats()


@router.get("/aggregate/{aggregate_type}/{aggregate_id}")
async def get_aggregate_events(
    aggregate_type: str,
    aggregate_id: str,
) -> dict[str, Any]:
    """获取聚合根的所有事件"""
    event_store = get_event_store()
    events = event_store.get_events_for_aggregate(aggregate_type, aggregate_id)

    return {
        "aggregate_type": aggregate_type,
        "aggregate_id": aggregate_id,
        "events": [e.to_dict() for e in events],
        "count": len(events),
    }


@router.get("/aggregate/{aggregate_type}/{aggregate_id}/state")
async def get_aggregate_state(
    aggregate_type: str,
    aggregate_id: str,
) -> dict[str, Any]:
    """重建聚合根状态"""
    event_store = get_event_store()

    try:
        state = event_store.rebuild_aggregate(aggregate_type, aggregate_id)
        return state
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to rebuild state: {str(e)}") from e
