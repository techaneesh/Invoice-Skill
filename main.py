"""main.py — FastAPI endpoints: GET /health, POST /api/chat."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from models import ChatRequest, ChatResponse
from database import check_db_connection
from agent import process_chat

app = FastAPI(
    title="Invoice Agent POC API",
    description="Natural-language database query agent with specialized Invoice Skill",
    version="1.0.0",
)

# Enable CORS for frontend clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", status_code=200)
def health_check():
    """Application and database connectivity health check."""
    db_connected = check_db_connection()
    if db_connected:
        return {"app_status": "healthy", "db_status": "connected"}
    return JSONResponse(
        status_code=503,
        content={
            "app_status": "healthy",
            "db_status": "unavailable",
            "error": "Database connection check failed.",
        },
    )


@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """Process natural language questions and return structured SQL results."""
    return process_chat(request)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
