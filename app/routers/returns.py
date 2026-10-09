from decimal import Decimal
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.orders import (
    ReturnRequest,
    ReturnItem,
    SalesOrder,
)
from app.models.inventory import Inventory
from app.models.user import User
from app.schemas.returns import ReturnCreate, ReturnResponse
from app.auth.dependencies import get_current_user


router = APIRouter(
    prefix="/returns",
    tags=["Returns"],
)


# CREATE RETURN
@router.post(
    "/sales-orders/{so_id}/returns",
    response_model=ReturnResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_return(
    so_id: int,
    data: ReturnCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Only Inventory Manager can create returns
    if current_user.role != "Inventory Manager":
        raise HTTPException(
            status_code=403,
            detail="Only Inventory Manager can create return requests",
        )

    sales_order = (
        db.query(SalesOrder)
        .filter(SalesOrder.id == so_id)
        .first()
    )

    if sales_order is None:
        raise HTTPException(
            status_code=404,
            detail="Sales order not found",
        )

    # Return only delivered orders
    if sales_order.status != "Delivered":
        raise HTTPException(
            status_code=400,
            detail="Returns are allowed only for Delivered orders",
        )

    # Return within 7 days
    if sales_order.delivered_at is None:
        raise HTTPException(
            status_code=400,
            detail="Delivery date is not available",
        )

    if datetime.utcnow() > sales_order.delivered_at + timedelta(days=7):
        raise HTTPException(
            status_code=400,
            detail="Return period of 7 days has expired",
        )

    if not data.items:
        raise HTTPException(
            status_code=400,
            detail="Return must contain at least one item",
        )

    # Create return request
    return_request = ReturnRequest(
        so_id=so_id,
        reason=data.reason,
        condition=data.condition,
        status="Requested",
        refund_amount=Decimal("0.00"),
        created_by=current_user.id,
    )

    db.add(return_request)
    db.flush()

    for return_item in data.items:

        order_item = (
            db.query(
                __import__(
                    "app.models.orders",
                    fromlist=["SalesOrderItem"]
                ).SalesOrderItem
            )
            .filter(
                __import__(
                    "app.models.orders",
                    fromlist=["SalesOrderItem"]
                ).SalesOrderItem.sales_order_id == so_id,
                __import__(
                    "app.models.orders",
                    fromlist=["SalesOrderItem"]
                ).SalesOrderItem.product_id == return_item.product_id,
            )
            .first()
        )

        if order_item is None:
            raise HTTPException(
                status_code=400,
                detail=f"Product {return_item.product_id} was not part of the order",
            )

        if return_item.quantity > order_item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Return quantity exceeds ordered quantity for product {return_item.product_id}",
            )

        db.add(
            ReturnItem(
                return_id=return_request.id,
                product_id=return_item.product_id,
                quantity=return_item.quantity,
                condition=data.condition,
            )
        )

        # Refund based on original order price including GST
        item_refund = (
            order_item.unit_price
            * return_item.quantity
            * Decimal("1.18")
        )

        return_request.refund_amount += item_refund

    db.commit()
    db.refresh(return_request)

    return return_request


# GET ALL RETURNS
@router.get("/", response_model=list[ReturnResponse])
def get_returns(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(ReturnRequest).all()


# INSPECT RETURN
@router.put("/{return_id}/inspect", response_model=ReturnResponse)
def inspect_return(
    return_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ["Admin", "Warehouse Staff"]:
        raise HTTPException(
            status_code=403,
            detail="Only Warehouse Staff or Admin can inspect returns",
        )

    return_request = (
        db.query(ReturnRequest)
        .filter(ReturnRequest.id == return_id)
        .first()
    )

    if return_request is None:
        raise HTTPException(
            status_code=404,
            detail="Return request not found",
        )

    if return_request.status != "Requested":
        raise HTTPException(
            status_code=400,
            detail="Only Requested returns can be inspected",
        )

    return_request.status = "Inspected"

    db.commit()
    db.refresh(return_request)

    return return_request


# APPROVE RETURN
@router.put("/{return_id}/approve", response_model=ReturnResponse)
def approve_return(
    return_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ["Admin", "Inventory Manager"]:
        raise HTTPException(
            status_code=403,
            detail="Only Admin or Inventory Manager can approve returns",
        )

    return_request = (
        db.query(ReturnRequest)
        .filter(ReturnRequest.id == return_id)
        .first()
    )

    if return_request is None:
        raise HTTPException(
            status_code=404,
            detail="Return request not found",
        )

    if return_request.status != "Inspected":
        raise HTTPException(
            status_code=400,
            detail="Only Inspected returns can be approved",
        )

    sales_order = (
        db.query(SalesOrder)
        .filter(SalesOrder.id == return_request.so_id)
        .first()
    )

    for item in return_request.items:

        if item.condition == "Good":
            inventory = (
                db.query(Inventory)
                .filter(
                    Inventory.product_id == item.product_id,
                    Inventory.warehouse_id == sales_order.warehouse_id,
                )
                .first()
            )

            if inventory:
                inventory.quantity_on_hand += item.quantity

    return_request.status = "Refunded"

    db.commit()
    db.refresh(return_request)

    return return_request


# REJECT RETURN
@router.put("/{return_id}/reject", response_model=ReturnResponse)
def reject_return(
    return_id: int,
    rejection_reason: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ["Admin", "Inventory Manager"]:
        raise HTTPException(
            status_code=403,
            detail="Only Admin or Inventory Manager can reject returns",
        )

    return_request = (
        db.query(ReturnRequest)
        .filter(ReturnRequest.id == return_id)
        .first()
    )

    if return_request is None:
        raise HTTPException(
            status_code=404,
            detail="Return request not found",
        )

    if return_request.status != "Inspected":
        raise HTTPException(
            status_code=400,
            detail="Only Inspected returns can be rejected",
        )

    if not rejection_reason.strip():
        raise HTTPException(
            status_code=400,
            detail="Rejection reason is required",
        )

    return_request.status = "Rejected"
    return_request.rejection_reason = rejection_reason

    db.commit()
    db.refresh(return_request)

    return return_request 