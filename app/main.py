import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.endpoints import n8n, signing, documents
from db.database import Base, engine
from core.limiter import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all DB tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Ensure storage directories exist
    os.makedirs(os.getenv("UPLOAD_DIR", "./uploads"), exist_ok=True)
    os.makedirs(os.getenv("SIGNED_DIR", "./signed"), exist_ok=True)
    yield


app = FastAPI(title="PDF Signing Service", version="1.0.0", lifespan=lifespan)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — tighten origin list in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (for any future JS/CSS assets)
_STATIC_DIR = Path(__file__).parent / "static"
_STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# Routers
app.include_router(n8n.router, prefix="/api/v1", tags=["Internal API (n8n)"])
app.include_router(documents.router, prefix="/api/v1", tags=["Public Document API"])
app.include_router(signing.router, prefix="/sign", tags=["Public Signing"])


@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "service": "pdf-signing-service"}
