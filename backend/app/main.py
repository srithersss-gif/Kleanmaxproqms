from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from backend.app.core.config import settings
from backend.app.api import api_router
from backend.app.seed_data import run_seed

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database tables and seed data exist
    try:
        run_seed()
    except Exception as e:
        print(f"Database init notice: {e}")
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Klean Max Pro — Commercial Quotation Automation and Area-Based Pricing System",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

# Guaranteed CORS middleware across all responses (including errors, exceptions & preflight OPTIONS)
@app.middleware("http")
async def cors_exception_handling_middleware(request: Request, call_next):
    origin = request.headers.get("origin") or "*"
    if request.method == "OPTIONS":
        res = Response(status_code=204)
        res.headers["Access-Control-Allow-Origin"] = origin
        res.headers["Access-Control-Allow-Credentials"] = "true"
        res.headers["Access-Control-Allow-Methods"] = "*"
        res.headers["Access-Control-Allow-Headers"] = "*"
        return res

    try:
        response = await call_next(request)
        if origin != "*":
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        else:
            response.headers["Access-Control-Allow-Origin"] = "*"
        return response
    except Exception as exc:
        import traceback
        err_msg = str(exc)
        trace = traceback.format_exc()
        print(f"Error on {request.method} {request.url.path}: {trace}")
        err_response = JSONResponse(
            status_code=500,
            content={
                "detail": err_msg,
                "error_type": type(exc).__name__,
                "path": request.url.path,
                "traceback": trace.splitlines()[-5:]
            }
        )
        if origin != "*":
            err_response.headers["Access-Control-Allow-Origin"] = origin
            err_response.headers["Access-Control-Allow-Credentials"] = "true"
        else:
            err_response.headers["Access-Control-Allow-Origin"] = "*"
        return err_response

# Standard CORSMiddleware with dynamic regex matching
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Mount static files and subdirectories for direct URL access
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
for sub in ["headers", "products", "unique_painters", "kleanmax"]:
    subdir = STATIC_DIR / sub
    if subdir.exists():
        app.mount(f"/{sub}", StaticFiles(directory=str(subdir)), name=f"static_{sub}")

# Include API Router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Root"])
def root():
    return {
        "status": "online",
        "service": "Klean Max Pro QMS API Backend",
        "version": "1.0.0",
        "docs": f"{settings.API_V1_STR}/docs",
        "health": "/api/health",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/{filename}.png")
@app.get("/{filename}.jpg")
@app.get("/{filename}.jpeg")
def get_root_static_image(filename: str):
    from fastapi.responses import FileResponse
    from fastapi import HTTPException
    for ext in [".png", ".jpg", ".jpeg"]:
        p = STATIC_DIR / f"{filename}{ext}"
        if p.exists():
            media = "image/png" if ext == ".png" else "image/jpeg"
            return FileResponse(p, media_type=media)
    raise HTTPException(status_code=404, detail="Image not found")


@app.get("/api/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "service": "Klean Max Pro QMS Backend",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/db-check", tags=["Health"])
def db_check():
    import traceback
    from sqlalchemy import text
    from backend.app.core.database import engine, db_url, db_init_error
    
    # Hide password in connection string for security
    safe_url = str(db_url)
    if "@" in safe_url and ":" in safe_url.split("@")[0]:
        prefix, rest = safe_url.split("@", 1)
        proto_user = prefix.rsplit(":", 1)[0]
        safe_url = f"{proto_user}:***@{rest}"
        
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            try:
                company_count = conn.execute(text("SELECT COUNT(*) FROM company_settings")).scalar()
            except Exception:
                company_count = "table_not_created"
        return {
            "status": "connected" if not db_init_error else "fallback_sqlite",
            "db_type": engine.name,
            "company_count": company_count,
            "test_query": result,
            "configured_url": safe_url,
            "db_init_warning": db_init_error
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc().splitlines()[-6:],
                "configured_url": safe_url,
                "db_init_warning": db_init_error
            }
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
