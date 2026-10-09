from decimal import Decimal

from pydantic import BaseModel, EmailStr, ConfigDict, Field


class CustomerCreate(BaseModel):
    customer_code: str
    name: str
    email: EmailStr
    phone: str = Field(pattern=r"^[0-9]{10}$")
    address: str | None = None
    credit_limit: Decimal = Decimal("0")


class CustomerResponse(BaseModel):
    id: int
    customer_code: str
    name: str
    email: str
    phone: str
    address: str | None
    credit_limit: Decimal
    is_active: bool

    model_config = ConfigDict(from_attributes=True)