from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.adjustment import StockAdjustment
from app.models.inventory import Inventory

router = APIRouter(
    prefix="/adjustments",
    tags=["Stock Adjustments"]
)


@router.post("/", status_code=201)
def create_adjustment(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["Warehouse Staff", "Admin", "Inventory Manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    required = ["product_id", "warehouse_id", "quantity", "reason"]

    for field in required:
        if field not in data:
            raise HTTPException(status_code=422, detail=f"{field} is required")

    if data["quantity"] <= 0:
        raise HTTPException(status_code=422, detail="Quantity must be positive")

    valid_reasons = ["Damaged", "Lost", "Expired", "Found", "Count Correction"]

    if data["reason"] not in valid_reasons:
        raise HTTPException(
            status_code=422,
            detail=f"Reason must be one of: {', '.join(valid_reasons)}"
        )

    adjustment = StockAdjustment(
        product_id=data["product_id"],
        warehouse_id=data["warehouse_id"],
        quantity=data["quantity"],
        reason=data["reason"],
        notes=data.get("notes"),
        created_by=current_user.id,
        status="Pending"
    )

    db.add(adjustment)
    db.commit()
    db.refresh(adjustment)

    return adjustment


@router.get("/")
def get_adjustments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(StockAdjustment).order_by(
        StockAdjustment.id.desc()
    ).all()


@router.put("/{adjustment_id}/approve")
def approve_adjustment(
    adjustment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["Admin", "Inventory Manager"]:
        raise HTTPException(status_code=403, detail="Only Admin or Inventory Manager can approve")

    adjustment = db.query(StockAdjustment).filter(
        StockAdjustment.id == adjustment_id
    ).first()

    if not adjustment:
        raise HTTPException(status_code=404, detail="Adjustment not found")

    if adjustment.status != "Pending":
        raise HTTPException(status_code=400, detail="Only Pending adjustments can be approved")

    inventory = db.query(Inventory).filter(
        Inventory.product_id == adjustment.product_id,
        Inventory.warehouse_id == adjustment.warehouse_id
    ).first()

    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory record not found")

    if adjustment.reason in ["Damaged", "Lost", "Expired"]:
        if inventory.quantity_on_hand < adjustment.quantity:
            raise HTTPException(status_code=400, detail="Insufficient stock")
        inventory.quantity_on_hand -= adjustment.quantity
    else:
        inventory.quantity += adjustment.quantity

    adjustment.status = "Approved"
    adjustment.approved_by = current_user.id
    adjustment.approved_at = datetime.utcnow()

    db.commit()
    db.refresh(adjustment)

    return adjustment


@router.put("/{adjustment_id}/reject")
def reject_adjustment(
    adjustment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["Admin", "Inventory Manager"]:
        raise HTTPException(status_code=403, detail="Only Admin or Inventory Manager can reject")

    adjustment = db.query(StockAdjustment).filter(
        StockAdjustment.id == adjustment_id
    ).first()

    if not adjustment:
        raise HTTPException(status_code=404, detail="Adjustment not found")

    if adjustment.status != "Pending":
        raise HTTPException(status_code=400, detail="Only Pending adjustments can be rejected")

    adjustment.status = "Rejected"
    adjustment.approved_by = current_user.id
    adjustment.approved_at = datetime.utcnow()

    db.commit()
    db.refresh(adjustment)

    return adjustment