from decimal import Decimal
from pydantic import BaseModel, Field
from typing import List, Optional


class ReturnItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class ReturnCreate(BaseModel):
    items: List[ReturnItemCreate]
    reason: str
    condition: Optional[str] = None


class ReturnItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    condition: Optional[str] = None

    class Config:
        from_attributes = True


class ReturnResponse(BaseModel):
    id: int
    so_id: int
    reason: str
    condition: Optional[str] = None
    status: str
    refund_amount: Decimal
    rejection_reason: Optional[str] = None

    class Config:
        from_attributes = True