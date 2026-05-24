from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.schemas.evolution import AnalyzeRequest, StrategyApplyRequest
from app.services.evolution_service import EvolutionService

router = APIRouter()


@router.post("/analyze")
async def analyze(
    payload: AnalyzeRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = EvolutionService(db)
    event, strategies = await svc.analyze(
        user_id=current_user.id,
        course_id=payload.course_id,
        focus=payload.focus,
    )
    return success_response(
        {
            "event": event.__class__.__name__,
            "event_id": str(event.id),
            "strategies_count": len(strategies),
            "strategies": [
                {
                    "id": str(s.id),
                    "strategy_type": s.strategy_type,
                    "before_value": s.before_value,
                    "after_value": s.after_value,
                    "description": s.description,
                    "status": s.status,
                    "risk_level": s.risk_level,
                    "evidence": s.evidence,
                    "version_no": s.version_no,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in strategies
            ],
        },
        request=request,
    )


@router.get("/strategies")
async def list_strategies(
    request: Request,
    course_id: UUID | None = None,
    strategy_type: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = EvolutionService(db)
    items, total = await svc.list_strategies(
        user_id=current_user.id,
        course_id=course_id,
        strategy_type=strategy_type,
        status=status,
        page=page,
        page_size=page_size,
    )
    return success_response(
        {
            "items": [s.model_dump(mode="json") for s in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        request=request,
    )


@router.post("/strategies/apply")
async def apply_strategy(
    payload: StrategyApplyRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = EvolutionService(db)
    strategy = await svc.apply_strategy(payload.strategy_id, current_user.id)
    return success_response(strategy.model_dump(mode="json"), request=request)


@router.get("/strategies/{strategy_id}")
async def get_strategy(
    strategy_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = EvolutionService(db)
    strategy = await svc.get_strategy(strategy_id)
    return success_response(strategy.model_dump(mode="json"), request=request)


@router.post("/strategies/{strategy_id}/rollback")
async def rollback_strategy(
    strategy_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = EvolutionService(db)
    strategy = await svc.rollback_strategy(strategy_id, current_user.id)
    return success_response(strategy.model_dump(mode="json"), request=request)


@router.get("/events")
async def list_events(
    request: Request,
    course_id: UUID | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = EvolutionService(db)
    items, total = await svc.list_events(
        user_id=current_user.id,
        course_id=course_id,
        page=page,
        page_size=page_size,
    )
    return success_response(
        {
            "items": [e.model_dump(mode="json") for e in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        request=request,
    )
