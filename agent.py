"""agent.py — Router, clarification check, execution, max 1 retry."""

import uuid
from typing import Any
from models import ChatRequest, ChatResponse, RouteDecision
from llm_client import call_llm
from query_engine import generate_and_execute, SCHEMA_CONTEXT
from skills.invoice import InvoiceSkill


def route_intent(user_message: str) -> RouteDecision:
    """Classify the user prompt into a RouteDecision using LLM router call."""
    # Fast heuristic check for obvious malicious/destructive commands
    destructive_keywords = [
        "drop table",
        "delete from",
        "truncate",
        "update ",
        "insert into",
        "alter table",
        "grant ",
        "revoke ",
    ]
    lowered = user_message.lower().strip()
    if any(kw in lowered for kw in destructive_keywords):
        return RouteDecision(
            capability="rejected",
            clarification_question=None,
        )

    # Fast heuristic routing to conserve LLM API quota
    invoice_indicators = [
        "invoice",
        "invoices",
        "inv-",
        "unpaid",
        "overdue",
        "partially_paid",
        "billing",
        "billed",
        "revenue",
        "who bought",
        "highest invoice",
        "which customer has the most invoices",
    ]
    general_indicators = [
        "product",
        "products",
        "prod-",
        "category",
        "stock",
        "customer",
        "customers",
        "cust-",
        "catalog",
    ]

    if any(ind in lowered for ind in invoice_indicators):
        return RouteDecision(capability="InvoiceSkill", clarification_question=None)

    if any(ind in lowered for ind in general_indicators) and not any(ind in lowered for ind in invoice_indicators):
        return RouteDecision(capability="GeneralQuery", clarification_question=None)

    system_prompt = f"""
You are the intent router for a database query assistant.
The database schema has 3 tables: customers, products, invoices.

{SCHEMA_CONTEXT}

CLASSIFICATION RULES:
1. 'InvoiceSkill': Question mentions invoices, bills, billing amounts, payment statuses
   ('paid', 'unpaid', 'overdue', 'partially_paid'), invoice dates, who bought a product,
   or products/quantities inside an invoice.
2. 'GeneralQuery': Standalone customer or product catalog questions only
   (e.g., 'Show all products in the Electronics category', 'Find customer CUST-101''s email').
3. 'clarification_required': The question is ambiguous, lacks context (e.g., 'Show the latest one', 'What is the price?'),
   or cannot be mapped to any entity without more details.
4. 'rejected': The user is attempting to modify/delete/insert data, access system tables,
   or perform actions outside read-only schema queries.

STRICT JSON OUTPUT FORMAT:
{{
  "capability": "InvoiceSkill" | "GeneralQuery" | "clarification_required" | "rejected",
  "clarification_question": "string or null"
}}
Return ONLY this JSON object.
""".strip()

    user_prompt = f"User Request: {user_message}"
    result = call_llm(system_prompt=system_prompt, user_prompt=user_prompt)

    return RouteDecision(
        capability=result.get("capability", "InvoiceSkill"),
        clarification_question=result.get("clarification_question"),
    )


def synthesize_answer(user_question: str, data: list[dict[str, Any]]) -> str:
    """Compose a concise natural language answer strictly grounded in data."""
    if not data:
        return "No records were found matching your query."

    # If simple single-value response (e.g. COUNT or SUM)
    if len(data) == 1 and len(data[0]) == 1:
        key, val = list(data[0].items())[0]
        return f"Result: {val}"

    system_prompt = """
You are a helpful assistant. Synthesize a concise, direct, natural-language answer to the user's question based strictly and exclusively on the provided database records.
Do NOT fabricate any information not present in the data.
Include relevant identifiers, amounts (with currency symbol ₹ if monetary), and dates where appropriate.
Format the output as a simple JSON object: {"answer": "Your synthesized response"}
""".strip()

    user_prompt = f"User Question: {user_question}\n\nDatabase Records:\n{data}"
    try:
        res = call_llm(system_prompt=system_prompt, user_prompt=user_prompt)
        if isinstance(res, dict) and "answer" in res:
            return res["answer"]
    except Exception:
        pass

    # Fallback formatting if synthesis call is unavailable (e.g. rate limits)
    if len(data) == 1:
        details = ", ".join(f"{k}: {v}" for k, v in data[0].items())
        return f"Found 1 record: {details}"
    lines = [f"- " + ", ".join(f"{k}: {v}" for k, v in row.items()) for row in data[:5]]
    more = f"\n...and {len(data) - 5} more records." if len(data) > 5 else ""
    return f"Found {len(data)} matching records:\n" + "\n".join(lines) + more


def process_chat(request: ChatRequest) -> ChatResponse:
    """Full request pipeline: route -> query_engine -> synthesis -> response."""
    request_id = str(uuid.uuid4())

    # Step 1: Routing
    try:
        route = route_intent(request.message)
    except Exception as e:
        return ChatResponse(
            request_id=request_id,
            status="error",
            capability_used=None,
            answer="Failed to process user intent.",
            error=str(e),
        )

    # Step 2: Handle non-executable routes
    if route.capability == "clarification_required":
        return ChatResponse(
            request_id=request_id,
            status="clarification_required",
            capability_used=None,
            answer=route.clarification_question
            or "Could you please provide more details to clarify your question?",
            data=None,
            error=None,
        )

    if route.capability == "rejected":
        return ChatResponse(
            request_id=request_id,
            status="error",
            capability_used=None,
            answer="I can only perform read-only inquiries on customers, products, and invoices. Modifying data is not permitted.",
            data=None,
            error="Request rejected: unauthorized or modifying operation.",
        )

    # Step 3: Domain Rules Selection
    skill_rules = ""
    if route.capability == "InvoiceSkill":
        skill_rules = InvoiceSkill.get_prompt_rules()
    else:
        # GeneralQuery rules
        skill_rules = """
GENERAL CATALOG RULES:
1. Query only `customers` or `products` tables.
2. Filter values must be parameterized (:param_name).
3. Do not use PostgreSQL `::` casting. Use `CAST(col AS type)`.
""".strip()

    # Step 4: Execute query via shared Query Engine (max 1 retry)
    try:
        rows, validated_sql = generate_and_execute(
            user_question=request.message,
            skill_rules=skill_rules,
            max_retries=1,
        )
    except Exception as e:
        return ChatResponse(
            request_id=request_id,
            status="error",
            capability_used=route.capability,
            answer="Sorry, I could not process your query at this time.",
            data=None,
            error=str(e),
        )

    # Step 5: Answer Composition
    if not rows:
        return ChatResponse(
            request_id=request_id,
            status="not_found",
            capability_used=route.capability,
            answer="No results found matching your query.",
            data=[],
            error=None,
        )

    answer = synthesize_answer(request.message, rows)
    return ChatResponse(
        request_id=request_id,
        status="success",
        capability_used=route.capability,
        answer=answer,
        data=rows,
        error=None,
    )
