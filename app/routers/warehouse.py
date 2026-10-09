from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.inventory import Warehouse

router = APIRouter(
    prefix="/warehouses",
    tags=["Warehouses"]
)


# CREATE WAREHOUSE
@router.post("/", status_code=status.HTTP_201_CREATED)
def create_warehouse(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "Admin":
        raise HTTPException(
            status_code=403,
            detail="Only Admin can create warehouses"
        )

    existing = db.query(Warehouse).filter(
        Warehouse.warehouse_code == data.get("warehouse_code")
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Warehouse code already exists"
        )

    warehouse = Warehouse(
        warehouse_code=data.get("warehouse_code"),
        name=data.get("name"),
        city=data.get("city"),
        address=data.get("address"),
        capacity=data.get("capacity"),
        manager_id=data.get("manager_id"),
        is_active=True,
        created_by=current_user.id
    )

    db.add(warehouse)
    db.commit()
    db.refresh(warehouse)

    return warehouse


# GET ALL WAREHOUSES
@router.get("/")
def get_warehouses(
    db: Session = Depends(get_db)
):
    return db.query(Warehouse).all()


# GET WAREHOUSE BY ID
@router.get("/{warehouse_id}")
def get_warehouse(
    warehouse_id: int,
    db: Session = Depends(get_db)
):
    warehouse = db.query(Warehouse).filter(
        Warehouse.id == warehouse_id
    ).first()

    if warehouse is None:
        raise HTTPException(
            status_code=404,
            detail="Warehouse not found"
        )

    return warehouse


# UPDATE WAREHOUSE
@router.put("/{warehouse_id}")
def update_warehouse(
    warehouse_id: int,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "Admin":
        raise HTTPException(
            status_code=403,
            detail="Only Admin can update warehouses"
        )

    warehouse = db.query(Warehouse).filter(
        Warehouse.id == warehouse_id
    ).first()

    if warehouse is None:
        raise HTTPException(
            status_code=404,
            detail="Warehouse not found"
        )

    if "warehouse_code" in data:
        warehouse.warehouse_code = data["warehouse_code"]

    if "name" in data:
        warehouse.name = data["name"]

    if "city" in data:
        warehouse.city = data["city"]

    if "address" in data:
        warehouse.address = data["address"]

    if "capacity" in data:
        warehouse.capacity = data["capacity"]

    if "manager_id" in data:
        warehouse.manager_id = data["manager_id"]

    if "is_active" in data:
        warehouse.is_active = data["is_active"]

    db.commit()
    db.refresh(warehouse)

    return warehouse


# DELETE / DEACTIVATE WAREHOUSE
@router.delete("/{warehouse_id}")
def delete_warehouse(
    warehouse_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "Admin":
        raise HTTPException(
            status_code=403,
            detail="Only Admin can delete warehouses"
        )

    warehouse = db.query(Warehouse).filter(
        Warehouse.id == warehouse_id
    ).first()

    if warehouse is None:
        raise HTTPException(
            status_code=404,
            detail="Warehouse not found"
        )

    # Warehouse cannot be deleted if it contains stock
    total_stock = sum(
        item.quantity_on_hand
        for item in warehouse.inventory
    )

    if total_stock > 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete warehouse because it contains stock"
        )

    warehouse.is_active = False

    db.commit()

    return {
        "message": "Warehouse deactivated successfully"
    }


# GET WAREHOUSE INVENTORY
@router.get("/{warehouse_id}/inventory")
def get_warehouse_inventory(
    warehouse_id: int,
    db: Session = Depends(get_db)
):
    warehouse = db.query(Warehouse).filter(
        Warehouse.id == warehouse_id
    ).first()

    if warehouse is None:
        raise HTTPException(
            status_code=404,
            detail="Warehouse not found"
        )

    return warehouse.inventory