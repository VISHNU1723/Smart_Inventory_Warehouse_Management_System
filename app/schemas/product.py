from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    name: str
    sku: str
    description: str | None = None
    price: float = Field(gt=0)
    quantity: int = Field(gt=0)
    category_id: int


class ProductResponse(BaseModel):
    id: int
    name: str
    sku: str
    description: str | None
    price: float | None = None
    quantity: int | None = None
    category_id: int
    is_active: bool

    class Config:
        from_attributes = True