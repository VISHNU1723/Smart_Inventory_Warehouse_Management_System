from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.orders import PurchaseOrder, PurchaseOrderItem
from app.models.inventory import Supplier, Warehouse, Inventory, StockMovement
from app.models.product import Product
from app.models.user import User
from app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderResponse,
)
from app.auth.dependencies import get_current_user


router = APIRouter(
    prefix="/purchase-orders",
    tags=["Purchase Orders"]
)


def check_manager_role(current_user: User):
    if current_user.role not in ["Admin", "Inventory Manager"]:
        raise HTTPException(
            status_code=403,
            detail="Only Admin or Inventory Manager can perform this action"
        )


# CREATE PURCHASE ORDER
@router.post(
    "/",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_201_CREATED
)
def create_purchase_order(
    data: PurchaseOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    check_manager_role(current_user)

    # Check supplier
    supplier = db.query(Supplier).filter(
        Supplier.id == data.supplier_id
    ).first()

    if supplier is None:
        raise HTTPException(
            status_code=404,
            detail="Supplier not found"
        )

    if not supplier.is_active:
        raise HTTPException(
            status_code=400,
            detail="Inactive supplier cannot receive new purchase orders"
        )

    # Check warehouse
    warehouse = db.query(Warehouse).filter(
        Warehouse.id == data.warehouse_id
    ).first()

    if warehouse is None:
        raise HTTPException(
            status_code=404,
            detail="Warehouse not found"
        )

    if not warehouse.is_active:
        raise HTTPException(
            status_code=400,
            detail="Inactive warehouse cannot receive stock"
        )

    # Check PO number
    existing_po = db.query(PurchaseOrder).filter(
        PurchaseOrder.po_number == data.po_number
    ).first()

    if existing_po:
        raise HTTPException(
            status_code=409,
            detail="Purchase order number already exists"
        )

    if not data.items:
        raise HTTPException(
            status_code=400,
            detail="Purchase order must contain at least one item"
        )

    # Calculate expected delivery date using supplier lead time
    expected_delivery_date = data.expected_delivery_date

    if expected_delivery_date is None:
        expected_delivery_date = datetime.utcnow() + timedelta(
            days=supplier.lead_time_days
        )

    purchase_order = PurchaseOrder(
        po_number=data.po_number,
        supplier_id=data.supplier_id,
        warehouse_id=data.warehouse_id,
        expected_delivery_date=expected_delivery_date,
        total_amount=Decimal("0.00"),
        status="Draft",
        created_by=current_user.id
    )

    db.add(purchase_order)
    db.flush()

    total_amount = Decimal("0.00")

    for item_data in data.items:

        if item_data.quantity_ordered <= 0:
            raise HTTPException(
                status_code=400,
                detail="Ordered quantity must be greater than zero"
            )

        if item_data.unit_cost < 0:
            raise HTTPException(
                status_code=400,
                detail="Unit cost cannot be negative"
            )

        product = db.query(Product).filter(
            Product.id == item_data.product_id
        ).first()

        if product is None:
            raise HTTPException(
                status_code=404,
                detail=f"Product {item_data.product_id} not found"
            )

        if not product.is_active:
            raise HTTPException(
                status_code=400,
                detail=f"Product {item_data.product_id} is inactive"
            )

        line_total = (
            Decimal(item_data.quantity_ordered)
            * item_data.unit_cost
        )

        total_amount += line_total

        po_item = PurchaseOrderItem(
            purchase_order_id=purchase_order.id,
            product_id=item_data.product_id,
            quantity_ordered=item_data.quantity_ordered,
            quantity_received=0,
            unit_cost=item_data.unit_cost
        )

        db.add(po_item)

    purchase_order.total_amount = total_amount

    db.commit()
    db.refresh(purchase_order)

    return purchase_order


# APPROVE PURCHASE ORDER
@router.put("/{po_id}/approve")
def approve_purchase_order(
    po_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    check_manager_role(current_user)

    purchase_order = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id
    ).first()

    if purchase_order is None:
        raise HTTPException(
            status_code=404,
            detail="Purchase order not found"
        )

    if purchase_order.status != "Draft":
        raise HTTPException(
            status_code=400,
            detail="Only Draft purchase orders can be approved"
        )

    purchase_order.status = "Approved"

    db.commit()
    db.refresh(purchase_order)

    return {
        "message": "Purchase order approved successfully",
        "po_id": purchase_order.id,
        "status": purchase_order.status
    }


# CANCEL PURCHASE ORDER
@router.put("/{po_id}/cancel")
def cancel_purchase_order(
    po_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    check_manager_role(current_user)

    purchase_order = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id
    ).first()

    if purchase_order is None:
        raise HTTPException(
            status_code=404,
            detail="Purchase order not found"
        )

    if purchase_order.status not in ["Draft", "Approved"]:
        raise HTTPException(
            status_code=400,
            detail="Only Draft or Approved purchase orders can be cancelled"
        )

    for item in purchase_order.items:
        if item.quantity_received > 0:
            raise HTTPException(
                status_code=400,
                detail="Purchase order with received items cannot be cancelled"
            )

    purchase_order.status = "Cancelled"

    db.commit()
    db.refresh(purchase_order)

    return {
        "message": "Purchase order cancelled successfully",
        "po_id": purchase_order.id,
        "status": purchase_order.status
    }

@router.post("/{po_id}/receive", response_model=PurchaseOrderResponse)
def receive_purchase_order(
    po_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_manager_role(current_user)

    # Get purchase order
    purchase_order = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.id == po_id)
        .first()
    )

    if purchase_order is None:
        raise HTTPException(
            status_code=404,
            detail="Purchase order not found"
        )

    # Only Approved orders can be received
    if purchase_order.status != "Approved":
        raise HTTPException(
            status_code=400,
            detail="Only Approved purchase orders can be received"
        )

    # Check warehouse
    warehouse = (
        db.query(Warehouse)
        .filter(Warehouse.id == purchase_order.warehouse_id)
        .first()
    )

    if warehouse is None or not warehouse.is_active:
        raise HTTPException(
            status_code=400,
            detail="Warehouse is inactive or not found"
        )

    # Receive every item
    for item in purchase_order.items:

        product = (
            db.query(Product)
            .filter(Product.id == item.product_id)
            .first()
        )

        if product is None or not product.is_active:
            raise HTTPException(
                status_code=400,
                detail=f"Product {item.product_id} is inactive or not found"
            )

        # Get inventory row
        inventory = (
            db.query(Inventory)
            .filter(
                Inventory.product_id == item.product_id,
                Inventory.warehouse_id == purchase_order.warehouse_id
            )
            .first()
        )

        # Create inventory row if it doesn't exist
        if inventory is None:
            inventory = Inventory(
                product_id=item.product_id,
                warehouse_id=purchase_order.warehouse_id,
                quantity_on_hand=0,
                quantity_reserved=0,
                created_by=current_user.id,
            )
            db.add(inventory)
            db.flush()

        # Add received quantity to stock
        inventory.quantity_on_hand += item.quantity_ordered

        # Mark item as received
        item.quantity_received = item.quantity_ordered

        # Create stock movement
        movement = StockMovement(
            product_id=item.product_id,
            warehouse_id=purchase_order.warehouse_id,
            movement_type="Purchase Receipt",
            quantity=item.quantity_ordered,
            reference_id=purchase_order.id,
            balance_after=inventory.quantity_on_hand,
            performed_by=current_user.id,
        )

        db.add(movement)

    # Update purchase order
    purchase_order.status = "Received"
    purchase_order.received_at = datetime.utcnow()

    db.commit()
    db.refresh(purchase_order)

    return purchase_order

# GET ALL PURCHASE ORDERS
@router.get("/", response_model=list[PurchaseOrderResponse])
def get_purchase_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(PurchaseOrder)

    if status_filter:
        query = query.filter(PurchaseOrder.status == status_filter)

    if search:
        query = query.filter(
            PurchaseOrder.po_number.ilike(f"%{search}%")
        )

    return (
        query
        .order_by(PurchaseOrder.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

# GET PURCHASE ORDER BY ID
@router.get("/{po_id}", response_model=PurchaseOrderResponse)
def get_purchase_order(
    po_id: int,
    db: Session = Depends(get_db)
):
    purchase_order = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id
    ).first()

    if purchase_order is None:
        raise HTTPException(
            status_code=404,
            detail="Purchase order not found"
        )

    return purchase_order