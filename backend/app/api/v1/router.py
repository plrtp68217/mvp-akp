from fastapi import APIRouter
from app.api.v1.endpoints import rules, orders, variables

router = APIRouter()

router.include_router(rules.router, prefix="/api/v1")
router.include_router(orders.router, prefix="/api/v1")
router.include_router(variables.router, prefix="/api/v1")
