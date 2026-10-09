# Smart Inventory & Warehouse Management System

A backend inventory and warehouse management system built using FastAPI and SQLAlchemy. The system manages products, warehouses, inventory, suppliers, customers, purchase orders, sales orders, returns, stock movements, audit logs, reports, stock transfers, stock adjustments, and Excel export.

## 🚀 Technologies Used

- Python 3.9+
- FastAPI
- SQLAlchemy
- MySQL
- Pydantic
- JWT Authentication
- Alembic
- Uvicorn
- OpenPyXL
- Swagger UI

## 📌 Main Features

### Authentication
- User registration
- User login
- JWT authentication
- Current user information
- Role-based access control

### Product Management
- Create products
- View products
- Search products by name/SKU
- Pagination
- SKU uniqueness validation
- Price and quantity validation
- Product activation/deactivation

### Category Management
- Create categories
- Update categories
- Delete categories
- Category validation

### Warehouse Management
- Create warehouses
- View warehouses
- Update warehouses
- Activate/deactivate warehouses
- Warehouse code validation

### Inventory Management
- View inventory
- Stock In
- Stock Out
- Stock movement tracking
- Search/filtering
- Pagination

### Supplier Management
- Supplier CRUD operations
- Supplier code uniqueness
- Email validation
- Phone validation
- GST validation

### Customer Management
- Customer CRUD operations
- Customer code uniqueness
- Email validation
- Phone validation

### Purchase Orders
- Create purchase orders
- View purchase orders
- Search/filter purchase orders
- Receive purchase orders
- Quantity and price validation
- Duplicate PO validation

### Sales Orders
- Create sales orders
- Confirm orders
- Pick orders
- Pack orders
- Dispatch orders
- Deliver orders
- Tracking number validation
- Stock availability validation

### Returns
- Create returns
- View returns
- Inspect returns
- Approve returns
- Return quantity validation

### Audit Logs
- Track system activities
- Filter by action
- Filter by entity type

### Reports
- Dashboard
- Stock valuation
- Low-stock report
- Sales report
- Top products
- Dead-stock report
- Supplier performance

## ⭐ Bonus Features Implemented

### Stock Transfers
- Create stock transfer
- Dispatch transfer
- Receive transfer
- Cancel transfer
- Transfer status workflow:
  - Pending
  - In Transit
  - Received
  - Cancelled

### Stock Adjustments
- Create stock adjustment
- Approve adjustment
- Reject adjustment
- Supported reasons:
  - Damaged
  - Lost
  - Expired
  - Found
  - Count Correction
- Stock is updated only after approval

### Excel Export
- Export products to Excel
- Generates `.xlsx` file using OpenPyXL

## 🔐 Validation

The system includes validation for:

- Unique SKU
- Unique warehouse code
- Unique supplier code
- Unique customer code
- Unique email
- Unique PO number
- Unique SO number
- Unique tracking number
- Positive quantities
- Positive prices
- 10-digit phone numbers
- 15-character GST numbers
- Required fields
- Proper HTTP status codes

## 📂 Project Structure

```text
Smart_Inventory_Warehouse_Management_System/
│
├── app/
│   ├── models/
│   ├── routers/
│   ├── schemas/
│   ├── services/
│   ├── database.py
│   └── main.py
│
├── alembic/
├── tests/
├── screenshots/
├── .env.example
├── .gitignore
├── alembic.ini
├── requirements.txt
└── README.md
