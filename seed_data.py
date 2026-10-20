"""seed_data.py — Pydantic-validated synthetic dataset generator and populator."""

import json
from decimal import Decimal
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

from models import LineItem, InvoiceSeed

load_dotenv()

CUSTOMERS_DATA = [
    {
        "customer_id": "CUST-101",
        "name": "Aarav Sharma",
        "email": "aarav.sharma@example.com",
        "phone": "+91-9876543210",
        "city": "Mumbai",
    },
    {
        "customer_id": "CUST-102",
        "name": "Priya Patel",
        "email": "priya.patel@example.com",
        "phone": "+91-9876543211",
        "city": "Bengaluru",
    },
    {
        "customer_id": "CUST-103",
        "name": "Rohan Verma",
        "email": "rohan.verma@example.com",
        "phone": "+91-9876543212",
        "city": "Delhi",
    },
    {
        "customer_id": "CUST-104",
        "name": "Sneha Reddy",
        "email": "sneha.reddy@example.com",
        "phone": "+91-9876543213",
        "city": "Hyderabad",
    },
    {
        "customer_id": "CUST-105",
        "name": "Vikram Malhotra",
        "email": "vikram.m@example.com",
        "phone": "+91-9876543214",
        "city": "Pune",
    },
    {
        "customer_id": "CUST-106",
        "name": "Ananya Iyer",
        "email": "ananya.iyer@example.com",
        "phone": "+91-9876543215",
        "city": "Chennai",
    },
    {
        "customer_id": "CUST-107",
        "name": "Rajesh Gupta",
        "email": "rajesh.gupta@example.com",
        "phone": "+91-9876543216",
        "city": "Kolkata",
    },
    {
        "customer_id": "CUST-108",
        "name": "Meera Nair",
        "email": "meera.nair@example.com",
        "phone": "+91-9876543217",
        "city": "Kochi",
    },
    {
        "customer_id": "CUST-109",
        "name": "Arjun Singh",
        "email": "arjun.singh@example.com",
        "phone": "+91-9876543218",
        "city": "Jaipur",
    },
    {
        "customer_id": "CUST-110",
        "name": "Pooja Joshi",
        "email": "pooja.joshi@example.com",
        "phone": "+91-9876543219",
        "city": "Ahmedabad",
    },
    {
        "customer_id": "CUST-111",
        "name": "Siddharth Rao",
        "email": "siddharth.rao@example.com",
        "phone": "+91-9876543220",
        "city": "Bengaluru",
    },
    {
        "customer_id": "CUST-112",
        "name": "Kavita Deshmukh",
        "email": "kavita.d@example.com",
        "phone": "+91-9876543221",
        "city": "Mumbai",
    },
    {
        "customer_id": "CUST-113",
        "name": "Amit Saxena",
        "email": "amit.saxena@example.com",
        "phone": "+91-9876543222",
        "city": "Lucknow",
    },
    {
        "customer_id": "CUST-114",
        "name": "Divya Menon",
        "email": "divya.m@example.com",
        "phone": "+91-9876543223",
        "city": "Trivandrum",
    },
    {
        "customer_id": "CUST-115",
        "name": "Gaurav Kapoor",
        "email": "gaurav.k@example.com",
        "phone": "+91-9876543224",
        "city": "Chandigarh",
    },
    {
        "customer_id": "CUST-116",
        "name": "Ritu Chawla",
        "email": "ritu.chawla@example.com",
        "phone": "+91-9876543225",
        "city": "Gurgaon",
    },
    {
        "customer_id": "CUST-117",
        "name": "Manoj Tiwari",
        "email": "manoj.tiwari@example.com",
        "phone": "+91-9876543226",
        "city": "Patna",
    },
    {
        "customer_id": "CUST-118",
        "name": "Sunita Roy",
        "email": "sunita.roy@example.com",
        "phone": "+91-9876543227",
        "city": "Bhubaneswar",
    },
    {
        "customer_id": "CUST-119",
        "name": "Harish Bhat",
        "email": "harish.bhat@example.com",
        "phone": "+91-9876543228",
        "city": "Mangalore",
    },
    {
        "customer_id": "CUST-120",
        "name": "Neha Agarwal",
        "email": "neha.agarwal@example.com",
        "phone": "+91-9876543229",
        "city": "Indore",
    },
]

PRODUCTS_DATA = [
    {
        "product_id": "PROD-101",
        "name": "Laptop Pro X1",
        "category": "Electronics",
        "description": "15-inch high performance business laptop",
        "price": Decimal("45000.00"),
        "stock_quantity": 25,
    },
    {
        "product_id": "PROD-102",
        "name": "Wireless Mouse",
        "category": "Accessories",
        "description": "Ergonomic 2.4GHz wireless optical mouse",
        "price": Decimal("1200.00"),
        "stock_quantity": 150,
    },
    {
        "product_id": "PROD-103",
        "name": "USB-C Hub",
        "category": "Accessories",
        "description": "Multi-port adapter with HDMI, USB 3.0, and PD",
        "price": Decimal("500.00"),
        "stock_quantity": 80,
    },
    {
        "product_id": "PROD-104",
        "name": "Cloud Suite License",
        "category": "Software",
        "description": "1-year subscription to cloud productivity suite",
        "price": Decimal("8000.00"),
        "stock_quantity": 500,
    },
    {
        "product_id": "PROD-105",
        "name": "Screen Protector Pack",
        "category": "Accessories",
        "description": "Tempered glass screen protector 2-pack",
        "price": Decimal("300.00"),
        "stock_quantity": 200,
    },
    {
        "product_id": "PROD-106",
        "name": "Mechanical Keyboard",
        "category": "Accessories",
        "description": "RGB mechanical keyboard with blue switches",
        "price": Decimal("3500.00"),
        "stock_quantity": 60,
    },
    {
        "product_id": "PROD-107",
        "name": "27-inch 4K Monitor",
        "category": "Electronics",
        "description": "Ultra HD IPS LED display with HDR",
        "price": Decimal("28000.00"),
        "stock_quantity": 15,
    },
    {
        "product_id": "PROD-108",
        "name": "Noise Cancelling Headphones",
        "category": "Electronics",
        "description": "Over-ear Bluetooth ANC headphones",
        "price": Decimal("9500.00"),
        "stock_quantity": 40,
    },
    {
        "product_id": "PROD-109",
        "name": "HD Webcam 1080p",
        "category": "Electronics",
        "description": "Wide-angle streaming camera with dual mics",
        "price": Decimal("2500.00"),
        "stock_quantity": 90,
    },
    {
        "product_id": "PROD-110",
        "name": "Security Suite Pro",
        "category": "Software",
        "description": "Comprehensive antivirus and endpoint firewall",
        "price": Decimal("4500.00"),
        "stock_quantity": 300,
    },
    {
        "product_id": "PROD-111",
        "name": "Database Analytics Add-on",
        "category": "Software",
        "description": "Advanced reporting and predictive BI tool",
        "price": Decimal("12000.00"),
        "stock_quantity": 100,
    },
    {
        "product_id": "PROD-112",
        "name": "External SSD 1TB",
        "category": "Electronics",
        "description": "High-speed NVMe portable drive USB 3.2",
        "price": Decimal("7500.00"),
        "stock_quantity": 50,
    },
    {
        "product_id": "PROD-113",
        "name": "Ergonomic Office Chair",
        "category": "Furniture",
        "description": "Breathable mesh lumbar support executive chair",
        "price": Decimal("14000.00"),
        "stock_quantity": 20,
    },
    {
        "product_id": "PROD-114",
        "name": "Standing Desk Converter",
        "category": "Furniture",
        "description": "Adjustable height tabletop riser",
        "price": Decimal("9000.00"),
        "stock_quantity": 30,
    },
    {
        "product_id": "PROD-115",
        "name": "Laptop Stand Aluminum",
        "category": "Accessories",
        "description": "Foldable ventilated cooling desk riser",
        "price": Decimal("1100.00"),
        "stock_quantity": 120,
    },
    {
        "product_id": "PROD-116",
        "name": "Cat6 Ethernet Cable 10m",
        "category": "Accessories",
        "description": "High speed gigabit shielded patch cord",
        "price": Decimal("350.00"),
        "stock_quantity": 250,
    },
    {
        "product_id": "PROD-117",
        "name": "Smart Power Strip",
        "category": "Electronics",
        "description": "4 AC outlets with 4 USB charging ports",
        "price": Decimal("1800.00"),
        "stock_quantity": 75,
    },
    {
        "product_id": "PROD-118",
        "name": "Developer SDK Toolkit",
        "category": "Software",
        "description": "Enterprise API connector and automation kit",
        "price": Decimal("15000.00"),
        "stock_quantity": 50,
    },
    {
        "product_id": "PROD-119",
        "name": "Wireless Presenter Pointer",
        "category": "Accessories",
        "description": "2.4GHz red laser presentation clicker",
        "price": Decimal("850.00"),
        "stock_quantity": 110,
    },
    {
        "product_id": "PROD-120",
        "name": "Dual Monitor Arm Mount",
        "category": "Accessories",
        "description": "Heavy duty gas spring desk clamp mount",
        "price": Decimal("4200.00"),
        "stock_quantity": 35,
    },
]

RAW_INVOICES_DATA = [
    {
        "invoice_number": "INV-201",
        "customer_id": "CUST-101",
        "invoice_date": "2026-09-05",
        "items": [
            {
                "product_id": "PROD-101",
                "quantity": 1,
                "unit_price": Decimal("45000.00"),
                "line_total": Decimal("45000.00"),
            }
        ],
        "total_amount": Decimal("45000.00"),
        "invoice_status": "issued",
        "payment_status": "paid",
    },
    {
        "invoice_number": "INV-202",
        "customer_id": "CUST-102",
        "invoice_date": "2026-09-15",
        "items": [
            {
                "product_id": "PROD-103",
                "quantity": 5,
                "unit_price": Decimal("500.00"),
                "line_total": Decimal("2500.00"),
            }
        ],
        "total_amount": Decimal("2500.00"),
        "invoice_status": "issued",
        "payment_status": "unpaid",
    },
    {
        "invoice_number": "INV-203",
        "customer_id": "CUST-101",
        "invoice_date": "2026-09-20",
        "items": [
            {
                "product_id": "PROD-102",
                "quantity": 2,
                "unit_price": Decimal("1200.00"),
                "line_total": Decimal("2400.00"),
            }
        ],
        "total_amount": Decimal("2400.00"),
        "invoice_status": "issued",
        "payment_status": "overdue",
    },
    {
        "invoice_number": "INV-204",
        "customer_id": "CUST-103",
        "invoice_date": "2026-10-01",
        "items": [
            {
                "product_id": "PROD-104",
                "quantity": 1,
                "unit_price": Decimal("8000.00"),
                "line_total": Decimal("8000.00"),
            }
        ],
        "total_amount": Decimal("8000.00"),
        "invoice_status": "void",
        "payment_status": "unpaid",
    },
    {
        "invoice_number": "INV-205",
        "customer_id": "CUST-101",
        "invoice_date": "2026-10-10",
        "items": [
            {
                "product_id": "PROD-101",
                "quantity": 1,
                "unit_price": Decimal("45000.00"),
                "line_total": Decimal("45000.00"),
            },
            {
                "product_id": "PROD-102",
                "quantity": 2,
                "unit_price": Decimal("1200.00"),
                "line_total": Decimal("2400.00"),
            },
            {
                "product_id": "PROD-105",
                "quantity": 1,
                "unit_price": Decimal("300.00"),
                "line_total": Decimal("300.00"),
            },
        ],
        "total_amount": Decimal("47700.00"),
        "invoice_status": "issued",
        "payment_status": "unpaid",
    },
    {
        "invoice_number": "INV-206",
        "customer_id": "CUST-104",
        "invoice_date": "2026-10-15",
        "items": [
            {
                "product_id": "PROD-103",
                "quantity": 10,
                "unit_price": Decimal("500.00"),
                "line_total": Decimal("5000.00"),
            },
            {
                "product_id": "PROD-105",
                "quantity": 5,
                "unit_price": Decimal("300.00"),
                "line_total": Decimal("1500.00"),
            },
        ],
        "total_amount": Decimal("6500.00"),
        "invoice_status": "issued",
        "payment_status": "partially_paid",
    },
    {
        "invoice_number": "INV-207",
        "customer_id": "CUST-105",
        "invoice_date": "2026-09-10",
        "items": [
            {
                "product_id": "PROD-106",
                "quantity": 1,
                "unit_price": Decimal("3500.00"),
                "line_total": Decimal("3500.00"),
            },
            {
                "product_id": "PROD-102",
                "quantity": 1,
                "unit_price": Decimal("1200.00"),
                "line_total": Decimal("1200.00"),
            },
        ],
        "total_amount": Decimal("4700.00"),
        "invoice_status": "issued",
        "payment_status": "paid",
    },
    {
        "invoice_number": "INV-208",
        "customer_id": "CUST-106",
        "invoice_date": "2026-09-18",
        "items": [
            {
                "product_id": "PROD-107",
                "quantity": 1,
                "unit_price": Decimal("28000.00"),
                "line_total": Decimal("28000.00"),
            }
        ],
        "total_amount": Decimal("28000.00"),
        "invoice_status": "issued",
        "payment_status": "paid",
    },
    {
        "invoice_number": "INV-209",
        "customer_id": "CUST-107",
        "invoice_date": "2026-09-25",
        "items": [
            {
                "product_id": "PROD-108",
                "quantity": 2,
                "unit_price": Decimal("9500.00"),
                "line_total": Decimal("19000.00"),
            },
            {
                "product_id": "PROD-115",
                "quantity": 2,
                "unit_price": Decimal("1100.00"),
                "line_total": Decimal("2200.00"),
            },
        ],
        "total_amount": Decimal("21200.00"),
        "invoice_status": "issued",
        "payment_status": "overdue",
    },
    {
        "invoice_number": "INV-210",
        "customer_id": "CUST-108",
        "invoice_date": "2026-10-02",
        "items": [
            {
                "product_id": "PROD-109",
                "quantity": 1,
                "unit_price": Decimal("2500.00"),
                "line_total": Decimal("2500.00"),
            },
            {
                "product_id": "PROD-116",
                "quantity": 2,
                "unit_price": Decimal("350.00"),
                "line_total": Decimal("700.00"),
            },
        ],
        "total_amount": Decimal("3200.00"),
        "invoice_status": "issued",
        "payment_status": "paid",
    },
    {
        "invoice_number": "INV-211",
        "customer_id": "CUST-109",
        "invoice_date": "2026-10-05",
        "items": [
            {
                "product_id": "PROD-110",
                "quantity": 1,
                "unit_price": Decimal("4500.00"),
                "line_total": Decimal("4500.00"),
            }
        ],
        "total_amount": Decimal("4500.00"),
        "invoice_status": "issued",
        "payment_status": "paid",
    },
    {
        "invoice_number": "INV-212",
        "customer_id": "CUST-110",
        "invoice_date": "2026-10-08",
        "items": [
            {
                "product_id": "PROD-111",
                "quantity": 1,
                "unit_price": Decimal("12000.00"),
                "line_total": Decimal("12000.00"),
            },
            {
                "product_id": "PROD-118",
                "quantity": 1,
                "unit_price": Decimal("15000.00"),
                "line_total": Decimal("15000.00"),
            },
        ],
        "total_amount": Decimal("27000.00"),
        "invoice_status": "issued",
        "payment_status": "unpaid",
    },
    {
        "invoice_number": "INV-213",
        "customer_id": "CUST-111",
        "invoice_date": "2026-10-11",
        "items": [
            {
                "product_id": "PROD-112",
                "quantity": 2,
                "unit_price": Decimal("7500.00"),
                "line_total": Decimal("15000.00"),
            }
        ],
        "total_amount": Decimal("15000.00"),
        "invoice_status": "issued",
        "payment_status": "paid",
    },
    {
        "invoice_number": "INV-214",
        "customer_id": "CUST-112",
        "invoice_date": "2026-10-12",
        "items": [
            {
                "product_id": "PROD-113",
                "quantity": 1,
                "unit_price": Decimal("14000.00"),
                "line_total": Decimal("14000.00"),
            },
            {
                "product_id": "PROD-114",
                "quantity": 1,
                "unit_price": Decimal("9000.00"),
                "line_total": Decimal("9000.00"),
            },
        ],
        "total_amount": Decimal("23000.00"),
        "invoice_status": "issued",
        "payment_status": "partially_paid",
    },
    {
        "invoice_number": "INV-215",
        "customer_id": "CUST-113",
        "invoice_date": "2026-10-13",
        "items": [
            {
                "product_id": "PROD-117",
                "quantity": 3,
                "unit_price": Decimal("1800.00"),
                "line_total": Decimal("5400.00"),
            }
        ],
        "total_amount": Decimal("5400.00"),
        "invoice_status": "void",
        "payment_status": "unpaid",
    },
    {
        "invoice_number": "INV-216",
        "customer_id": "CUST-114",
        "invoice_date": "2026-10-14",
        "items": [
            {
                "product_id": "PROD-119",
                "quantity": 2,
                "unit_price": Decimal("850.00"),
                "line_total": Decimal("1700.00"),
            },
            {
                "product_id": "PROD-102",
                "quantity": 1,
                "unit_price": Decimal("1200.00"),
                "line_total": Decimal("1200.00"),
            },
        ],
        "total_amount": Decimal("2900.00"),
        "invoice_status": "issued",
        "payment_status": "paid",
    },
    {
        "invoice_number": "INV-217",
        "customer_id": "CUST-115",
        "invoice_date": "2026-10-15",
        "items": [
            {
                "product_id": "PROD-120",
                "quantity": 1,
                "unit_price": Decimal("4200.00"),
                "line_total": Decimal("4200.00"),
            },
            {
                "product_id": "PROD-107",
                "quantity": 1,
                "unit_price": Decimal("28000.00"),
                "line_total": Decimal("28000.00"),
            },
        ],
        "total_amount": Decimal("32200.00"),
        "invoice_status": "issued",
        "payment_status": "paid",
    },
    {
        "invoice_number": "INV-218",
        "customer_id": "CUST-116",
        "invoice_date": "2026-10-16",
        "items": [
            {
                "product_id": "PROD-106",
                "quantity": 2,
                "unit_price": Decimal("3500.00"),
                "line_total": Decimal("7000.00"),
            }
        ],
        "total_amount": Decimal("7000.00"),
        "invoice_status": "issued",
        "payment_status": "unpaid",
    },
    {
        "invoice_number": "INV-219",
        "customer_id": "CUST-117",
        "invoice_date": "2026-10-17",
        "items": [
            {
                "product_id": "PROD-108",
                "quantity": 1,
                "unit_price": Decimal("9500.00"),
                "line_total": Decimal("9500.00"),
            },
            {
                "product_id": "PROD-112",
                "quantity": 1,
                "unit_price": Decimal("7500.00"),
                "line_total": Decimal("7500.00"),
            },
        ],
        "total_amount": Decimal("17000.00"),
        "invoice_status": "issued",
        "payment_status": "paid",
    },
    {
        "invoice_number": "INV-220",
        "customer_id": "CUST-118",
        "invoice_date": "2026-10-18",
        "items": [
            {
                "product_id": "PROD-101",
                "quantity": 1,
                "unit_price": Decimal("45000.00"),
                "line_total": Decimal("45000.00"),
            },
            {
                "product_id": "PROD-118",
                "quantity": 1,
                "unit_price": Decimal("15000.00"),
                "line_total": Decimal("15000.00"),
            },
        ],
        "total_amount": Decimal("60000.00"),
        "invoice_status": "issued",
        "payment_status": "unpaid",
    },
]


def validate_seed_dataset() -> list[InvoiceSeed]:
    """Validate seed data in Python with Pydantic before any DB operation."""
    valid_prod_ids = {p["product_id"] for p in PRODUCTS_DATA}
    validated_invoices: list[InvoiceSeed] = []

    for raw_inv in RAW_INVOICES_DATA:
        items = [LineItem(**item) for item in raw_inv["items"]]
        inv = InvoiceSeed(
            invoice_number=raw_inv["invoice_number"],
            customer_id=raw_inv["customer_id"],
            invoice_date=raw_inv["invoice_date"],
            items=items,
            total_amount=raw_inv["total_amount"],
            invoice_status=raw_inv["invoice_status"],
            payment_status=raw_inv["payment_status"],
        )
        inv.validate_product_ids(valid_prod_ids)
        validated_invoices.append(inv)

    return validated_invoices


def seed_database(admin_db_url: str | None = None) -> None:
    """Populate database with validated seed data."""
    validated_invoices = validate_seed_dataset()

    url = admin_db_url or os.getenv("ADMIN_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL must be set to run seed_database.")

    admin_engine = create_engine(url)

    with admin_engine.begin() as conn:
        # Clear existing records
        conn.execute(text("TRUNCATE TABLE invoices, products, customers CASCADE;"))

        # Insert customers
        for cust in CUSTOMERS_DATA:
            conn.execute(
                text(
                    """
                    INSERT INTO customers (customer_id, name, email, phone, city)
                    VALUES (:customer_id, :name, :email, :phone, :city)
                    """
                ),
                cust,
            )

        # Insert products
        for prod in PRODUCTS_DATA:
            conn.execute(
                text(
                    """
                    INSERT INTO products (product_id, name, category, description, price, stock_quantity)
                    VALUES (:product_id, :name, :category, :description, :price, :stock_quantity)
                    """
                ),
                prod,
            )

        # Insert invoices
        for inv in validated_invoices:
            items_json = json.dumps(
                [
                    {
                        "product_id": item.product_id,
                        "quantity": item.quantity,
                        "unit_price": float(item.unit_price),
                        "line_total": float(item.line_total),
                    }
                    for item in inv.items
                ]
            )

            conn.execute(
                text(
                    """
                    INSERT INTO invoices (invoice_number, customer_id, invoice_date, items, total_amount, invoice_status, payment_status)
                    VALUES (:invoice_number, :customer_id, :invoice_date, CAST(:items AS JSONB), :total_amount, :invoice_status, :payment_status)
                    """
                ),
                {
                    "invoice_number": inv.invoice_number,
                    "customer_id": inv.customer_id,
                    "invoice_date": inv.invoice_date,
                    "items": items_json,
                    "total_amount": inv.total_amount,
                    "invoice_status": inv.invoice_status,
                    "payment_status": inv.payment_status,
                },
            )

    print(f"Successfully seeded {len(CUSTOMERS_DATA)} customers, {len(PRODUCTS_DATA)} products, and {len(validated_invoices)} invoices with validation.")


if __name__ == "__main__":
    seed_database()
