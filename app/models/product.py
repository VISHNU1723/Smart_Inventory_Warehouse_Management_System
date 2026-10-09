from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(150), nullable=False, index=True)

    sku = Column(String(100), unique=True, nullable=False, index=True)

    description = Column(String(500), nullable=True)

    barcode = Column(String(100), unique=True, nullable=True)

    category_id = Column(
        Integer,
        ForeignKey("categories.id"),
        nullable=False,
        index=True,
    )

    unit = Column(String(30), nullable=False)

    cost_price = Column(Numeric(12, 2), nullable=False)

    selling_price = Column(Numeric(12, 2), nullable=False)

    reorder_level = Column(Integer, nullable=False)

    reorder_quantity = Column(Integer, nullable=False)

    preferred_supplier_id = Column(
        Integer,
        ForeignKey("suppliers.id"),
        nullable=True,
        index=True,
    )

    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    created_by = Column(
        Integer,
        nullable=True,
    )

    # Category relationship
    category = relationship(
        "Category",
        back_populates="products",
    )

    # Preferred supplier relationship
    preferred_supplier = relationship(
        "Supplier",
        back_populates="products",
    )

    # Inventory relationship
    inventory = relationship(
        "Inventory",
        back_populates="product",
    )

    # Stock movement relationship
    stock_movements = relationship(
        "StockMovement",
        back_populates="product",
    )