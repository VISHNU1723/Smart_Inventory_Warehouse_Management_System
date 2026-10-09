from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.orders import Customer
from app.schemas.customer import CustomerCreate, CustomerResponse
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.services.audit_service import create_audit_log


router = APIRouter(
    prefix="/customers",
    tags=["Customers"],
)


@router.post(
    "/",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_customer(
    data: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ["Admin", "Inventory Manager"]:
        raise HTTPException(
            status_code=403,
            detail="Only Admin or Inventory Manager can create customers",
        )

    existing = db.query(Customer).filter(
        (Customer.customer_code == data.customer_code) |
        (Customer.email == data.email)
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Customer code or email already exists",
        )

    customer = Customer(
        customer_code=data.customer_code,
        name=data.name,
        email=data.email,
        phone=data.phone,
        address=data.address,
        credit_limit=data.credit_limit,
        is_active=True,
        created_by=current_user.id,
    )

    db.add(customer)
    db.commit()
    db.refresh(customer)

    create_audit_log(
        db=db,
        user_id=current_user.id,
        action="CREATE",
        entity_type="Customer",
        entity_id=customer.id,
        new_value={
            "customer_code": customer.customer_code,
            "name": customer.name,
            "email": customer.email,
            "credit_limit": str(customer.credit_limit),
    },
)

    db.commit()

    return customer


@router.get(
    "/",
    response_model=list[CustomerResponse],
)
def get_customers(
    db: Session = Depends(get_db),
):
    return db.query(Customer).all()


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
):
    customer = db.query(Customer).filter(
        Customer.id == customer_id
    ).first()

    if customer is None:
        raise HTTPException(
            status_code=404,
            detail="Customer not found",
        )

    return customer


@router.put(
    "/{customer_id}",
    response_model=CustomerResponse,
)
def update_customer(
    customer_id: int,
    data: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ["Admin", "Inventory Manager"]:
        raise HTTPException(
            status_code=403,
            detail="Only Admin or Inventory Manager can update customers",
        )

    customer = db.query(Customer).filter(
        Customer.id == customer_id
    ).first()

    if customer is None:
        raise HTTPException(
            status_code=404,
            detail="Customer not found",
        )

    customer.customer_code = data.customer_code
    customer.name = data.name
    customer.email = data.email
    customer.phone = data.phone
    customer.address = data.address
    customer.credit_limit = data.credit_limit

    db.commit()
    db.refresh(customer)

    return customer