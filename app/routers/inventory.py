from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.inventory import Inventory, StockMovement
from app.models.product import Product
from app.models.user import User
from app.auth.dependencies import get_current_user


router = APIRouter(
    prefix="/inventory",
    tags=["Inventory"]
)


# =========================================================
# GET INVENTORY - PAGINATION + FILTERING
# =========================================================
@router.get("/")
def get_inventory(
    product_id: int | None = Query(None),
    warehouse_id: int | None = Query(None),
    low_stock: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Inventory)

    # Filter by product
    if product_id is not None:
        query = query.filter(
            Inventory.product_id == product_id
        )

    # Filter by warehouse
    if warehouse_id is not None:
        query = query.filter(
            Inventory.warehouse_id == warehouse_id
        )

    inventory = query.all()

    # Low-stock filter
    if low_stock:
        inventory = [
            item
            for item in inventory
            if item.quantity_available
            <= (
                item.product.reorder_level
                if item.product and item.product.reorder_level is not None
                else 0
            )
        ]

    # Pagination
    inventory = inventory[skip:skip + limit]

    return [
        {
            "id": item.id,
            "product_id": item.product_id,
            "warehouse_id": item.warehouse_id,
            "quantity_on_hand": item.quantity_on_hand,
            "quantity_reserved": item.quantity_reserved,
            "quantity_available": item.quantity_available
        }
        for item in inventory
    ]


# =========================================================
# GET INVENTORY BY PRODUCT + WAREHOUSE
# =========================================================
@router.get("/{product_id}/{warehouse_id}")
def get_inventory_by_product_warehouse(
    product_id: int,
    warehouse_id: int,
    db: Session = Depends(get_db)
):
    item = db.query(Inventory).filter(
        Inventory.product_id == product_id,
        Inventory.warehouse_id == warehouse_id
    ).first()

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Inventory record not found"
        )

    return {
        "id": item.id,
        "product_id": item.product_id,
        "warehouse_id": item.warehouse_id,
        "quantity_on_hand": item.quantity_on_hand,
        "quantity_reserved": item.quantity_reserved,
        "quantity_available": item.quantity_available
    }


# =========================================================
# STOCK IN
# =========================================================
@router.post("/stock-in")
def stock_in(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    product_id = data.get("product_id")
    warehouse_id = data.get("warehouse_id")
    quantity = data.get("quantity")

    if product_id is None or warehouse_id is None or quantity is None:
        raise HTTPException(
            status_code=400,
            detail="product_id, warehouse_id and quantity are required"
        )

    if quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail="Quantity must be greater than zero"
        )

    product = db.query(Product).filter(
        Product.id == product_id
    ).first()

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    inventory = db.query(Inventory).filter(
        Inventory.product_id == product_id,
        Inventory.warehouse_id == warehouse_id
    ).first()

    if inventory is None:
        inventory = Inventory(
            product_id=product_id,
            warehouse_id=warehouse_id,
            quantity_on_hand=quantity,
            quantity_reserved=0,
            created_by=current_user.id
        )
        db.add(inventory)
        db.flush()
    else:
        inventory.quantity_on_hand += quantity

    movement = StockMovement(
        product_id=product_id,
        warehouse_id=warehouse_id,
        movement_type="STOCK_IN",
        quantity=quantity,
        reference_id=None,
        balance_after=inventory.quantity_on_hand,
        performed_by=current_user.id
    )

    db.add(movement)
    db.commit()
    db.refresh(inventory)

    return {
        "message": "Stock added successfully",
        "product_id": inventory.product_id,
        "warehouse_id": inventory.warehouse_id,
        "quantity_on_hand": inventory.quantity_on_hand,
        "quantity_reserved": inventory.quantity_reserved,
        "quantity_available": inventory.quantity_available
    }


# =========================================================
# STOCK OUT
# =========================================================
@router.post("/stock-out")
def stock_out(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    product_id = data.get("product_id")
    warehouse_id = data.get("warehouse_id")
    quantity = data.get("quantity")

    if product_id is None or warehouse_id is None or quantity is None:
        raise HTTPException(
            status_code=400,
            detail="product_id, warehouse_id and quantity are required"
        )

    if quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail="Quantity must be greater than zero"
        )

    inventory = db.query(Inventory).filter(
        Inventory.product_id == product_id,
        Inventory.warehouse_id == warehouse_id
    ).first()

    if inventory is None:
        raise HTTPException(
            status_code=404,
            detail="Inventory record not found"
        )

    if quantity > inventory.quantity_available:
        raise HTTPException(
            status_code=400,
            detail="Insufficient available stock"
        )

    inventory.quantity_on_hand -= quantity

    movement = StockMovement(
        product_id=product_id,
        warehouse_id=warehouse_id,
        movement_type="STOCK_OUT",
        quantity=quantity,
        reference_id=None,
        balance_after=inventory.quantity_on_hand,
        performed_by=current_user.id
    )

    db.add(movement)
    db.commit()
    db.refresh(inventory)

    return {
        "message": "Stock removed successfully",
        "product_id": inventory.product_id,
        "warehouse_id": inventory.warehouse_id,
        "quantity_on_hand": inventory.quantity_on_hand,
        "quantity_reserved": inventory.quantity_reserved,
        "quantity_available": inventory.quantity_available
    }


# =========================================================
# GET STOCK MOVEMENTS - FILTERING + PAGINATION
# =========================================================
@router.get("/movements")
def get_stock_movements(
    product_id: int | None = Query(None),
    warehouse_id: int | None = Query(None),
    movement_type: str | None = Query(None),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    query = db.query(StockMovement)

    if product_id is not None:
        query = query.filter(
            StockMovement.product_id == product_id
        )

    if warehouse_id is not None:
        query = query.filter(
            StockMovement.warehouse_id == warehouse_id
        )

    if movement_type is not None:
        query = query.filter(
            StockMovement.movement_type == movement_type
        )

    if start_date is not None:
        query = query.filter(
            StockMovement.created_at >= start_date
        )

    if end_date is not None:
        query = query.filter(
            StockMovement.created_at <= end_date
        )

    movements = (
        query
        .order_by(StockMovement.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return [
        {
            "id": movement.id,
            "product_id": movement.product_id,
            "warehouse_id": movement.warehouse_id,
            "movement_type": movement.movement_type,
            "quantity": movement.quantity,
            "balance_after": movement.balance_after,
            "performed_by": movement.performed_by,
            "created_at": movement.created_at
        }
        for movement in movements
    ]