from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field
from typing import List, Optional


class SalesOrderItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(gt=0)


class SalesOrderCreate(BaseModel):
    so_number: str
    customer_id: int
    warehouse_id: int
    items: List[SalesOrderItemCreate]


class SalesOrderResponse(BaseModel):
    id: int
    so_number: str
    customer_id: int
    warehouse_id: int
    subtotal: Decimal
    tax_amount: Decimal
    grand_total: Decimal
    status: str
    courier_name: Optional[str] = None
    tracking_number: Optional[str] = None
    dispatched_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None

    class Config:
        from_attributes = True