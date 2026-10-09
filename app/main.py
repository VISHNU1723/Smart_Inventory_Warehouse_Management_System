from fastapi import FastAPI

from app.routers.auth import router as auth_router
from app.routers.products import router as products_router
from app.routers.categories import router as categories_router
from app.routers.warehouse import router as warehouse_router
from app.routers.inventory import router as inventory_router
from app.routers.suppliers import router as suppliers_router
from app.routers.purchase_orders import router as purchase_orders_router
from app.routers.customers import router as customers_router
from app.routers.sales_orders import router as sales_orders_router
from app.routers.returns import router as returns_router
from app.routers.audit import router as audit_router
from app.routers.notifications import router as notifications_router
from app.routers.customers import router as customers_router
from app.routers.reports import router as reports_router
from app.routers.transfers import router as transfers_router
from app.routers.adjustments import router as adjustments_router
from app.routers.export import router as export_router


app = FastAPI(
    title="Smart Inventory & Warehouse Management System",
    version="1.0.0",
)


app.include_router(auth_router)
app.include_router(products_router)
app.include_router(categories_router)
app.include_router(warehouse_router)
app.include_router(inventory_router)
app.include_router(suppliers_router)
app.include_router(purchase_orders_router)
app.include_router(customers_router)
app.include_router(sales_orders_router)
app.include_router(returns_router)
app.include_router(audit_router)
app.include_router(notifications_router)
app.include_router(reports_router)
app.include_router(transfers_router)
app.include_router(adjustments_router)
app.include_router(export_router)

@app.get("/")
def root():
    return {
        "message": "Smart Inventory & Warehouse Management System API"
    }