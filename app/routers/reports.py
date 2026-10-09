from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.product import Product
from app.models.inventory import Inventory, Warehouse, Supplier
from app.models.orders import (
    PurchaseOrder,
    SalesOrder,
    SalesOrderItem,
    ReturnRequest,
)


router = APIRouter(
    prefix="/reports",
    tags=["Reports"],
)


def check_report_role(current_user: User):
    if current_user.role not in ["Admin", "Inventory Manager"]:
        raise HTTPException(
            status_code=403,
            detail="Only Admin or Inventory Manager can view reports",
        )


@router.get("/dashboard")
def dashboard_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_report_role(current_user)

    total_products = db.query(Product).filter(Product.is_active == True).count()

    total_stock_value = (
        db.query(
            func.coalesce(
                func.sum(Inventory.quantity_on_hand * Product.cost_price),
                0,
            )
        )
        .join(Product, Product.id == Inventory.product_id)
        .scalar()
    )

    low_stock_count = (
        db.query(Inventory)
        .join(Product, Product.id == Inventory.product_id)
        .filter(
            Product.is_active == True,
            Inventory.quantity_available <= Product.reorder_level,
        )
        .count()
    )

    pending_purchase_orders = (
        db.query(PurchaseOrder)
        .filter(
            PurchaseOrder.status.in_(["Draft", "Approved", "Partially Received"])
        )
        .count()
    )

    pending_sales_orders = (
        db.query(SalesOrder)
        .filter(
            SalesOrder.status.in_(["Draft", "Confirmed", "Picked", "Packed"])
        )
        .count()
    )

    today = datetime.utcnow().date()

    today_dispatches = (
        db.query(SalesOrder)
        .filter(
            SalesOrder.dispatched_at.isnot(None),
            func.date(SalesOrder.dispatched_at) == today,
        )
        .count()
    )

    return {
        "total_products": total_products,
        "total_stock_value": float(total_stock_value or 0),
        "low_stock_count": low_stock_count,
        "pending_purchase_orders": pending_purchase_orders,
        "pending_sales_orders": pending_sales_orders,
        "todays_dispatches": today_dispatches,
    }


@router.get("/stock-valuation")
def stock_valuation_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_report_role(current_user)

    rows = (
        db.query(
            Warehouse.id,
            Warehouse.name,
            func.coalesce(
                func.sum(Inventory.quantity_on_hand * Product.cost_price),
                0,
            ).label("stock_value"),
        )
        .join(Inventory, Inventory.warehouse_id == Warehouse.id)
        .join(Product, Product.id == Inventory.product_id)
        .group_by(Warehouse.id, Warehouse.name)
        .all()
    )

    return [
        {
            "warehouse_id": row.id,
            "warehouse_name": row.name,
            "stock_value": float(row.stock_value or 0),
        }
        for row in rows
    ]


@router.get("/low-stock")
def low_stock_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_report_role(current_user)

    rows = (
        db.query(Inventory, Product, Supplier)
        .join(Product, Product.id == Inventory.product_id)
        .outerjoin(
            Supplier,
            Supplier.id == Product.preferred_supplier_id,
        )
        .filter(
            Product.is_active == True,
            Inventory.quantity_available <= Product.reorder_level,
        )
        .all()
    )

    return [
        {
            "product_id": product.id,
            "product_name": product.name,
            "sku": product.sku,
            "warehouse_id": inventory.warehouse_id,
            "quantity_available": inventory.quantity_available,
            "reorder_level": product.reorder_level,
            "suggested_reorder_quantity": product.reorder_quantity,
            "preferred_supplier": supplier.name if supplier else None,
        }
        for inventory, product, supplier in rows
    ]


@router.get("/sales")
def sales_report(
    start_date: datetime,
    end_date: datetime,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_report_role(current_user)

    sales_count = (
        db.query(SalesOrder)
        .filter(
            SalesOrder.created_at >= start_date,
            SalesOrder.created_at <= end_date,
            SalesOrder.status != "Cancelled",
        )
        .count()
    )

    revenue = (
        db.query(func.coalesce(func.sum(SalesOrder.grand_total), 0))
        .filter(
            SalesOrder.created_at >= start_date,
            SalesOrder.created_at <= end_date,
            SalesOrder.status != "Cancelled",
        )
        .scalar()
    )

    returns = (
        db.query(func.coalesce(func.sum(ReturnRequest.refund_amount), 0))
        .filter(
            ReturnRequest.created_at >= start_date,
            ReturnRequest.created_at <= end_date,
        )
        .scalar()
    )

    return {
        "start_date": start_date,
        "end_date": end_date,
        "sales_count": sales_count,
        "revenue": float(revenue or 0),
        "returns": float(returns or 0),
    }


@router.get("/top-products")
def top_products_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_report_role(current_user)

    rows = (
        db.query(
            Product.id,
            Product.name,
            Product.sku,
            func.sum(SalesOrderItem.quantity).label("quantity_sold"),
        )
        .join(
            SalesOrderItem,
            SalesOrderItem.product_id == Product.id,
        )
        .join(
            SalesOrder,
            SalesOrder.id == SalesOrderItem.sales_order_id,
        )
        .filter(SalesOrder.status != "Cancelled")
        .group_by(Product.id, Product.name, Product.sku)
        .order_by(func.sum(SalesOrderItem.quantity).desc())
        .limit(10)
        .all()
    )

    return [
        {
            "product_id": row.id,
            "product_name": row.name,
            "sku": row.sku,
            "quantity_sold": int(row.quantity_sold or 0),
        }
        for row in rows
    ]


@router.get("/dead-stock")
def dead_stock_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_report_role(current_user)

    cutoff_date = datetime.utcnow() - timedelta(days=90)

    sold_product_ids = (
        db.query(SalesOrderItem.product_id)
        .join(
            SalesOrder,
            SalesOrder.id == SalesOrderItem.sales_order_id,
        )
        .filter(
            SalesOrder.created_at >= cutoff_date,
            SalesOrder.status != "Cancelled",
        )
        .distinct()
        .subquery()
    )

    products = (
        db.query(Product)
        .filter(
            Product.is_active == True,
            ~Product.id.in_(sold_product_ids),
        )
        .all()
    )

    return [
        {
            "product_id": product.id,
            "product_name": product.name,
            "sku": product.sku,
        }
        for product in products
    ]


@router.get("/supplier-performance")
def supplier_performance_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_report_role(current_user)

    suppliers = db.query(Supplier).all()

    result = []

    for supplier in suppliers:
        orders = (
            db.query(PurchaseOrder)
            .filter(
                PurchaseOrder.supplier_id == supplier.id,
                PurchaseOrder.status == "Received",
            )
            .all()
        )

        if not orders:
            percentage = 0
        else:
            on_time = 0

            for order in orders:
                if (
                    order.received_at
                    and order.expected_delivery_date
                    and order.received_at <= order.expected_delivery_date
                ):
                    on_time += 1

            percentage = round((on_time / len(orders)) * 100, 2)

        result.append(
            {
                "supplier_id": supplier.id,
                "supplier_name": supplier.name,
                "total_received_orders": len(orders),
                "on_time_delivery_percentage": percentage,
            }
        )

    return result