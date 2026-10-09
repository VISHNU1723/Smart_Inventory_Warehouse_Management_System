from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.inventory import Inventory, StockMovement
from app.models.inventory import Warehouse
from app.models.product import Product
from app.models.transfer import StockTransfer
from app.schemas.transfer import TransferCreate, TransferResponse


router = APIRouter(
    prefix="/transfers",
    tags=["Stock Transfers"]
)


@router.post("/", response_model=TransferResponse, status_code=201)
def create_transfer(
    data: TransferCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["Admin", "Inventory Manager", "Warehouse Staff"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    if data.source_warehouse_id == data.destination_warehouse_id:
        raise HTTPException(
            status_code=400,
            detail="Source and destination warehouses must be different"
        )

    product = db.query(Product).filter(
        Product.id == data.product_id
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    source = db.query(Warehouse).filter(
        Warehouse.id == data.source_warehouse_id
    ).first()

    destination = db.query(Warehouse).filter(
        Warehouse.id == data.destination_warehouse_id
    ).first()

    if not source or not destination:
        raise HTTPException(status_code=404, detail="Warehouse not found")

    if not source.is_active or not destination.is_active:
        raise HTTPException(status_code=400, detail="Warehouse is inactive")

    inventory = db.query(Inventory).filter(
        Inventory.product_id == data.product_id,
        Inventory.warehouse_id == data.source_warehouse_id
    ).first()

    if not inventory:
        raise HTTPException(
            status_code=400,
            detail="Source inventory not found"
        )

    available = inventory.quantity_on_hand - inventory.quantity_reserved

    if data.quantity > available:
        raise HTTPException(
            status_code=400,
            detail="Insufficient stock in source warehouse"
        )

    transfer = StockTransfer(
        product_id=data.product_id,
        source_warehouse_id=data.source_warehouse_id,
        destination_warehouse_id=data.destination_warehouse_id,
        quantity=data.quantity,
        status="Pending"
    )

    db.add(transfer)
    db.commit()
    db.refresh(transfer)

    return transfer


@router.get("/", response_model=list[TransferResponse])
def get_transfers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(StockTransfer).order_by(
        StockTransfer.id.desc()
    ).all()


@router.put("/{transfer_id}/dispatch", response_model=TransferResponse)
def dispatch_transfer(
    transfer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    transfer = db.query(StockTransfer).filter(
        StockTransfer.id == transfer_id
    ).first()

    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")

    if transfer.status != "Pending":
        raise HTTPException(
            status_code=400,
            detail="Only Pending transfers can be dispatched"
        )

    inventory = db.query(Inventory).filter(
        Inventory.product_id == transfer.product_id,
        Inventory.warehouse_id == transfer.source_warehouse_id
    ).first()

    if not inventory:
        raise HTTPException(status_code=400, detail="Source inventory not found")

    available = inventory.quantity_on_hand - inventory.quantity_reserved

    if transfer.quantity > available:
        raise HTTPException(status_code=400, detail="Insufficient stock")

    inventory.quantity_on_hand -= transfer.quantity

    db.add(StockMovement(
        product_id=transfer.product_id,
        warehouse_id=transfer.source_warehouse_id,
        movement_type="Transfer Out",
        quantity=transfer.quantity,
        balance_after=inventory.quantity_on_hand,
        reference_id=transfer.id,
        performed_by=current_user.id
    ))

    transfer.status = "In Transit"

    db.commit()
    db.refresh(transfer)

    return transfer


@router.put("/{transfer_id}/receive", response_model=TransferResponse)
def receive_transfer(
    transfer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    transfer = db.query(StockTransfer).filter(
        StockTransfer.id == transfer_id
    ).first()

    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")

    if transfer.status != "In Transit":
        raise HTTPException(
            status_code=400,
            detail="Only In Transit transfers can be received"
        )

    inventory = db.query(Inventory).filter(
        Inventory.product_id == transfer.product_id,
        Inventory.warehouse_id == transfer.destination_warehouse_id
    ).first()

    if not inventory:
        inventory = Inventory(
            product_id=transfer.product_id,
            warehouse_id=transfer.destination_warehouse_id,
            quantity_on_hand=0,
            quantity_reserved=0
        )
        db.add(inventory)
        db.flush()

    inventory.quantity_on_hand += transfer.quantity

    db.add(StockMovement(
        product_id=transfer.product_id,
        warehouse_id=transfer.destination_warehouse_id,
        movement_type="Transfer In",
        quantity=transfer.quantity,
        balance_after=inventory.quantity_on_hand,
        reference_id=transfer.id,
        performed_by=current_user.id
    ))

    transfer.status = "Received"

    db.commit()
    db.refresh(transfer)

    return transfer


@router.put("/{transfer_id}/cancel", response_model=TransferResponse)
def cancel_transfer(
    transfer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    transfer = db.query(StockTransfer).filter(
        StockTransfer.id == transfer_id
    ).first()

    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")

    if transfer.status not in ["Pending", "In Transit"]:
        raise HTTPException(
            status_code=400,
            detail="Transfer cannot be cancelled"
        )

    if transfer.status == "In Transit":
        inventory = db.query(Inventory).filter(
            Inventory.product_id == transfer.product_id,
            Inventory.warehouse_id == transfer.source_warehouse_id
        ).first()

        if inventory:
            inventory.quantity_on_hand += transfer.quantity

    transfer.status = "Cancelled"

    db.commit()
    db.refresh(transfer)

    return transfer