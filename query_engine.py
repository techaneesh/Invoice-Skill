"""query_engine.py — Schema context, SQLGlot AST validator, safe SQLAlchemy executor."""

import re
from typing import Any
import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from database import execute_readonly_query
from llm_client import call_llm
from models import GeneratedSQL

# --- 1. Schema Context ---

SCHEMA_CONTEXT = """
PostgreSQL database with exactly 3 tables:

TABLE customers (
    customer_id VARCHAR(32) PRIMARY KEY,     -- e.g. 'CUST-101'
    name VARCHAR(120) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    phone VARCHAR(30),
    city VARCHAR(80),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

TABLE products (
    product_id VARCHAR(32) PRIMARY KEY,      -- e.g. 'PROD-101'
    name VARCHAR(150) NOT NULL,
    category VARCHAR(80) NOT NULL,          -- e.g. 'Electronics', 'Software', 'Accessories'
    description TEXT,
    price NUMERIC(12,2) NOT NULL,           -- Current catalog price
    stock_quantity INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

TABLE invoices (
    id SERIAL PRIMARY KEY,
    invoice_number VARCHAR(32) UNIQUE NOT NULL, -- e.g. 'INV-205'
    customer_id VARCHAR(32) NOT NULL REFERENCES customers(customer_id),
    invoice_date DATE NOT NULL,
    items JSONB NOT NULL,                   -- Array of: [{"product_id": "...", "quantity": 1, "unit_price": 45000.00, "line_total": 45000.00}]
    total_amount NUMERIC(12,2) NOT NULL,
    invoice_status VARCHAR(32) NOT NULL,    -- 'issued' or 'void'
    payment_status VARCHAR(32) NOT NULL,    -- 'unpaid', 'partially_paid', 'paid', 'overdue'
    created_at TIMESTAMPTZ DEFAULT NOW()
);
""".strip()

# --- 2. Security Allowlists ---

ALLOWED_TABLES = {"customers", "products", "invoices"}

ALLOWED_COLUMNS = {
    "customers": {"customer_id", "name", "email", "phone", "city", "created_at"},
    "products": {
        "product_id",
        "name",
        "category",
        "description",
        "price",
        "stock_quantity",
        "created_at",
    },
    "invoices": {
        "id",
        "invoice_number",
        "customer_id",
        "invoice_date",
        "items",
        "total_amount",
        "invoice_status",
        "payment_status",
        "created_at",
    },
    "item": {"value"},  # Derived lateral table alias for jsonb_array_elements
}

ALLOWED_FUNCTIONS = {
    "COUNT",
    "SUM",
    "AVG",
    "MIN",
    "MAX",
    "COALESCE",
    "LOWER",
    "UPPER",
    "ROUND",
    "CAST",
    "DATE_TRUNC",
    "EXTRACT",
    "CURRENT_DATE",
    "NOW",
    "JSONB_ARRAY_ELEMENTS",
    "JSONEXTRACT",
    "JSONEXTRACTSCALAR",
    "ARRAY_AGG",
    "STRING_AGG",
}

BLOCKED_FUNCTIONS = {
    "PG_SLEEP",
    "PG_READ_FILE",
    "CURRENT_SETTING",
    "SET_CONFIG",
    "DBLINK",
    "LO_IMPORT",
    "LO_EXPORT",
    "PG_TERMINATE_BACKEND",
    "PG_CANCEL_BACKEND",
    "SYSTEM",
}

MAX_LIMIT = 100


def validate_sql(sql_query: str, parameters: dict[str, Any] | None = None) -> str:
    """Strictly validate SQL query and parameters using SQLGlot AST inspection.

    Ensures:
    1. Single-statement SELECT query only (reject DDL, DML, multi-statement, INTO).
    2. Exact parameter binding match (:param_name vs parameters dict).
    3. Tables and schemas allowlist (only public/no-schema customers, products, invoices, and lateral alias 'item').
    4. Columns allowlist against known table schemas.
    5. Functions allowlist (reject blocked/system functions).
    6. Programmatic LIMIT enforcement (clamp or inject LIMIT 100).

    Returns:
        Validated (and potentially LIMIT-clamped) SQL string.
    """
    if parameters is None:
        parameters = {}

    if not sql_query or not sql_query.strip():
        raise ValueError("SQL query cannot be empty.")

    # 1. Parameter binding verification using regex
    # Match named bind parameters :name (excluding double colon :: casts which are disallowed anyway)
    # Negative lookbehind and lookahead to avoid ::
    placeholders = set(re.findall(r"(?<!:):([a-zA-Z_][a-zA-Z0-9_]*)(?!:)", sql_query))
    param_keys = set(parameters.keys())

    missing_params = placeholders - param_keys
    if missing_params:
        raise ValueError(
            f"Query contains parameter placeholder(s) missing from parameters dict: {missing_params}"
        )

    extra_params = param_keys - placeholders
    if extra_params:
        raise ValueError(
            f"Parameters dict contains key(s) not found in query placeholders: {extra_params}"
        )

    # 2. Parse with SQLGlot postgres dialect
    try:
        parsed_statements = sqlglot.parse(sql_query, read="postgres")
    except ParseError as e:
        raise ValueError(f"SQL parsing error: {e}") from e

    if len(parsed_statements) != 1:
        raise ValueError(
            f"Expected exactly 1 SQL statement, got {len(parsed_statements)}. Multi-statement queries are strictly forbidden."
        )

    stmt = parsed_statements[0]
    if not isinstance(stmt, exp.Select):
        raise ValueError(
            f"Only SELECT queries are allowed. Received root AST node type: {type(stmt).__name__}"
        )

    # Reject INTO clauses (e.g. SELECT ... INTO new_table)
    if stmt.args.get("into"):
        raise ValueError("SELECT INTO clauses are strictly forbidden.")

    # Reject locking clauses (e.g. FOR UPDATE, FOR SHARE)
    if stmt.args.get("locks"):
        raise ValueError("Locking clauses (FOR UPDATE/SHARE) are strictly forbidden.")

    # 3. Table and Schema Allowlist
    # Build alias map: alias -> physical table name (or virtual 'item')
    alias_to_table: dict[str, str] = {}
    cte_names: set[str] = set()

    # Track CTEs if any
    with_clause = stmt.args.get("with")
    if with_clause:
        for cte in with_clause.expressions:
            if isinstance(cte, exp.CTE) and cte.alias:
                cte_names.add(cte.alias.lower())

    for table in stmt.find_all(exp.Table):
        # Schema verification
        db = table.db
        if db and db.lower() not in {"public", ""}:
            raise ValueError(
                f"Access to schema '{db}' is forbidden. Only application tables in the default schema are allowed."
            )

        tbl_name = table.name.lower()
        alias = table.alias.lower() if table.alias else tbl_name

        if tbl_name in ALLOWED_TABLES:
            alias_to_table[alias] = tbl_name
            alias_to_table[tbl_name] = tbl_name
        elif tbl_name in cte_names:
            alias_to_table[alias] = tbl_name
        elif tbl_name in {"item", "items"}:
            # Allow lateral alias if referenced as table
            alias_to_table[alias] = "item"
        else:
            raise ValueError(
                f"Table '{tbl_name}' is not in the allowed tables list: {ALLOWED_TABLES}"
            )

    # Check for lateral derived table aliases like jsonb_array_elements(...) AS item(value)
    for lateral in stmt.find_all(exp.Lateral):
        if lateral.alias:
            alias_to_table[lateral.alias.lower()] = "item"

    # Also check joins for lateral functions
    for join in stmt.find_all(exp.Join):
        this = join.this
        if isinstance(this, (exp.Lateral, exp.Anonymous, exp.Func)):
            if join.alias:
                alias_to_table[join.alias.lower()] = "item"

    # 4. Column Allowlist
    all_allowed_columns = set()
    for col_set in ALLOWED_COLUMNS.values():
        all_allowed_columns.update(col_set)

    for col in stmt.find_all(exp.Column):
        col_name = col.name.lower()
        # Wildcard '*' is allowed
        if col_name == "*":
            continue

        table_qualifier = col.table.lower() if col.table else None
        if table_qualifier:
            resolved_table = alias_to_table.get(table_qualifier)
            if resolved_table in ALLOWED_COLUMNS:
                if col_name not in ALLOWED_COLUMNS[resolved_table]:
                    raise ValueError(
                        f"Column '{col_name}' does not exist on table '{resolved_table}'."
                    )
            elif resolved_table in cte_names:
                # Column is on a valid CTE
                pass
            elif table_qualifier in ALLOWED_COLUMNS:
                if col_name not in ALLOWED_COLUMNS[table_qualifier]:
                    raise ValueError(
                        f"Column '{col_name}' does not exist on table '{table_qualifier}'."
                    )
            else:
                raise ValueError(
                    f"Unknown or disallowed table qualifier '{table_qualifier}' for column '{col_name}'."
                )
        else:
            # Unaliased column: must belong to at least one allowed table or CTE
            if col_name not in all_allowed_columns and not cte_names:
                raise ValueError(
                    f"Column '{col_name}' is not in the allowed schema columns."
                )

    # 5. Function Allowlist
    for func in stmt.find_all((exp.Func, exp.Anonymous)):
        if isinstance(
            func,
            (
                exp.Connector,
                exp.Binary,
                exp.Unary,
                exp.Between,
                exp.In,
            ),
        ):
            continue

        func_name = ""
        if isinstance(func, exp.Anonymous):
            func_name = func.name.upper()
        else:
            func_name = func.key.upper()

        if func_name in BLOCKED_FUNCTIONS:
            raise ValueError(f"Function '{func_name}' is strictly blocked for security.")

        # If it's a built-in expression that maps to standard SQL (like CAST, EXTRACT, etc.)
        # sqlglot represents them as specific AST classes
        base_func_name = getattr(func, "sql_name", lambda: func_name)().upper()
        if func_name not in ALLOWED_FUNCTIONS and base_func_name not in ALLOWED_FUNCTIONS:
            # Check if it's an approved standard expression
            if not isinstance(
                func,
                (
                    exp.Cast,
                    exp.Count,
                    exp.Sum,
                    exp.Avg,
                    exp.Min,
                    exp.Max,
                    exp.Round,
                    exp.Lower,
                    exp.Upper,
                    exp.Coalesce,
                    exp.CurrentDate,
                    exp.CurrentTimestamp,
                    exp.Extract,
                    exp.DateTrunc,
                    exp.Trim,
                    exp.JSONExtract,
                    exp.JSONExtractScalar,
                    exp.JSONBExtract,
                    exp.JSONBExtractScalar,
                ),
            ):
                raise ValueError(
                    f"Function '{func_name}' is not in the allowed functions list."
                )

    # 6. Programmatic Row Limit Enforcement
    limit_node = stmt.args.get("limit")
    needs_limit_injection = False

    if limit_node is None:
        needs_limit_injection = True
        limit_val = MAX_LIMIT
    else:
        # Extract limit value
        limit_expr = limit_node.expression
        if isinstance(limit_expr, exp.Literal):
            try:
                val = int(limit_expr.this)
                if val > MAX_LIMIT or val <= 0:
                    needs_limit_injection = True
                    limit_val = MAX_LIMIT
                else:
                    limit_val = val
            except (ValueError, TypeError):
                needs_limit_injection = True
                limit_val = MAX_LIMIT
        else:
            needs_limit_injection = True
            limit_val = MAX_LIMIT

    if needs_limit_injection:
        # If the original query already had a LIMIT clause, replace it
        if limit_node is not None:
            # Replace existing limit with 100
            limit_pattern = re.compile(r"\bLIMIT\s+\d+\b", re.IGNORECASE)
            if limit_pattern.search(sql_query):
                validated_sql = limit_pattern.sub(f"LIMIT {limit_val}", sql_query)
                return validated_sql.strip()

        # Otherwise append LIMIT 100
        validated_sql = sql_query.rstrip("; \t\n") + f" LIMIT {limit_val}"
        return validated_sql

    return sql_query.strip()


def generate_sql(
    user_question: str,
    skill_rules: str = "",
    error_feedback: str | None = None,
) -> GeneratedSQL:
    """Prompt the LLM to generate structured SQL (query and parameters)."""
    system_prompt = f"""
You are an expert PostgreSQL SQL generator for an AI query agent.
Given the database schema and domain rules, generate a safe, parameterized PostgreSQL SELECT query.

{SCHEMA_CONTEXT}

{skill_rules}

STRICT OUTPUT REQUIREMENTS:
1. You must respond ONLY with a JSON object conforming to:
   {{
     "sql_query": "SELECT ... FROM ... WHERE column = :param_name ...",
     "parameters": {{"param_name": value}}
   }}
2. ALL filter values (ids, dates, amounts, statuses) MUST be bound via named parameters (`:param_name`).
3. Never interpolate raw user inputs into the query string.
4. Do NOT use PostgreSQL `::` casting (e.g. `::numeric`). Use `CAST(col AS NUMERIC)` instead.
5. Exclude void invoices unless explicitly asked.
6. Return ONLY the JSON object, with no markdown formatting or extra text.
""".strip()

    user_prompt = f"User Question: {user_question}"
    if error_feedback:
        user_prompt += f"\n\nPREVIOUS ATTEMPT FAILED WITH ERROR: {error_feedback}\nPlease correct the SQL query and parameters to fix this error."

    response_json = call_llm(system_prompt=system_prompt, user_prompt=user_prompt)

    if not isinstance(response_json, dict) or "sql_query" not in response_json:
        raise ValueError(f"Invalid LLM response format: {response_json}")

    return GeneratedSQL(
        sql_query=response_json["sql_query"],
        parameters=response_json.get("parameters", {}),
    )


def generate_and_execute(
    user_question: str,
    skill_rules: str = "",
    max_retries: int = 1,
) -> tuple[list[dict[str, Any]], str]:
    """Generate, validate, and execute SQL with bounded retry on failure.

    Returns:
        tuple of (rows, final_validated_sql)
    """
    last_error: str | None = None

    for attempt in range(max_retries + 1):
        try:
            # Step 1: Generate SQL
            gen = generate_sql(
                user_question=user_question,
                skill_rules=skill_rules,
                error_feedback=last_error if attempt > 0 else None,
            )

            # Step 2: Validate SQL with AST inspection
            validated_sql = validate_sql(gen.sql_query, gen.parameters)

            # Step 3: Execute safe query
            rows = execute_readonly_query(validated_sql, gen.parameters)
            return rows, validated_sql

        except Exception as e:
            last_error = str(e)
            if attempt >= max_retries:
                raise RuntimeError(
                    f"Query generation and execution failed after {max_retries + 1} attempt(s): {last_error}"
                ) from e

    raise RuntimeError("Unexpected termination of generate_and_execute.")
