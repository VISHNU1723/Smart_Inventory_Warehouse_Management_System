from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.inventory import Supplier
from app.schemas.supplier import SupplierCreate, SupplierResponse
from app.auth.dependencies import get_current_user
from app.models.user import User

router = APIRouter(
    prefix="/suppliers",
    tags=["Suppliers"]
)


# CREATE SUPPLIER
@router.post("/", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
def create_supplier(
    data: SupplierCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "Admin":
        raise HTTPException(
            status_code=403,
            detail="Only Admin can create suppliers"
        )

    existing = db.query(Supplier).filter(
        (Supplier.supplier_code == data.supplier_code) |
        (Supplier.email == data.email) |
        (Supplier.gst_number == data.gst_number)
    ).first()

    if existing:
        raise HTTPException(
           status_code=409,
           detail="Supplier code, email, or GST number already exists"
        )

    supplier = Supplier(
        supplier_code=data.supplier_code,
        name=data.name,
        email=data.email,
        phone=data.phone,
        gst_number=data.gst_number,
        address=data.address,
        lead_time_days=data.lead_time_days,
        is_active=True,
        created_by=current_user.id
    )

    db.add(supplier)
    db.commit()
    db.refresh(supplier)

    return supplier


# GET ALL SUPPLIERS
@router.get("/", response_model=list[SupplierResponse])
def get_suppliers(
    db: Session = Depends(get_db)
):
    return db.query(Supplier).all()


# GET SUPPLIER BY ID
@router.get("/{supplier_id}", response_model=SupplierResponse)
def get_supplier(
    supplier_id: int,
    db: Session = Depends(get_db)
):
    supplier = db.query(Supplier).filter(
        Supplier.id == supplier_id
    ).first()

    if supplier is None:
        raise HTTPException(
            status_code=404,
            detail="Supplier not found"
        )

    return supplier


# UPDATE SUPPLIER
@router.put("/{supplier_id}", response_model=SupplierResponse)
def update_supplier(
    supplier_id: int,
    data: SupplierCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "Admin":
        raise HTTPException(
            status_code=403,
            detail="Only Admin can update suppliers"
        )

    supplier = db.query(Supplier).filter(
        Supplier.id == supplier_id
    ).first()

    if supplier is None:
        raise HTTPException(
            status_code=404,
            detail="Supplier not found"
        )

    supplier.supplier_code = data.supplier_code
    supplier.name = data.name
    supplier.email = data.email
    supplier.phone = data.phone
    supplier.gst_number = data.gst_number
    supplier.address = data.address
    supplier.lead_time_days = data.lead_time_days

    db.commit()
    db.refresh(supplier)

    return supplier


# DELETE / DEACTIVATE SUPPLIER
@router.delete("/{supplier_id}")
def delete_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "Admin":
        raise HTTPException(
            status_code=403,
            detail="Only Admin can delete suppliers"
        )

    supplier = db.query(Supplier).filter(
        Supplier.id == supplier_id
    ).first()

    if supplier is None:
        raise HTTPException(
            status_code=404,
            detail="Supplier not found"
        )

    supplier.is_active = False

    db.commit()

    return {
        "message": "Supplier deactivated successfully"
    }