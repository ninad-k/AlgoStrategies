from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import ensure_schemas
from app.routers import auth, upload, traders, strategies, accounts, attribution_rules, pnl, admin, execution

app = FastAPI(title="Trading Dashboard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    ensure_schemas()


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(upload.router, prefix="/api/v1/upload", tags=["upload"])
app.include_router(traders.router, prefix="/api/v1/traders", tags=["traders"])
app.include_router(strategies.router, prefix="/api/v1/strategies", tags=["strategies"])
app.include_router(accounts.router, prefix="/api/v1/accounts", tags=["accounts"])
app.include_router(attribution_rules.router, prefix="/api/v1/attribution-rules", tags=["attribution-rules"])
app.include_router(pnl.router, prefix="/api/v1/pnl", tags=["pnl"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(execution.router, prefix="/api/v1/execution", tags=["execution"])
