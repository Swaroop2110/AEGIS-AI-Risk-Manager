"""
AEGIS — Autonomous Evidence-Generating Intelligence System
Main FastAPI Application Entry Point

Razorpay AI Buildathon 2026 · Track 02: AI Risk Manager
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import uvicorn

from config import server_config, EVIDENCE_DIR
from database.connection import init_db

# Import routers
from api.routes_scoring import router as scoring_router
from api.routes_disputes import router as disputes_router
from api.routes_dashboard import router as dashboard_router
from api.routes_simulator import router as simulator_router
from api.routes_data import router as data_router
from api.routes_metrics import router as metrics_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    import sys
    # Ensure stdout supports UTF-8 on Windows
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-8-sig"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    # Startup
    print("=" * 60)
    print("[AEGIS] Autonomous Evidence-Generating Intelligence System")
    print("   Razorpay AI Buildathon 2026 - Track 02: AI Risk Manager")
    print("=" * 60)
    init_db()
    print("[AEGIS] All systems online.")
    yield
    # Shutdown
    print("[AEGIS] Shutting down...")


app = FastAPI(
    title="AEGIS — AI Risk Manager",
    description=(
        "Autonomous Evidence-Generating Intelligence System: "
        "Predictive chargeback prevention & autonomous dispute defense "
        "powered by Graph Neural Networks, Causal AI, and multi-agent representment."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=server_config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for evidence PDFs
app.mount("/evidence", StaticFiles(directory=str(EVIDENCE_DIR)), name="evidence")

# Register API routers
app.include_router(scoring_router, prefix="/api/v1/scoring", tags=["Scoring"])
app.include_router(disputes_router, prefix="/api/v1/disputes", tags=["Disputes"])
app.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["Dashboard"])
app.include_router(simulator_router, prefix="/api/v1/simulator", tags=["Simulator"])
app.include_router(data_router, prefix="/api/v1/data", tags=["Data Generation"])
app.include_router(metrics_router, prefix="/api/v1/metrics", tags=["Metrics & ROI"])


@app.get("/", tags=["Health"])
async def root():
    return {
        "name": "AEGIS",
        "version": "1.0.0",
        "description": "Autonomous Evidence-Generating Intelligence System",
        "status": "operational",
        "tracks": "Razorpay AI Buildathon 2026 — Track 02: AI Risk Manager",
        "modules": {
            "scoring_engine": "active",
            "dispute_defense": "active",
            "graph_intelligence": "active",
            "causal_ai": "active",
            "war_room": "active",
        }
    }


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": "aegis"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=server_config.host,
        port=server_config.port,
        reload=server_config.debug,
    )
