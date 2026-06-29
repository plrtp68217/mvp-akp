from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.connection import get_db
from app.services.rule_engine import RuleEngine

from app.schemas.order import OrderCreate

router = APIRouter(prefix="/orders", tags=["orders"])

@router.post("/", status_code=201)
async def create_order(
    order_data: OrderCreate,
    db: Session = Depends(get_db)
):
    total_amount = sum(item.quantity * item.price for item in order_data.items)

    engine = RuleEngine(db)
    processed_data = engine.process_rules({"total": total_amount})
    
    return {
        "message": "Order created",
        "processed_data": processed_data
    }