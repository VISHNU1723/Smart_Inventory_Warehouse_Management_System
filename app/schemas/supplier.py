from pydantic import BaseModel, EmailStr, Field


class SupplierCreate(BaseModel):
    supplier_code: str
    name: str
    email: EmailStr
    phone: str = Field(pattern=r"^[0-9]{10}$")
    gst_number: str | None = Field(
    default=None,
    min_length=15,
    max_length=15
)
    address: str | None = None
    lead_time_days: int = 0


class SupplierResponse(BaseModel):
    id: int
    supplier_code: str
    name: str
    email: str
    phone: str
    gst_number: str | None
    address: str | None
    lead_time_days: int
    is_active: bool

    class Config:
        from_attributes = True