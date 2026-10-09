from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class PurchaseOrderItemCreate(BaseModel):
    product_id: int
    quantity_ordered: int = Field(gt=0)
    dunit_cost: Decimal = Field(gt=0)


class PurchaseOrderCreate(BaseModel):
    po_number: str
    supplier_id: int
    warehouse_id: int
    expected_delivery_date: datetime | None = None
    items: list[PurchaseOrderItemCreate]


class PurchaseOrderItemResponse(BaseModel):
    id: int
    product_id: int
    quantity_ordered: int
    quantity_received: int
    unit_cost: Decimal

    class Config:
        from_attributes = True


class PurchaseOrderResponse(BaseModel):
    id: int
    po_number: str
    supplier_id: int
    warehouse_id: int
    expected_delivery_date: datetime | None
    received_at: datetime | None
    total_amount: Decimal
    status: str

    class Config:
        from_attributes = True