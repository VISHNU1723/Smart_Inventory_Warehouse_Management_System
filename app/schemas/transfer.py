from datetime import datetime
from pydantic import BaseModel, Field


class TransferCreate(BaseModel):
    product_id: int
    source_warehouse_id: int
    destination_warehouse_id: int
    quantity: int = Field(gt=0)


class TransferResponse(BaseModel):
    id: int
    product_id: int
    source_warehouse_id: int
    destination_warehouse_id: int
    quantity: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True