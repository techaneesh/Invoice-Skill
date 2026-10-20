"""models.py — All Pydantic models for the Invoice Agent POC."""

from decimal import Decimal
from typing import Optional, Literal
from pydantic import BaseModel, Field, model_validator


# --- API Models ---

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    session_id: str = Field(default="demo-session")


class ChatResponse(BaseModel):
    request_id: str
    status: Literal["success", "clarification_required", "not_found", "error"]
    capability_used: Optional[str] = None
    answer: str
    data: Optional[list[dict]] = None
    error: Optional[str] = None


# --- Routing Models ---

class RouteDecision(BaseModel):
    capability: Literal["InvoiceSkill", "GeneralQuery", "clarification_required", "rejected"]
    clarification_question: Optional[str] = None


# --- SQL Generation Models ---

class GeneratedSQL(BaseModel):
    sql_query: str
    parameters: dict = Field(default_factory=dict)


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
    invoice_status: Literal["issued", "void"]
    payment_status: Literal["unpaid", "partially_paid", "paid", "overdue"]

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
