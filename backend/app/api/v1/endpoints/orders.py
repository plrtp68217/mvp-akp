from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.connection import get_db
from app.schemas.order import OrderCreate, OrderResponse
from app.services.rule_service import RuleService

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/", response_model=OrderResponse, status_code=201)
def create_order(
    order_data: OrderCreate,
    db: Session = Depends(get_db),
):
    """Создать заказ и прогнать активные правила через движок."""
    service = RuleService(db)
    order, applied_actions = service.process_order(order_data)

    response = OrderResponse.model_validate(order)
    response.applied_actions = applied_actions
    return response
