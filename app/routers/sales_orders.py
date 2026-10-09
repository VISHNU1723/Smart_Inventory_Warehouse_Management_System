from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.orders import SalesOrder, SalesOrderItem
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.orders import Customer
from app.schemas.sales_order import SalesOrderCreate, SalesOrderResponse
from app.auth.dependencies import get_current_user
from app.models.user import User


router = APIRouter(
    prefix="/sales-orders",
    tags=["Sales Orders"],
)


@router.post(
    "/",
    response_model=SalesOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_sales_order(
    data: SalesOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    customer = (
        db.query(Customer)
        .filter(Customer.id == data.customer_id)
        .first()
    )

    if customer is None:
        raise HTTPException(
            status_code=404,
            detail="Customer not found",
        )

    if not customer.is_active:
        raise HTTPException(
            status_code=400,
            detail="Inactive customer cannot place sales orders",
        )

    existing = (
        db.query(SalesOrder)
        .filter(SalesOrder.so_number == data.so_number)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Sales order number already exists",
        )

    if not data.items:
        raise HTTPException(
            status_code=400,
            detail="Sales order must contain at least one item",
        )

    subtotal = Decimal("0.00")

    for item in data.items:
        product = (
            db.query(Product)
            .filter(Product.id == item.product_id)
            .first()
        )

        if product is None:
            raise HTTPException(
                status_code=404,
                detail=f"Product {item.product_id} not found",
            )

        if not product.is_active:
            raise HTTPException(
                status_code=400,
                detail=f"Product {item.product_id} is inactive",
            )

        inventory = (
            db.query(Inventory)
            .filter(
                Inventory.product_id == item.product_id,
                Inventory.warehouse_id == data.warehouse_id,
            )
            .first()
        )

        if inventory is None:
            raise HTTPException(
                status_code=400,
                detail=f"No inventory found for product {item.product_id}",
            )

        available = (
            inventory.quantity_on_hand
            - inventory.quantity_reserved
        )

        if item.quantity > available:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for product {item.product_id}",
            )

        subtotal += item.unit_price * item.quantity

    tax_amount = subtotal * Decimal("0.18")
    grand_total = subtotal + tax_amount

    sales_order = SalesOrder(
        so_number=data.so_number,
        customer_id=data.customer_id,
        warehouse_id=data.warehouse_id,
        subtotal=subtotal,
        tax_amount=tax_amount,
        grand_total=grand_total,
        status="Draft",
        created_by=current_user.id,
    )

    db.add(sales_order)
    db.flush()

    for item in data.items:
        line_total = item.unit_price * item.quantity

        order_item = SalesOrderItem(
            sales_order_id=sales_order.id,
            product_id=item.product_id,
            quantity=item.quantity,
            unit_price=item.unit_price,
            line_total=line_total,
        )

        db.add(order_item)

    db.commit()
    db.refresh(sales_order)

    return sales_order

@router.put("/{so_id}/confirm", response_model=SalesOrderResponse)
def confirm_sales_order(
    so_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Role check
    if current_user.role not in ["Admin", "Inventory Manager"]:
        raise HTTPException(
            status_code=403,
            detail="Only Admin or Inventory Manager can confirm sales orders"
        )

    # Get sales order
    sales_order = (
        db.query(SalesOrder)
        .filter(SalesOrder.id == so_id)
        .first()
    )

    if sales_order is None:
        raise HTTPException(
            status_code=404,
            detail="Sales order not found"
        )

    # Order must be Draft
    if sales_order.status != "Draft":
        raise HTTPException(
            status_code=400,
            detail="Only Draft sales orders can be confirmed"
        )

    # Check customer
    customer = (
        db.query(Customer)
        .filter(Customer.id == sales_order.customer_id)
        .first()
    )

    if customer is None or not customer.is_active:
        raise HTTPException(
            status_code=400,
            detail="Customer is inactive or not found"
        )

    # Check warehouse
    from app.models.inventory import Warehouse

    warehouse = (
        db.query(Warehouse)
        .filter(Warehouse.id == sales_order.warehouse_id)
        .first()
    )

    if warehouse is None or not warehouse.is_active:
        raise HTTPException(
            status_code=400,
            detail="Warehouse is inactive or not found"
        )

    # Check available stock and reserve it
    for item in sales_order.items:

        inventory = (
            db.query(Inventory)
            .filter(
                Inventory.product_id == item.product_id,
                Inventory.warehouse_id == sales_order.warehouse_id
            )
            .first()
        )

        if inventory is None:
            raise HTTPException(
                status_code=400,
                detail=f"No inventory found for product {item.product_id}"
            )

        available_stock = (
            inventory.quantity_on_hand - inventory.quantity_reserved
        )

        if item.quantity > available_stock:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient available stock for product {item.product_id}"
            )

        inventory.quantity_reserved += item.quantity

    # Check customer credit limit
    open_order_total = (
        db.query(SalesOrder)
        .filter(
            SalesOrder.customer_id == sales_order.customer_id,
            SalesOrder.id != sales_order.id,
            SalesOrder.status.in_(
                ["Confirmed", "Picked", "Packed", "Dispatched"]
            )
        )
        .with_entities(SalesOrder.grand_total)
        .all()
    )

    existing_credit = sum(
        (amount[0] or Decimal("0.00")) for amount in open_order_total
    )

    if existing_credit + sales_order.grand_total > customer.credit_limit:
        raise HTTPException(
            status_code=400,
            detail="Customer credit limit exceeded"
        )

    # Confirm order
    sales_order.status = "Confirmed"

    db.commit()
    db.refresh(sales_order)

    return sales_order

@router.put("/{so_id}/cancel", response_model=SalesOrderResponse)
def cancel_sales_order(
    so_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Role check
    if current_user.role not in ["Admin", "Inventory Manager"]:
        raise HTTPException(
            status_code=403,
            detail="Only Admin or Inventory Manager can cancel sales orders"
        )

    # Get sales order
    sales_order = (
        db.query(SalesOrder)
        .filter(SalesOrder.id == so_id)
        .first()
    )

    if sales_order is None:
        raise HTTPException(
            status_code=404,
            detail="Sales order not found"
        )

    # Only Draft or Confirmed orders can be cancelled
    if sales_order.status not in ["Draft", "Confirmed"]:
        raise HTTPException(
            status_code=400,
            detail="Only Draft or Confirmed sales orders can be cancelled"
        )

    # Release reserved stock if order was Confirmed
    if sales_order.status == "Confirmed":
        for item in sales_order.items:
            inventory = (
                db.query(Inventory)
                .filter(
                    Inventory.product_id == item.product_id,
                    Inventory.warehouse_id == sales_order.warehouse_id
                )
                .first()
            )

            if inventory:
                inventory.quantity_reserved = max(
                    0,
                    inventory.quantity_reserved - item.quantity
                )

    sales_order.status = "Cancelled"

    db.commit()
    db.refresh(sales_order)

    return sales_order

@router.put("/{so_id}/pick", response_model=SalesOrderResponse)
def pick_sales_order(
    so_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ["Admin", "Warehouse Staff"]:
        raise HTTPException(
            status_code=403,
            detail="Only Admin or Warehouse Staff can pick sales orders"
        )

    sales_order = (
        db.query(SalesOrder)
        .filter(SalesOrder.id == so_id)
        .first()
    )

    if sales_order is None:
        raise HTTPException(
            status_code=404,
            detail="Sales order not found"
        )

    if sales_order.status != "Confirmed":
        raise HTTPException(
            status_code=400,
            detail="Only Confirmed sales orders can be picked"
        )

    sales_order.status = "Picked"

    db.commit()
    db.refresh(sales_order)

    return sales_order

@router.put("/{so_id}/pack", response_model=SalesOrderResponse)
def pack_sales_order(
    so_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ["Admin", "Warehouse Staff"]:
        raise HTTPException(
            status_code=403,
            detail="Only Admin or Warehouse Staff can pack sales orders"
        )

    sales_order = (
        db.query(SalesOrder)
        .filter(SalesOrder.id == so_id)
        .first()
    )

    if sales_order is None:
        raise HTTPException(
            status_code=404,
            detail="Sales order not found"
        )

    if sales_order.status != "Picked":
        raise HTTPException(
            status_code=400,
            detail="Only Picked sales orders can be packed"
        )

    sales_order.status = "Packed"

    db.commit()
    db.refresh(sales_order)

    return sales_order

@router.put("/{so_id}/dispatch", response_model=SalesOrderResponse)
def dispatch_sales_order(
    so_id: int,
    courier_name: str,
    tracking_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ["Admin", "Warehouse Staff"]:
        raise HTTPException(
            status_code=403,
            detail="Only Admin or Warehouse Staff can dispatch sales orders"
        )

    sales_order = (
        db.query(SalesOrder)
        .filter(SalesOrder.id == so_id)
        .first()
    )

    if sales_order is None:
        raise HTTPException(status_code=404, detail="Sales order not found")

    if sales_order.status != "Packed":
        raise HTTPException(
            status_code=400,
            detail="Only Packed sales orders can be dispatched"
        )

    existing_tracking = (
        db.query(SalesOrder)
        .filter(SalesOrder.tracking_number == tracking_number)
        .first()
    )

    if existing_tracking:
        raise HTTPException(
            status_code=409,
            detail="Tracking number already exists"
        )

    sales_order.courier_name = courier_name
    sales_order.tracking_number = tracking_number
    sales_order.dispatched_at = datetime.utcnow()
    sales_order.status = "Dispatched"

    db.commit()
    db.refresh(sales_order)

    return sales_order

@router.put("/{so_id}/deliver", response_model=SalesOrderResponse)
def deliver_sales_order(
    so_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ["Admin", "Warehouse Staff"]:
        raise HTTPException(
            status_code=403,
            detail="Only Admin or Warehouse Staff can deliver sales orders"
        )

    sales_order = (
        db.query(SalesOrder)
        .filter(SalesOrder.id == so_id)
        .first()
    )

    if sales_order is None:
        raise HTTPException(status_code=404, detail="Sales order not found")

    if sales_order.status != "Dispatched":
        raise HTTPException(
            status_code=400,
            detail="Only Dispatched sales orders can be delivered"
        )

    sales_order.status = "Delivered"
    sales_order.delivered_at = datetime.utcnow()

    db.commit()
    db.refresh(sales_order)

    return sales_order

@router.get(
    "/",
    response_model=list[SalesOrderResponse],
)
def get_sales_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(SalesOrder)

    if status_filter:
        query = query.filter(SalesOrder.status == status_filter)

    if search:
        query = query.filter(
            SalesOrder.so_number.ilike(f"%{search}%")
        )

    return (
        query
        .order_by(SalesOrder.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get(
    "/{so_id}",
    response_model=SalesOrderResponse,
)
def get_sales_order(
    so_id: int,
    db: Session = Depends(get_db),
):
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

    return sales_order

@router.put("/{so_id}/confirm", response_model=SalesOrderResponse)
def confirm_sales_order(
    so_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ["Admin", "Inventory Manager"]:
        raise HTTPException(
            status_code=403,
            detail="Only Admin or Inventory Manager can confirm sales orders",
        )

    sales_order = (
        db.query(SalesOrder)
        .filter(SalesOrder.id == so_id)
        .first()
    )

    if sales_order is None:
        raise HTTPException(status_code=404, detail="Sales order not found")

    if sales_order.status != "Draft":
        raise HTTPException(
            status_code=400,
            detail="Only Draft orders can be confirmed",
        )

    customer = (
        db.query(Customer)
        .filter(Customer.id == sales_order.customer_id)
        .first()
    )

    if customer is None or not customer.is_active:
        raise HTTPException(
            status_code=400,
            detail="Customer is inactive or not found",
        )

    # Check customer credit limit
    open_statuses = ["Confirmed", "Picked", "Packed", "Dispatched"]

    open_orders = (
        db.query(SalesOrder)
        .filter(
            SalesOrder.customer_id == sales_order.customer_id,
            SalesOrder.status.in_(open_statuses),
            SalesOrder.id != sales_order.id,
        )
        .all()
    )

    open_value = sum(
        (order.grand_total for order in open_orders),
        Decimal("0.00"),
    )

    if open_value + sales_order.grand_total > customer.credit_limit:
        raise HTTPException(
            status_code=400,
            detail="Customer credit limit exceeded",
        )

    # Reserve stock
    for item in sales_order.items:
        inventory = (
            db.query(Inventory)
            .filter(
                Inventory.product_id == item.product_id,
                Inventory.warehouse_id == sales_order.warehouse_id,
            )
            .first()
        )

        if inventory is None:
            raise HTTPException(
                status_code=400,
                detail=f"No inventory found for product {item.product_id}",
            )

        available = (
            inventory.quantity_on_hand
            - inventory.quantity_reserved
        )

        if item.quantity > available:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for product {item.product_id}",
            )

        inventory.quantity_reserved += item.quantity

    sales_order.status = "Confirmed"

    db.commit()
    db.refresh(sales_order)

    return sales_order

@router.put("/{so_id}/cancel", response_model=SalesOrderResponse)
def cancel_sales_order(
    so_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ["Admin", "Inventory Manager"]:
        raise HTTPException(
            status_code=403,
            detail="Only Admin or Inventory Manager can cancel sales orders",
        )

    sales_order = (
        db.query(SalesOrder)
        .filter(SalesOrder.id == so_id)
        .first()
    )

    if sales_order is None:
        raise HTTPException(status_code=404, detail="Sales order not found")

    if sales_order.status not in ["Draft", "Confirmed"]:
        raise HTTPException(
            status_code=400,
            detail="Only Draft or Confirmed orders can be cancelled",
        )

    # Release reserved stock if the order was confirmed
    if sales_order.status == "Confirmed":
        for item in sales_order.items:
            inventory = (
                db.query(Inventory)
                .filter(
                    Inventory.product_id == item.product_id,
                    Inventory.warehouse_id == sales_order.warehouse_id,
                )
                .first()
            )

            if inventory:
                inventory.quantity_reserved = max(
                    0,
                    inventory.quantity_reserved - item.quantity
                )

    sales_order.status = "Cancelled"

    db.commit()
    db.refresh(sales_order)

    return sales_order