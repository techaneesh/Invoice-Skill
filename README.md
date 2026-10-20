# 🧾 AI Agent with Invoice Skill (POC)

A simple, secure natural-language database query agent built with **FastAPI**, **Streamlit**, and **PostgreSQL**.

Ask questions in plain English (e.g., *"Show all unpaid invoices"* or *"Which products are in invoice INV-205?"*). The AI routes the question, generates safe parameterized SQL, validates it through a strict security engine (SQLGlot AST), runs it in a read-only transaction, and gives you back a clean answer and data table.

---

## 🚀 Quick Setup Guide

Follow these simple steps to run the POC on your local machine:

### Step 1: Clone and Open Project
```bash
git clone <repo-url>
cd Invoice-Skill
```

### Step 2: Create Virtual Environment & Install Dependencies
Open a terminal in the project folder:

**On Windows (PowerShell):**
```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**On Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

### Step 3: Configure Environment Variables
Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Open `.env` and set your credentials:
```env
# Database Credentials
DATABASE_URL=postgresql://poc_readonly_user:readonly_pass@localhost:5432/invoice_poc
ADMIN_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/invoice_poc

# Choose LLM: "gemini" or "openai"
LLM_PROVIDER=gemini

# Your API Key
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
```

---

### Step 4: Connecting with pgAdmin 4

If connecting via **pgAdmin 4**:
1. In pgAdmin left sidebar, expand **Servers**.
2. If prompted for password on existing server (e.g. `PostgreSQL 16`), enter:
   - **Password:** `postgres`
3. To register a new connection directly to `invoice_poc`:
   - Right-click **Servers** > **Register** > **Server...**
   - **General Tab:** Name: `Invoice POC`
   - **Connection Tab:**
     - Host name/address: `localhost`
     - Port: `5432`
     - Maintenance database: `invoice_poc`
     - Username: `postgres`
     - Password: `postgres`
     - Click **Save**
4. The database is pre-created and pre-seeded with all 3 tables: `customers`, `products`, `invoices`.

### Database Credentials Reference:
| Role / Account | Username | Password | Database | Host:Port |
| :--- | :--- | :--- | :--- | :--- |
| **Admin Superuser** | `postgres` | `postgres` | `invoice_poc` | `localhost:5432` |
| **POC Read-Only User** | `poc_readonly_user` | `readonly_pass` | `invoice_poc` | `localhost:5432` |

---

## 🖥️ Starting the Application (2 Separate Terminals)

To run the application, open **two separate terminal windows**:

### Terminal 1: Start FastAPI Backend Server
```powershell
# Activate venv if needed:
.venv\Scripts\Activate.ps1

# Run backend:
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```
- API is running at: `http://127.0.0.1:8000`
- API documentation: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

### Terminal 2: Start Streamlit Frontend Chat UI
```powershell
# Activate venv if needed:
.venv\Scripts\Activate.ps1

# Run frontend:
streamlit run app.py
```
- Streamlit UI will open automatically in your browser at: **`http://localhost:8501`**

---

## ⚡ Demo Questions to Try

Once `http://localhost:8501` is open, click any of the quick buttons in the sidebar or type them in the chat:

1. **"Show invoice INV-205."** *(Shows invoice header)*
2. **"Show the latest invoice for customer CUST-101."** *(Finds latest by date)*
3. **"Which customer does invoice INV-205 belong to?"** *(Joins customers table)*
4. **"Which products are included in invoice INV-205?"** *(Expands JSONB line items)*
5. **"Show each product's quantity and price in invoice INV-205."** *(Item-level details)*
6. **"Show all unpaid invoices."** *(Filters by payment status, excludes void)*
7. **"Show unpaid invoices above ₹10,000."** *(Combines status and amount filter)*
8. **"Find invoices issued last month."** *(Date calculation relative to today)*
9. **"Calculate the total value of unpaid invoices."** *(Header-only aggregation, no double counting)*
10. **"Show all products in the electronics category."** *(GeneralQuery catalog lookup)*
11. **"Find customer CUST-101's email."** *(GeneralQuery customer lookup)*
12. **"How many invoices does each customer have?"** *(Aggregates invoices per customer)*

---

## 🧪 Running Automated Tests

To verify security, AST validation, routing, and APIs, run:

```bash
pytest tests/ -v
```

All 32 tests will run:
- `test_security.py`: SQL injection prevention, DDL/DML blocking, table/column allowlists, LIMIT 100 enforcement.
- `test_query_engine.py`: JSONB lateral queries, no double counting, Pydantic seed validations.
- `test_routing.py`: InvoiceSkill vs GeneralQuery classification and malicious prompt rejection.
- `test_api.py`: FastAPI endpoints and Decimal string serialization.

---

## 📁 Project Architecture

```text
Invoice-Skill/
├── app.py                   # Streamlit chat interface
├── main.py                  # FastAPI REST endpoints (/health, /api/chat)
├── agent.py                 # Intent routing, execution orchestrator, answer synthesis
├── skills/
│   └── invoice.py           # InvoiceSkill prompt rules & JSONB expansion queries
├── query_engine.py          # SQLGlot AST validation & safe execution
├── database.py              # Read-only transaction execution & Decimal formatting
├── llm_client.py            # Gemini & OpenAI client adapter
├── models.py                # Pydantic models for request, response, SQL, and seed data
├── schema.sql               # PostgreSQL tables (customers, products, invoices) + read-only role
├── seed_data.py             # Deterministic seed data populator with Pydantic checks
├── tests/                   # 32 unit and integration tests
├── .env.example             # Configuration template
├── requirements.txt         # Pinned Python package dependencies
└── README.md                # This setup guide
```

---

## 🛑 How to Stop the Servers

In each terminal window, press:
```text
Ctrl + C
```
This safely shuts down both Uvicorn and Streamlit.