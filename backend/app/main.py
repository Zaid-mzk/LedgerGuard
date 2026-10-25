from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.api.v1.routes import router

app = FastAPI(
    title="LedgerGuard API",
    version="1.0.0",
    description="Synthetic payment-integrity simulation. Not connected to banks or payment providers.",
)
origins = [settings.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(set(origins)),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)
app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.exception_handler(HTTPException)
async def safe_http_error(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {}
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": detail.get("code", "HTTP_ERROR"),
                "message": detail.get("message", "The request could not be completed"),
                "request_id": request.headers.get("x-request-id", "not-provided"),
            }
        },
    )


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    # Keep internal exception details out of API responses; server logs can be configured separately.
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "request_id": request.headers.get("x-request-id", "not-provided"),
            }
        },
    )
