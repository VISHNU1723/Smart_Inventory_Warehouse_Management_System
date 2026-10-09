from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, index=True)
    po_number = Column(String(50), unique=True, nullable=False, index=True)

    supplier_id = Column(
        Integer,
        ForeignKey("suppliers.id"),
        nullable=False,
    )

    warehouse_id = Column(
        Integer,
        ForeignKey("warehouses.id"),
        nullable=False,
    )

    expected_delivery_date = Column(DateTime, nullable=True)
    received_at = Column(DateTime, nullable=True)

    total_amount = Column(Numeric(12, 2), default=0, nullable=False)
    status = Column(String(50), default="Draft", nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    created_by = Column(Integer, nullable=True)

    supplier = relationship(
        "Supplier",
        back_populates="purchase_orders",
    )

    warehouse = relationship(
        "Warehouse",
        back_populates="purchase_orders",
    )

    items = relationship(
        "PurchaseOrderItem",
        back_populates="purchase_order",
        cascade="all, delete-orphan",
    )


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id = Column(Integer, primary_key=True, index=True)

    purchase_order_id = Column(
        Integer,
        ForeignKey("purchase_orders.id"),
        nullable=False,
    )

    product_id = Column(
        Integer,
        ForeignKey("products.id"),
        nullable=False,
    )

    quantity_ordered = Column(Integer, nullable=False)
    quantity_received = Column(Integer, default=0, nullable=False)
    unit_cost = Column(Numeric(12, 2), nullable=False)

    purchase_order = relationship(
        "PurchaseOrder",
        back_populates="items",
    )

    product = relationship("Product")


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    customer_code = Column(String(50), unique=True, nullable=False)
    name = Column(String(150), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    phone = Column(String(20), nullable=False)
    address = Column(Text, nullable=True)
    credit_limit = Column(Numeric(12, 2), default=0, nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    created_by = Column(Integer, nullable=True)

    sales_orders = relationship(
        "SalesOrder",
        back_populates="customer",
    )


class SalesOrder(Base):
    __tablename__ = "sales_orders"

    id = Column(Integer, primary_key=True, index=True)
    so_number = Column(String(50), unique=True, nullable=False, index=True)

    customer_id = Column(
        Integer,
        ForeignKey("customers.id"),
        nullable=False,
    )

    warehouse_id = Column(
        Integer,
        ForeignKey("warehouses.id"),
        nullable=False,
    )

    subtotal = Column(Numeric(12, 2), default=0, nullable=False)
    tax_amount = Column(Numeric(12, 2), default=0, nullable=False)
    grand_total = Column(Numeric(12, 2), default=0, nullable=False)

    status = Column(String(50), default="Draft", nullable=False)

    courier_name = Column(String(100), nullable=True)
    tracking_number = Column(String(100), unique=True, nullable=True)

    dispatched_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    created_by = Column(Integer, nullable=True)

    customer = relationship(
        "Customer",
        back_populates="sales_orders",
    )

    warehouse = relationship(
        "Warehouse",
        back_populates="sales_orders",
    )

    items = relationship(
        "SalesOrderItem",
        back_populates="sales_order",
        cascade="all, delete-orphan",
    )

    returns = relationship(
        "ReturnRequest",
        back_populates="sales_order",
        cascade="all, delete-orphan",
    )


class SalesOrderItem(Base):
    __tablename__ = "sales_order_items"

    id = Column(Integer, primary_key=True, index=True)

    sales_order_id = Column(
        Integer,
        ForeignKey("sales_orders.id"),
        nullable=False,
    )

    product_id = Column(
        Integer,
        ForeignKey("products.id"),
        nullable=False,
    )

    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=False)
    line_total = Column(Numeric(12, 2), nullable=False)

    sales_order = relationship(
        "SalesOrder",
        back_populates="items",
    )

    product = relationship("Product")


class ReturnRequest(Base):
    __tablename__ = "returns"

    id = Column(Integer, primary_key=True, index=True)

    so_id = Column(
        Integer,
        ForeignKey("sales_orders.id"),
        nullable=False,
    )

    reason = Column(Text, nullable=False)
    condition = Column(String(30), nullable=True)
    status = Column(
        String(30),
        default="Requested",
        nullable=False,
    )

    refund_amount = Column(
        Numeric(12, 2),
        default=0,
        nullable=False,
    )

    rejection_reason = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    created_by = Column(Integer, nullable=True)

    sales_order = relationship(
        "SalesOrder",
        back_populates="returns",
    )

    items = relationship(
        "ReturnItem",
        back_populates="return_request",
        cascade="all, delete-orphan",
    )


class ReturnItem(Base):
    __tablename__ = "return_items"

    id = Column(Integer, primary_key=True, index=True)

    return_id = Column(
        Integer,
        ForeignKey("returns.id"),
        nullable=False,
    )

    product_id = Column(
        Integer,
        ForeignKey("products.id"),
        nullable=False,
    )

    quantity = Column(Integer, nullable=False)
    condition = Column(String(30), nullable=True)

    return_request = relationship(
        "ReturnRequest",
        back_populates="items",
    )

    product = relationship("Product")