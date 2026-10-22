"""
Main FastAPI Application Entrypoint for TCWC-25 Financial Engine.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router as api_router

app = FastAPI(
    title="TCWC-25 Algorithmic-Reverse Expense & Age Calculator API",
    description=(
        "Production-grade financial engineering backend for horizon mapping, "
        "lifestyle inflation forecasting, lumpsum targeting, and real purchasing power preservation."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

# Mount alias for /api/plan-future and /api/calculator/when-reach-goal to directly support both /api and /api/v1 prefixes
from app.api.routes import plan_future, when_reach_goal
from app.schemas.plan_future import PlanFutureResponse, PlanFutureRequest
from app.schemas.when_reach_goal import WhenReachGoalResponse, WhenReachGoalRequest

app.add_api_route(
    "/api/plan-future",
    plan_future,
    methods=["POST"],
    response_model=PlanFutureResponse,
    summary="Direct /api/plan-future LLM-Powered Planning Endpoint",
    tags=["Calculator"]
)

app.add_api_route(
    "/api/calculator/when-reach-goal",
    when_reach_goal,
    methods=["POST"],
    response_model=WhenReachGoalResponse,
    summary="Direct /api/calculator/when-reach-goal Endpoint",
    tags=["Calculator"]
)



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
