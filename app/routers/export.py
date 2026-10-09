from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO
from openpyxl import Workbook

from app.database import get_db
from app.models.product import Product

router = APIRouter(prefix="/export", tags=["Export"])


@router.get("/products")
def export_products(db: Session = Depends(get_db)):
    products = db.query(Product).all()

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Products"

    sheet.append([
        "ID",
        "Name",
        "SKU",
        "Barcode",
        "Description",
        "Unit",
        "Cost Price",
        "Selling Price",
        "Reorder Level",
        "Reorder Quantity",
        "Category ID",
        "Supplier ID",
        "Active",
    ])

    for product in products:
        sheet.append([
            product.id,
            product.name,
            product.sku,
            product.barcode,
            product.description,
            product.unit,
            product.cost_price,
            product.selling_price,
            product.reorder_level,
            product.reorder_quantity,
            product.category_id,
            product.preferred_supplier_id,
            product.is_active,
        ])

    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=products.xlsx"
        },
    )