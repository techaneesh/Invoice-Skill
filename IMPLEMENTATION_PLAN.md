# Implementation Plan: AI Agent with Invoice Skill (POC)

## Goal Description

Build a **Python-based natural-language database query POC** — an AI agent that knows the schema of a PostgreSQL database (3 tables: `customers`, `products`, `invoices`), receives user questions in plain English, dynamically generates safe SQL via an LLM, validates it with SQLGlot, executes it in a read-only transaction, and returns structured answers.

The system has **one specialized skill** (`InvoiceSkill`) for invoice/billing/payment queries and a **general fallback** (`GeneralQuery`) for standalone customer/product catalog queries. Both share a single secure query engine.

**Frontend:** Streamlit chat UI  
**Backend:** FastAPI REST API  
**Database:** PostgreSQL (locally installed)  
**LLM:** Configurable — Google Gemini or OpenAI (via env var)

---

## User Review Required

> [!IMPORTANT]
> **PostgreSQL Setup** — You confirmed you'll install PostgreSQL locally. The plan assumes:
> - PostgreSQL is accessible at `localhost:5432`
> - You'll create a database (e.g., `invoice_poc`) and a user with appropriate privileges
> - Connection string provided via `.env` file
>
> The `schema.sql` file will contain all DDL + read-only role creation, runnable with `psql`.

> [!IMPORTANT]
> **LLM API Keys Required** — The LLM client supports both Gemini and OpenAI. You must provide at least one API key in `.env`:
> - `LLM_PROVIDER=gemini` + `GEMINI_API_KEY=...`
> - or `LLM_PROVIDER=openai` + `OPENAI_API_KEY=...`

> [!WARNING]
> **No Conversation Memory** — This POC is **stateless per request**. There is no multi-turn conversation memory or chat history sent to the LLM. Each question is independent. The `session_id` field exists for future extensibility but is not used for context retrieval in this POC.

---

## Open Questions

All questions have been resolved:
- ✅ Frontend: Streamlit only
- ✅ LLM: Configurable Gemini/OpenAI via env var
- ✅ Database: PostgreSQL (local installation)

---

## Architecture Overview

```mermaid
flowchart TD
    A["User (Browser)"] -->|Chat message| B["Streamlit UI<br/>app.py"]
    B -->|POST /api/chat| C["FastAPI<br/>main.py"]
    C --> D["Agent Router<br/>agent.py"]
    D -->|Classify intent| E["LLM Client<br/>llm_client.py"]
    E -->|RouteDecision| D

    D -->|InvoiceSkill| F["InvoiceSkill<br/>skills/invoice.py"]
    D -->|GeneralQuery| G["GeneralQuery<br/>agent.py"]

    F -->|schema + rules| H["Query Engine<br/>query_engine.py"]
    G -->|schema only| H

    H -->|Generate SQL| E
    E -->|GeneratedSQL JSON| H
    H -->|Validate AST| I["SQLGlot Validator"]
    I -->|Pass| J["Execute Query<br/>database.py"]
    I -->|Fail + retry ≤1| H
    J -->|Read-only txn| K["PostgreSQL"]
    J -->|Rows| H
    H -->|Data| D
    D -->|Synthesize answer| E
    D -->|ChatResponse| C
    C -->|JSON| B
    B -->|Render| A
```

### Request Flow (Sequence)

```mermaid
sequenceDiagram
    participant U as User
    participant ST as Streamlit
    participant FA as FastAPI
    participant AG as Agent
    participant LLM as LLM Client
    participant SK as InvoiceSkill
    participant QE as Query Engine
    participant DB as PostgreSQL

    U->>ST: Type question
    ST->>FA: POST /api/chat {message, session_id}
    FA->>AG: process(message)
    AG->>LLM: Classify intent (routing prompt)
    LLM-->>AG: RouteDecision {capability, clarification}
    
    alt capability == "InvoiceSkill"
        AG->>SK: get_prompt_rules()
        SK-->>AG: domain rules + JSONB patterns
    end
    
    AG->>QE: generate_and_execute(message, rules)
    QE->>LLM: Generate SQL (schema + rules + question)
    LLM-->>QE: GeneratedSQL {sql_query, parameters}
    QE->>QE: validate_sql() via SQLGlot AST
    
    alt Validation fails & retries < 1
        QE->>LLM: Fix SQL (error feedback)
        LLM-->>QE: Fixed GeneratedSQL
        QE->>QE: validate_sql() again
    end
    
    QE->>DB: SET TRANSACTION READ ONLY
    QE->>DB: SET LOCAL statement_timeout = '3000ms'
    QE->>DB: Execute parameterized SELECT
    DB-->>QE: Result rows
    QE-->>AG: formatted data[]
    
    alt data is not empty
        AG->>LLM: Synthesize natural language answer
        LLM-->>AG: answer text
    else data is empty
        AG-->>AG: "No results found" (no LLM call)
    end
    
    AG-->>FA: ChatResponse
    FA-->>ST: JSON response
    ST-->>U: Render answer + data table
```

---

## Proposed Changes

### File Structure

```text
D:\Invoice-Skill\
├── app.py                   # Streamlit chat UI (~100 lines)
├── main.py                  # FastAPI: GET /health, POST /api/chat
├── agent.py                 # Router + orchestrator + retry logic
├── skills/
│   ├── __init__.py          # Empty (package marker)
│   └── invoice.py           # InvoiceSkill: prompt rules & JSONB patterns
├── query_engine.py          # Schema context + SQLGlot validator + executor bridge
├── database.py              # SQLAlchemy engine, session, read-only execute helper
├── llm_client.py            # Configurable Gemini/OpenAI adapter (structured JSON)
├── models.py                # All Pydantic models
├── schema.sql               # PostgreSQL DDL + read-only role
├── seed_data.py             # Pydantic-validated deterministic seed data generator
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Shared fixtures (test DB, mock LLM)
│   ├── test_routing.py
│   ├── test_query_engine.py
│   ├── test_security.py
│   └── test_api.py
├── .env.example
├── requirements.txt
└── README.md
```

> [!NOTE]
> Two files added beyond the spec: `skills/__init__.py` and `tests/conftest.py`. Both are standard Python package markers / pytest fixtures — zero logic, purely structural.

---

### Component 1: Database Layer

#### [NEW] `schema.sql`

PostgreSQL DDL defining the 3 tables with all constraints, plus a read-only role.

```sql
-- ============================================================
-- schema.sql — Invoice Agent POC: PostgreSQL DDL
-- ============================================================

-- 1. Create tables
CREATE TABLE IF NOT EXISTS customers (
    customer_id   VARCHAR(32)  PRIMARY KEY,
    name          VARCHAR(120) NOT NULL,
    email         VARCHAR(150) UNIQUE NOT NULL,
    phone         VARCHAR(30),
    city          VARCHAR(80),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS products (
    product_id     VARCHAR(32)   PRIMARY KEY,
    name           VARCHAR(150)  NOT NULL,
    category       VARCHAR(80)   NOT NULL,
    description    TEXT,
    price          NUMERIC(12,2) NOT NULL CHECK (price >= 0),
    stock_quantity INTEGER       NOT NULL DEFAULT 0 CHECK (stock_quantity >= 0),
    created_at     TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS invoices (
    id              SERIAL        PRIMARY KEY,
    invoice_number  VARCHAR(32)   UNIQUE NOT NULL,
    customer_id     VARCHAR(32)   NOT NULL REFERENCES customers(customer_id),
    invoice_date    DATE          NOT NULL,
    items           JSONB         NOT NULL,
    total_amount    NUMERIC(12,2) NOT NULL CHECK (total_amount >= 0),
    invoice_status  VARCHAR(32)   NOT NULL CHECK (invoice_status IN ('issued', 'void')),
    payment_status  VARCHAR(32)   NOT NULL CHECK (payment_status IN ('unpaid', 'partially_paid', 'paid', 'overdue')),
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- 2. Read-only role (least privilege)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'poc_readonly_user') THEN
        CREATE ROLE poc_readonly_user WITH LOGIN PASSWORD 'readonly_pass';
    END IF;
END
$$;

GRANT SELECT ON customers, products, invoices TO poc_readonly_user;
-- Explicitly no INSERT, UPDATE, DELETE, TRUNCATE
```

**Key design decisions:**
- `items JSONB NOT NULL` — stores line items as a JSON array, avoiding a 4th table
- `invoice_status` vs `payment_status` — separate lifecycle concerns
- `CHECK` constraints enforce valid enum values at the DB level
- `poc_readonly_user` gets only `SELECT` — defense in depth alongside app-level validation

---

#### [NEW] `database.py`

SQLAlchemy async-compatible engine setup and a read-only execution helper.

```python
"""database.py — SQLAlchemy PostgreSQL engine & read-only execution helper."""

import os
from contextlib import contextmanager
from decimal import Decimal
from datetime import date, datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://poc_readonly_user:readonly_pass@localhost:5432/invoice_poc")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5)
SessionLocal = sessionmaker(bind=engine)


def execute_readonly_query(sql: str, parameters: dict) -> list[dict]:
    """Execute a validated SQL query in a read-only transaction with timeout.
    
    Returns rows as list of dicts with Decimal/date serialization applied.
    """
    with engine.connect() as conn:
        # Enforce read-only at transaction level
        conn.execute(text("SET TRANSACTION READ ONLY"))
        conn.execute(text("SET LOCAL statement_timeout = '3000ms'"))
        
        result = conn.execute(text(sql), parameters)
        columns = list(result.keys())
        rows = []
        for row in result.fetchall():
            row_dict = {}
            for col, val in zip(columns, row):
                if isinstance(val, Decimal):
                    row_dict[col] = f"{val:.2f}"
                elif isinstance(val, (date, datetime)):
                    row_dict[col] = val.isoformat()
                else:
                    row_dict[col] = val
            rows.append(row_dict)
        return rows


def check_db_connection() -> bool:
    """Ping the database. Returns True if connected, False otherwise."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
```

**Design notes:**
- `execute_readonly_query` is the **single execution entry point** — both skills use it
- `SET TRANSACTION READ ONLY` + `SET LOCAL statement_timeout = '3000ms'` — safety at DB level
- Decimal → `"47700.00"` string formatting happens here (consistent serialization)
- `pool_pre_ping=True` — auto-reconnect on stale connections

---

### Component 2: Pydantic Models

#### [NEW] `models.py`

All Pydantic models in one file — API contracts, SQL output, seed validation, routing.

```python
"""models.py — All Pydantic models for the Invoice Agent POC."""

from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator


# --- API Models ---

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    session_id: str = Field(default="demo-session")


class ChatResponse(BaseModel):
    request_id: str
    status: str  # "success" | "clarification_required" | "not_found" | "error"
    capability_used: Optional[str] = None
    answer: str
    data: Optional[list[dict]] = None
    error: Optional[str] = None


# --- Routing Models ---

class RouteDecision(BaseModel):
    capability: str  # "InvoiceSkill" | "GeneralQuery" | "clarification_required" | "rejected"
    clarification_question: Optional[str] = None


# --- SQL Generation Models ---

class GeneratedSQL(BaseModel):
    sql_query: str
    parameters: dict


# --- Seed Validation Models ---

class LineItem(BaseModel):
    product_id: str
    quantity: int = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0)
    line_total: Decimal = Field(..., ge=0)

    @model_validator(mode="after")
    def validate_line_total(self):
        expected = self.quantity * self.unit_price
        if self.line_total != expected:
            raise ValueError(
                f"line_total {self.line_total} != quantity({self.quantity}) * unit_price({self.unit_price}) = {expected}"
            )
        return self


class InvoiceSeed(BaseModel):
    invoice_number: str
    customer_id: str
    invoice_date: str
    items: list[LineItem] = Field(..., min_length=1)
    total_amount: Decimal = Field(..., ge=0)
    invoice_status: str
    payment_status: str

    @model_validator(mode="after")
    def validate_total(self):
        expected = sum(item.line_total for item in self.items)
        if self.total_amount != expected:
            raise ValueError(
                f"total_amount {self.total_amount} != sum of line_totals {expected}"
            )
        return self

    def validate_product_ids(self, valid_product_ids: set[str]):
        for item in self.items:
            if item.product_id not in valid_product_ids:
                raise ValueError(f"Unknown product_id: {item.product_id}")
```

**Key decisions:**
- `LineItem.validate_line_total` — catches `line_total != qty * unit_price` at seed time
- `InvoiceSeed.validate_total` — catches `total_amount != sum(line_totals)` at seed time
- `InvoiceSeed.validate_product_ids()` — called separately with the set of seeded product IDs
- `ChatResponse.data` is `list[dict]` not a typed model — flexibility for dynamic query results

---

### Component 3: LLM Client

#### [NEW] `llm_client.py`

A simple, swappable adapter that supports both Gemini and OpenAI. Returns structured JSON.

```python
"""llm_client.py — Configurable LLM adapter (Gemini / OpenAI)."""

import os
import json

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")  # "gemini" or "openai"


def call_llm(system_prompt: str, user_prompt: str) -> dict:
    """Send a prompt to the configured LLM and parse JSON response.
    
    Both Gemini and OpenAI paths instruct the LLM to respond ONLY 
    with valid JSON (no markdown fences, no explanation).
    Returns: parsed dict from JSON response.
    """
    if LLM_PROVIDER == "gemini":
        return _call_gemini(system_prompt, user_prompt)
    elif LLM_PROVIDER == "openai":
        return _call_openai(system_prompt, user_prompt)
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER}")


def _call_gemini(system_prompt: str, user_prompt: str) -> dict:
    """Call Google Gemini API."""
    import google.generativeai as genai
    
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel(
        model_name=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        system_instruction=system_prompt,
    )
    response = model.generate_content(
        user_prompt,
        generation_config=genai.types.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.0,
        ),
    )
    return json.loads(response.text)


def _call_openai(system_prompt: str, user_prompt: str) -> dict:
    """Call OpenAI API."""
    from openai import OpenAI
    
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )
    return json.loads(response.choices[0].message.content)
```

**Design notes:**
- **Zero abstraction overhead** — two functions, one switch. No ABC, no registry.
- **Structured JSON output enforced** — Gemini uses `response_mime_type="application/json"`, OpenAI uses `response_format={"type": "json_object"}`
- `temperature=0.0` — deterministic SQL generation
- Model name configurable via env vars (`GEMINI_MODEL`, `OPENAI_MODEL`)

---

### Component 4: InvoiceSkill

#### [NEW] `skills/__init__.py`
Empty file (package marker).

#### [NEW] `skills/invoice.py`

Domain-specific prompt rules for invoice queries — injected into the SQL generation prompt.

```python
"""skills/invoice.py — InvoiceSkill: domain-specific prompt rules for invoice queries."""


class InvoiceSkill:
    """Provides invoice-domain prompt rules to the query engine.
    
    NOT a query executor — just a rules provider. The shared query_engine
    handles all SQL generation, validation, and execution.
    """
    
    NAME = "InvoiceSkill"

    @staticmethod
    def get_prompt_rules() -> str:
        return """
INVOICE DOMAIN RULES (you MUST follow these):

1. VOID EXCLUSION: Unless the user explicitly asks for voided invoices,
   always include: WHERE invoice_status = :invoice_status 
   with parameter invoice_status = 'issued'.

2. HEADER-ONLY AGGREGATION (prevents double counting):
   When querying invoice counts, invoice-level totals (SUM(total_amount)),
   statuses, or dates WITHOUT needing item-level product details,
   query the invoices table directly. NEVER expand jsonb_array_elements
   for invoice-level aggregations.

3. JSONB LINE-ITEM EXPANSION (when product details needed):
   When querying products, quantities, or prices INSIDE an invoice, use:
   
   SELECT p.product_id, p.name AS product_name,
          CAST(item.value ->> 'quantity' AS INTEGER) AS quantity,
          CAST(item.value ->> 'unit_price' AS NUMERIC) AS unit_price,
          CAST(item.value ->> 'line_total' AS NUMERIC) AS line_total
   FROM invoices AS i
   CROSS JOIN LATERAL jsonb_array_elements(i.items) AS item(value)
   JOIN products AS p ON p.product_id = (item.value ->> 'product_id')
   WHERE i.invoice_number = :invoice_number
   LIMIT 100

4. TYPE CAST RULE: Always use CAST(x AS NUMERIC) or CAST(x AS INTEGER).
   NEVER use PostgreSQL :: cast syntax (conflicts with :param_name binding).

5. DATE HANDLING: "Last month" = previous calendar month relative to NOW().
   Use: WHERE invoice_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
        AND invoice_date < DATE_TRUNC('month', CURRENT_DATE)
""".strip()
```

**Key design decisions:**
- `InvoiceSkill` is a **rules-only class** — no SQL execution logic, no DB access
- The double-counting rule (#2) is critical: without it, `SUM(total_amount)` over JSONB-expanded rows multiplies by item count
- The `CAST` rule (#4) prevents SQLAlchemy parameter binding conflicts
- Rules are injected as part of the system prompt during SQL generation

---

### Component 5: Query Engine (Core)

#### [NEW] `query_engine.py`

The heart of the system — schema context, SQLGlot AST validation, and execution orchestration.

```python
"""query_engine.py — Schema context, SQLGlot AST validator, safe execution."""

import sqlglot
from sqlglot import exp
from database import execute_readonly_query
from llm_client import call_llm
from models import GeneratedSQL

# --- Schema Context (injected into LLM prompts) ---

SCHEMA_CONTEXT = """
PostgreSQL database with exactly 3 tables:

TABLE customers (
    customer_id VARCHAR(32) PRIMARY KEY,  -- e.g. 'CUST-101'
    name VARCHAR(120) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    phone VARCHAR(30),
    city VARCHAR(80),
    created_at TIMESTAMPTZ DEFAULT NOW()
)

TABLE products (
    product_id VARCHAR(32) PRIMARY KEY,  -- e.g. 'PROD-101'
    name VARCHAR(150) NOT NULL,
    category VARCHAR(80) NOT NULL,  -- e.g. 'Electronics', 'Software', 'Accessories'
    description TEXT,
    price NUMERIC(12,2) NOT NULL,  -- Current catalog price
    stock_quantity INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
)

TABLE invoices (
    id SERIAL PRIMARY KEY,
    invoice_number VARCHAR(32) UNIQUE NOT NULL,  -- e.g. 'INV-205'
    customer_id VARCHAR(32) NOT NULL REFERENCES customers(customer_id),
    invoice_date DATE NOT NULL,
    items JSONB NOT NULL,  -- Array of: {"product_id", "quantity", "unit_price", "line_total"}
    total_amount NUMERIC(12,2) NOT NULL,
    invoice_status VARCHAR(32) NOT NULL,  -- 'issued' or 'void'
    payment_status VARCHAR(32) NOT NULL,  -- 'unpaid','partially_paid','paid','overdue'
    created_at TIMESTAMPTZ DEFAULT NOW()
)
"""

# --- Allowlists ---

ALLOWED_TABLES = {"customers", "products", "invoices"}

ALLOWED_COLUMNS = {
    "customers": {"customer_id", "name", "email", "phone", "city", "created_at"},
    "products": {"product_id", "name", "category", "description", "price", "stock_quantity", "created_at"},
    "invoices": {"id", "invoice_number", "customer_id", "invoice_date", "items",
                 "total_amount", "invoice_status", "payment_status", "created_at"},
    "item": {"value"},  # JSONB lateral alias
}

ALLOWED_FUNCTIONS = {
    "COUNT", "SUM", "AVG", "MIN", "MAX", "COALESCE", "LOWER", "UPPER",
    "ROUND", "CAST", "DATE_TRUNC", "EXTRACT", "CURRENT_DATE", "NOW",
    "JSONB_ARRAY_ELEMENTS", "ARRAY_AGG", "STRING_AGG",
}

BLOCKED_FUNCTIONS = {
    "PG_SLEEP", "PG_READ_FILE", "CURRENT_SETTING", "SET_CONFIG",
    "DBLINK", "LO_IMPORT", "LO_EXPORT", "PG_TERMINATE_BACKEND",
}

MAX_LIMIT = 100
```

**SQLGlot Validation (`validate_sql`)** will perform these checks in order:
1. **Single-statement check** — `sqlglot.parse()` must return exactly 1 `exp.Select`
2. **Parameter binding verification** — extract `:param` placeholders, match against `parameters` keys
3. **Table allowlist** — resolve all table references (including subqueries/CTEs), reject system schemas
4. **Column allowlist** — verify all column references belong to allowed tables (with alias resolution)
5. **Function allowlist** — check every `exp.Func`/`exp.Anonymous` node against allow/block lists
6. **Limit enforcement** — if no LIMIT or LIMIT > 100, programmatically inject `.limit(100)`

**Execution flow:**
1. Build SQL generation prompt (schema + skill rules + user question)
2. Call LLM → parse into `GeneratedSQL` Pydantic model
3. Run `validate_sql()` — if fails, return error for retry
4. Call `database.execute_readonly_query()` with validated SQL + params
5. Return `list[dict]` of result rows

---

### Component 6: Agent (Router + Orchestrator)

#### [NEW] `agent.py`

Single entry point that routes, generates, validates, executes, and composes answers.

```python
"""agent.py — Router, orchestrator, and retry logic."""

import uuid
from models import ChatRequest, ChatResponse, RouteDecision, GeneratedSQL
from llm_client import call_llm
from query_engine import generate_and_execute, SCHEMA_CONTEXT
from skills.invoice import InvoiceSkill

MAX_RETRIES = 1


async def process_chat(request: ChatRequest) -> ChatResponse:
    """Main entry point: route → generate SQL → validate → execute → answer."""
    request_id = str(uuid.uuid4())
    
    # Step 1: Route the user's intent
    route = _route_intent(request.message)
    
    if route.capability == "clarification_required":
        return ChatResponse(
            request_id=request_id,
            status="clarification_required",
            answer=route.clarification_question or "Could you please clarify your question?",
        )
    
    if route.capability == "rejected":
        return ChatResponse(
            request_id=request_id,
            status="error",
            answer="I can only answer read-only questions about customers, products, and invoices.",
            error="Request rejected: data modification not allowed.",
        )
    
    # Step 2: Get skill-specific rules (if applicable)
    skill_rules = ""
    if route.capability == "InvoiceSkill":
        skill_rules = InvoiceSkill.get_prompt_rules()
    
    # Step 3: Generate, validate, execute (with retry)
    data, error = None, None
    for attempt in range(MAX_RETRIES + 1):
        try:
            data = generate_and_execute(request.message, skill_rules)
            error = None
            break
        except Exception as e:
            error = str(e)
            # On first failure, the generate_and_execute will be called 
            # again with error context (handled inside query_engine)
    
    if error:
        return ChatResponse(
            request_id=request_id,
            status="error",
            capability_used=route.capability,
            answer="Sorry, I couldn't process your query. Please try rephrasing.",
            error=error,
        )
    
    # Step 4: Compose answer
    if not data:
        return ChatResponse(
            request_id=request_id,
            status="not_found",
            capability_used=route.capability,
            answer="No results found for your query.",
            data=[],
        )
    
    answer = _synthesize_answer(request.message, data)
    return ChatResponse(
        request_id=request_id,
        status="success",
        capability_used=route.capability,
        answer=answer,
        data=data,
    )
```

**Routing prompt** sends the user message + schema summary to the LLM and asks for a `RouteDecision` JSON. The routing rules are:
- Mentions invoices/bills/billing/payment/bought → `InvoiceSkill`
- Standalone customer/product catalog queries → `GeneralQuery`
- Ambiguous/no-context → `clarification_required`
- Data modification requests → `rejected`

**Answer synthesis:**
- If `data` is empty → return `not_found` (no LLM call)
- If `data` has rows → one concise LLM call grounded in the data to produce a natural language summary

---

### Component 7: FastAPI Endpoints

#### [NEW] `main.py`

Minimal FastAPI app with two endpoints.

```python
"""main.py — FastAPI endpoints: GET /health, POST /api/chat."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from models import ChatRequest, ChatResponse
from database import check_db_connection
from agent import process_chat

app = FastAPI(title="Invoice Agent POC", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    db_ok = check_db_connection()
    if db_ok:
        return {"app_status": "healthy", "db_status": "connected"}
    return JSONResponse(
        status_code=503,
        content={"app_status": "healthy", "db_status": "unavailable",
                 "error": "Database connection check failed."},
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    return await process_chat(request)
```

---

### Component 8: Streamlit UI

#### [NEW] `app.py`

Compact chat UI (~100 lines) that calls the FastAPI backend.

**UI Elements:**
- `st.chat_input()` for user messages
- `st.session_state.messages` for chat history (display only — not sent to LLM for context)
- Each response shows:
  - `answer` text in a chat bubble
  - `capability_used` as a colored badge (`st.caption`)
  - `st.dataframe()` when `data` contains rows
  - `st.warning()` for `clarification_required`
  - `st.info()` for `not_found`
  - `st.error()` for `error` status

```python
"""app.py — Streamlit chat UI for Invoice Agent POC."""

import streamlit as st
import requests

API_URL = "http://localhost:8000"

st.set_page_config(page_title="Invoice Agent", page_icon="🧾")
st.title("🧾 Invoice Agent")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("data"):
            st.dataframe(msg["data"])
        if msg.get("badge"):
            st.caption(f"🏷️ {msg['badge']}")

# Chat input
if prompt := st.chat_input("Ask about invoices, customers, or products..."):
    # Show user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Call API
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                resp = requests.post(
                    f"{API_URL}/api/chat",
                    json={"message": prompt, "session_id": "streamlit-session"},
                    timeout=30,
                )
                result = resp.json()
            except Exception as e:
                st.error(f"API Error: {e}")
                result = None
        
        if result:
            status = result.get("status")
            answer = result.get("answer", "")
            data = result.get("data")
            badge = result.get("capability_used", "")
            
            if status == "clarification_required":
                st.warning(answer)
            elif status == "not_found":
                st.info(answer)
            elif status == "error":
                st.error(answer)
            else:
                st.markdown(answer)
            
            if data:
                st.dataframe(data)
            if badge:
                st.caption(f"🏷️ {badge}")
            
            # Save to history
            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "data": data,
                "badge": badge,
            })
```

---

### Component 9: Seed Data

#### [NEW] `seed_data.py`

Deterministic seed data generator with Pydantic validation. Run once to populate the database.

**Seed Records:**

| Entity | IDs | Notes |
|--------|-----|-------|
| Customers | `CUST-101` to `CUST-104` | Different cities |
| Products | `PROD-101` to `PROD-105` | Electronics, Software, Accessories categories |
| Invoices | `INV-201` to `INV-206` | Mixed statuses, dates, multi-item invoices |

**Invoice Seed Details:**

| Invoice | Customer | Date | Items | Total | Invoice Status | Payment Status |
|---------|----------|------|-------|-------|----------------|----------------|
| INV-201 | CUST-101 | 2026-09-05 | PROD-101 ×1 (₹45,000) | ₹45,000.00 | issued | paid |
| INV-202 | CUST-102 | 2026-09-15 | PROD-103 ×5 (₹500 ea) | ₹2,500.00 | issued | unpaid |
| INV-203 | CUST-101 | 2026-09-20 | PROD-102 ×2 (₹1,200 ea) | ₹2,400.00 | issued | overdue |
| INV-204 | CUST-103 | 2026-10-01 | PROD-104 ×1 (₹8,000) | ₹8,000.00 | void | unpaid |
| INV-205 | CUST-101 | 2026-10-10 | PROD-101 ×1 (₹45,000) + PROD-102 ×2 (₹1,200 ea) + PROD-105 ×1 (₹300) | ₹47,700.00 | issued | unpaid |
| INV-206 | CUST-104 | 2026-10-15 | PROD-103 ×10 (₹500 ea) + PROD-105 ×5 (₹300 ea) | ₹6,500.00 | issued | partially_paid |

**Product Catalog:**

| Product | Name | Category | Price |
|---------|------|----------|-------|
| PROD-101 | Laptop Pro X1 | Electronics | ₹45,000.00 |
| PROD-102 | Wireless Mouse | Accessories | ₹1,200.00 |
| PROD-103 | USB-C Hub | Accessories | ₹500.00 |
| PROD-104 | Cloud Suite License | Software | ₹8,000.00 |
| PROD-105 | Screen Protector Pack | Accessories | ₹300.00 |

**Validation flow:**
1. Build `LineItem` and `InvoiceSeed` Pydantic models for each invoice
2. Call `validate_product_ids()` against the set of seeded product IDs
3. If all pass, insert via SQLAlchemy
4. If any fail, raise with clear error message

---

### Component 10: Test Suite

#### [NEW] `tests/conftest.py`
Shared pytest fixtures:
- Mock LLM client (returns predetermined JSON for routing and SQL generation)
- Test database setup (optional — can use mocked `execute_readonly_query`)

---

#### [NEW] `tests/test_security.py`
Tests for `validate_sql()`:

| Test Case | Input | Expected |
|-----------|-------|----------|
| Reject DELETE | `DELETE FROM invoices` | `ValidationError` |
| Reject DROP | `DROP TABLE invoices` | `ValidationError` |
| Reject UPDATE | `UPDATE invoices SET ...` | `ValidationError` |
| Reject INSERT | `INSERT INTO invoices ...` | `ValidationError` |
| Reject multi-statement | `SELECT 1; DROP TABLE invoices` | `ValidationError` |
| Reject COPY | `COPY invoices TO '/tmp/x'` | `ValidationError` |
| Reject pg_catalog | `SELECT * FROM pg_catalog.pg_tables` | `ValidationError` |
| Reject information_schema | `SELECT * FROM information_schema.tables` | `ValidationError` |
| Reject unknown table | `SELECT * FROM secrets` | `ValidationError` |
| Reject unknown column | `SELECT password FROM customers` | `ValidationError` |
| Reject pg_sleep | `SELECT pg_sleep(5)` | `ValidationError` |
| Reject pg_read_file | `SELECT pg_read_file('/etc/passwd')` | `ValidationError` |
| Enforce LIMIT (none) | `SELECT * FROM customers` | SQL rewritten with `LIMIT 100` |
| Enforce LIMIT (too high) | `SELECT * FROM customers LIMIT 5000` | SQL rewritten with `LIMIT 100` |
| Reject missing params | SQL has `:x` but params = {} | `ValidationError` |
| Reject extra params | SQL has no params but params = {x: 1} | `ValidationError` |

---

#### [NEW] `tests/test_query_engine.py`
Tests for JSONB queries, aggregations, and seed validation:

| Test Case | What it verifies |
|-----------|-----------------|
| JSONB lateral join accepted | `validate_sql` passes for canonical `CROSS JOIN LATERAL jsonb_array_elements(i.items) AS item(value)` |
| INV-205 multi-product results | Query returns 3 products with correct quantities and unit prices |
| Unpaid total no double-count | `SUM(total_amount)` WHERE unpaid + issued = correct total (not multiplied by item count) |
| Void excluded from aggregation | `SUM(total_amount)` excludes INV-204 (void) |
| Seed validation: mismatched total | `InvoiceSeed` with wrong `total_amount` raises `ValidationError` |
| Seed validation: invalid product_id | `InvoiceSeed` with `PROD-999` raises `ValidationError` |
| Seed validation: zero quantity | `LineItem` with `quantity=0` raises `ValidationError` |
| Seed validation: negative line_total | `LineItem` with wrong `line_total` calc raises `ValidationError` |

---

#### [NEW] `tests/test_routing.py`
Tests for intent routing:

| Prompt | Expected Route |
|--------|---------------|
| "Show invoice INV-205" | `InvoiceSkill` |
| "Show unpaid invoices" | `InvoiceSkill` |
| "Which products are in invoice INV-205?" | `InvoiceSkill` |
| "Show all products in electronics" | `GeneralQuery` |
| "Find customer CUST-101's email" | `GeneralQuery` |
| "Show the latest one" (no context) | `clarification_required` |
| "Delete all invoices" | `rejected` |
| "Drop the customers table" | `rejected` |

> [!NOTE]
> Routing tests will mock the LLM to return deterministic `RouteDecision` JSON, so they don't require live API calls.

---

#### [NEW] `tests/test_api.py`
Tests for FastAPI endpoints:

| Test Case | What it verifies |
|-----------|-----------------|
| GET /health (DB up) | Returns 200 with `db_status: "connected"` |
| GET /health (DB down) | Returns 503 with `db_status: "unavailable"` |
| POST /api/chat structure | Response matches `ChatResponse` schema |
| Decimal serialization | `total_amount` appears as `"47700.00"` string, not float |
| Empty message rejected | 422 validation error for empty `message` |

---

### Component 11: Configuration Files

#### [NEW] `.env.example`

```env
# Database
DATABASE_URL=postgresql://poc_readonly_user:readonly_pass@localhost:5432/invoice_poc

# LLM Provider: "gemini" or "openai"
LLM_PROVIDER=gemini

# Gemini
GEMINI_API_KEY=your-gemini-api-key-here
GEMINI_MODEL=gemini-2.0-flash

# OpenAI (alternative)
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_MODEL=gpt-4o-mini

# App
APP_TIMEZONE=Asia/Kolkata
```

#### [NEW] `requirements.txt`

```text
fastapi==0.115.*
uvicorn[standard]==0.34.*
sqlalchemy==2.0.*
psycopg2-binary==2.9.*
pydantic==2.10.*
sqlglot==26.*
streamlit==1.45.*
requests==2.32.*
python-dotenv==1.1.*
google-generativeai==0.8.*
openai==1.82.*
pytest==8.3.*
httpx==0.28.*
```

#### [MODIFY] `README.md`

Complete setup and usage guide:
1. Prerequisites (Python 3.11+, PostgreSQL)
2. Installation steps
3. Database setup (`psql -f schema.sql`, seed data)
4. Environment configuration
5. Running the app (FastAPI + Streamlit)
6. Demo questions
7. Running tests

---

## Demo Questions Verification Matrix

All 12 demo questions mapped to their expected routing and behavior:

| # | Question | Route | Query Type | Key Assertion |
|---|----------|-------|------------|---------------|
| 1 | Show invoice INV-205 | InvoiceSkill | Header query | Returns INV-205 details |
| 2 | Show the latest invoice for customer CUST-101 | InvoiceSkill | Header + ORDER BY | Returns INV-205 (Oct 10) |
| 3 | Which customer does invoice INV-205 belong to? | InvoiceSkill | JOIN customers | Returns CUST-101 name |
| 4 | Which products are included in invoice INV-205? | InvoiceSkill | JSONB expansion | Returns 3 products |
| 5 | Show each product's quantity and price in INV-205 | InvoiceSkill | JSONB expansion | Qty + unit_price per item |
| 6 | Show all unpaid invoices | InvoiceSkill | Filter payment_status | Excludes void, shows unpaid |
| 7 | Show unpaid invoices above ₹10,000 | InvoiceSkill | Filter + amount check | Returns INV-205 only |
| 8 | Find invoices issued last month | InvoiceSkill | Date range filter | Returns Sep 2026 invoices |
| 9 | Calculate the total value of unpaid invoices | InvoiceSkill | SUM aggregation | No double-counting |
| 10 | Show all products in electronics category | GeneralQuery | Simple filter | Returns PROD-101 |
| 11 | Find customer CUST-101's email | GeneralQuery | Simple lookup | Returns email |
| 12 | How many invoices does each customer have? | InvoiceSkill | GROUP BY + COUNT | Per-customer counts |

---

## Verification Plan

### Automated Tests

```bash
# Run full test suite
pytest tests/ -v

# Run specific test files
pytest tests/test_security.py -v      # SQL injection & validation
pytest tests/test_query_engine.py -v  # JSONB, aggregations, seed validation
pytest tests/test_routing.py -v       # Intent classification
pytest tests/test_api.py -v           # API endpoint contracts
```

### Manual Verification

1. **Database setup:**
   - Run `schema.sql` against PostgreSQL
   - Run `seed_data.py` to populate tables
   - Verify 4 customers, 5 products, 6 invoices exist

2. **Start the services:**
   ```bash
   # Terminal 1: FastAPI backend
   uvicorn main:app --reload --port 8000
   
   # Terminal 2: Streamlit frontend
   streamlit run app.py
   ```

3. **Health check:**
   ```bash
   curl http://localhost:8000/health
   # Expected: {"app_status": "healthy", "db_status": "connected"}
   ```

4. **Run all 12 demo questions** through the Streamlit UI and verify:
   - Correct routing (check `capability_used` badge)
   - Accurate data returned
   - Natural language answer is coherent
   - Data table renders properly for multi-row results

5. **Security smoke tests:**
   - Try "Delete all invoices" → should return `rejected`
   - Try "Show me the pg_catalog tables" → should fail validation

6. **Edge cases:**
   - Empty message → 422 error
   - Very long message → truncated at 1000 chars
   - Question about void invoices → should return INV-204 when explicitly asked

---

## Implementation Order

The recommended build sequence (dependencies flow top-down):

```mermaid
flowchart TD
    A["1. models.py<br/>(Pydantic models — no deps)"] --> B["2. database.py<br/>(SQLAlchemy engine)"]
    A --> C["3. llm_client.py<br/>(LLM adapter)"]
    B --> D["4. schema.sql<br/>(DDL)"]
    A --> E["5. seed_data.py<br/>(Seed generator)"]
    D --> E
    C --> F["6. skills/invoice.py<br/>(InvoiceSkill rules)"]
    B --> G["7. query_engine.py<br/>(Validator + executor)"]
    C --> G
    F --> H["8. agent.py<br/>(Router + orchestrator)"]
    G --> H
    H --> I["9. main.py<br/>(FastAPI)"]
    I --> J["10. app.py<br/>(Streamlit UI)"]
    A --> K["11. tests/<br/>(All test files)"]
    G --> K
    H --> K
    I --> K
    J --> L["12. README.md<br/>(.env.example, requirements.txt)"]
```

**Build order:**
1. `models.py` — foundation, no dependencies
2. `database.py` — engine + execution helper
3. `llm_client.py` — LLM adapter
4. `schema.sql` — database DDL
5. `seed_data.py` — data population
6. `skills/invoice.py` — InvoiceSkill rules
7. `query_engine.py` — the core validator/executor
8. `agent.py` — router + orchestrator
9. `main.py` — FastAPI endpoints
10. `app.py` — Streamlit UI
11. `tests/` — all test files
12. `README.md`, `.env.example`, `requirements.txt` — docs + config
