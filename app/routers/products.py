from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductResponse
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.inventory import Inventory


router = APIRouter(
    prefix="/products",
    tags=["Products"],
)


def product_response(product):
    return {
        "id": product.id,
        "name": product.name,
        "sku": product.sku,
        "description": product.description,
        "price": product.selling_price,
        "quantity": product.reorder_quantity,
        "category_id": product.category_id,
        "is_active": product.is_active,
    }


@router.post(
    "/",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_product(
    data: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "Admin":
        raise HTTPException(
            status_code=403,
            detail="Only Admin can create products",
        )

    existing_product = db.query(Product).filter(
        Product.sku == data.sku
    ).first()

    if existing_product:
        raise HTTPException(
            status_code=409,
            detail="Product SKU already exists",
        )

    product = Product(
        name=data.name,
        sku=data.sku,
        description=data.description,
        barcode=None,
        category_id=data.category_id,
        unit="piece",
        cost_price=data.price,
        selling_price=data.price,
        reorder_level=5,
        reorder_quantity=data.quantity,
        preferred_supplier_id=None,
        is_active=True,
        created_by=current_user.id,
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    return product_response(product)


@router.get("/", response_model=list[ProductResponse])
def get_products(
    search: str | None = Query(None, description="Search by product name or SKU"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Product)

    if search:
        search_value = f"%{search}%"
        query = query.filter(
            (Product.name.ilike(search_value)) |
            (Product.sku.ilike(search_value))
        )

    products = (
        query
        .offset(skip)
        .limit(limit)
        .all()
    )

    return [product_response(product) for product in products]

@router.get(
    "/{product_id}",
    response_model=ProductResponse,
)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(
        Product.id == product_id
    ).first()

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found",
        )

    return product_response(product)

@router.put(
    "/{product_id}",
    response_model=ProductResponse,
)
def update_product(
    product_id: int,
    data: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ["Admin", "Inventory Manager"]:
        raise HTTPException(
            status_code=403,
            detail="Only Admin or Inventory Manager can update products",
        )

    product = db.query(Product).filter(
        Product.id == product_id
    ).first()

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found",
        )

    duplicate = db.query(Product).filter(
        Product.sku == data.sku,
        Product.id != product_id
    ).first()

    if duplicate:
        raise HTTPException(
            status_code=409,
            detail="Product SKU already exists",
        )

    product.name = data.name
    product.sku = data.sku
    product.description = data.description
    product.category_id = data.category_id
    product.cost_price = data.price
    product.selling_price = data.price
    product.reorder_quantity = data.quantity

    db.commit()
    db.refresh(product)

    return product_response(product)


@router.delete(
    "/{product_id}",
    response_model=ProductResponse,
)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ["Admin", "Inventory Manager"]:
        raise HTTPException(
            status_code=403,
            detail="Only Admin or Inventory Manager can delete products",
        )

    product = db.query(Product).filter(
        Product.id == product_id
    ).first()

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found",
        )

    stock = db.query(Inventory).filter(
        Inventory.product_id == product_id,
        Inventory.quantity_on_hand > 0
    ).first()

    if stock:
        raise HTTPException(
            status_code=400,
            detail="Cannot deactivate product while stock exists",
        )

    product.is_active = False

    db.commit()
    db.refresh(product)

    return product_response(product)