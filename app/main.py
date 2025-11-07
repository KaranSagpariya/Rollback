"""FastAPI application entry-point for the risk estimator service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .config import Settings, get_settings
from .models import (
    CICDHookRequest,
    CICDHookResponse,
    ExportResponse,
    HealthResponse,
    HistoricalSimulationResult,
    ServiceMetrics,
    SimulationResult,
    SummaryResponse,
)
from .risk_engine import RiskEngine
from .storage import SimulationStorage
from .viz import render_dependency_graph, render_risk_barchart

settings: Settings = get_settings()
risk_engine = RiskEngine(settings=settings)
simulation_storage = SimulationStorage(settings=settings)

app = FastAPI(
    title="Rolling Update Risk Estimator",
    version="1.0.0",
    description=(
        "Pre-deployment risk assessment system leveraging dependency graphs "
        "and historical failure analytics to support rolling update decisions."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_engine() -> RiskEngine:
    """FastAPI dependency returning the singleton risk engine."""
    return risk_engine


def get_storage() -> SimulationStorage:
    """FastAPI dependency returning the in-memory storage component."""
    return simulation_storage


@app.get("/health", response_model=HealthResponse, tags=["Operational"])
def health_check() -> HealthResponse:
    """Return a simple heartbeat payload."""
    return HealthResponse(status="ok", timestamp_utc=datetime.now(timezone.utc))


@app.post(
    "/simulate",
    response_model=SimulationResult,
    summary="Run a risk simulation",
    tags=["Simulation"],
    response_description="Latest risk metrics for all services.",
    responses={
        200: {
            "description": "Simulation result",
            "content": {
                "application/json": {
                    "example": {
                        "summary": {
                            "average_risk": 58.4,
                            "highest_risk_service": "orders-service",
                            "highest_risk_score": 82.3,
                            "blocked_services": ["orders-service"],
                            "blocked_count": 1,
                            "timestamp_utc": "2025-11-07T01:45:00Z",
                        },
                        "services": [
                            {
                                "service_name": "auth-service",
                                "dependency_impact_score": 42.1,
                                "rollback_rate": 33.4,
                                "change_frequency": 55.1,
                                "error_spike_history": 48.6,
                                "latency_instability": 36.7,
                                "risk_score": 45.3,
                                "decision": "Manual Review",
                            },
                            {
                                "service_name": "orders-service",
                                "dependency_impact_score": 91.4,
                                "rollback_rate": 65.0,
                                "change_frequency": 72.2,
                                "error_spike_history": 58.9,
                                "latency_instability": 49.3,
                                "risk_score": 82.3,
                                "decision": "Block Deployment",
                            },
                        ],
                        "edges": [
                            {"source": "inventory-service", "target": "orders-service"},
                            {"source": "payment-service", "target": "orders-service"},
                        ],
                    }
                }
            },
        }
    },
)
def simulate(
    engine: RiskEngine = Depends(get_engine),
    storage: SimulationStorage = Depends(get_storage),
    seed: Optional[int] = None,
) -> SimulationResult:
    """
    Execute a new simulation run using the current history context.

    The response includes service-level metrics, dependency edges, and
    aggregated summary statistics.
    """
    result = _execute_simulation(engine, storage, seed=seed)
    return result


@app.post(
    "/simulate/historical",
    response_model=HistoricalSimulationResult,
    summary="Run simulation and include history",
    tags=["Simulation"],
)
def simulate_with_history(
    engine: RiskEngine = Depends(get_engine),
    storage: SimulationStorage = Depends(get_storage),
    seed: Optional[int] = None,
) -> HistoricalSimulationResult:
    """Execute a simulation and return the result with historical context."""
    result = _execute_simulation(engine, storage, seed=seed)
    history = storage.history
    return HistoricalSimulationResult(
        summary=result.summary,
        services=result.services,
        edges=result.edges,
        history=history,
    )


@app.get(
    "/services",
    response_model=SimulationResult,
    summary="Retrieve the latest simulation data",
    tags=["Simulation"],
)
def get_services(storage: SimulationStorage = Depends(get_storage)) -> SimulationResult:
    """Return the most recently computed simulation result."""
    latest = storage.latest_result
    if latest is None:
        raise HTTPException(status_code=404, detail="No simulation results available yet.")
    return latest


@app.get(
    "/summary",
    response_model=SummaryResponse,
    summary="Get summary metrics",
    tags=["Insights"],
)
def get_summary(storage: SimulationStorage = Depends(get_storage)) -> SummaryResponse:
    """Return summary metrics from the most recent simulation."""
    latest = storage.latest_result
    if latest is None:
        raise HTTPException(status_code=404, detail="Simulation not run yet.")
    summary = latest.summary
    return SummaryResponse(
        average_risk=summary.average_risk,
        highest_risk_service=summary.highest_risk_service,
        highest_risk_score=summary.highest_risk_score,
        blocked_count=summary.blocked_count,
    )


@app.get(
    "/graph.png",
    response_class=FileResponse,
    summary="Visualise the dependency graph",
    tags=["Visualisations"],
)
def graph_image(
    storage: SimulationStorage = Depends(get_storage),
    engine: RiskEngine = Depends(get_engine),
) -> FileResponse:
    """Generate and return the dependency graph visualisation."""
    latest = storage.latest_result
    if latest is None:
        latest = _execute_simulation(engine, storage)
    output_path = settings.graph_image_path
    render_dependency_graph(latest, output_path)
    return FileResponse(output_path, media_type="image/png")


@app.get(
    "/barchart.png",
    response_class=FileResponse,
    summary="Visualise service risk comparison",
    tags=["Visualisations"],
)
def barchart_image(
    storage: SimulationStorage = Depends(get_storage),
    engine: RiskEngine = Depends(get_engine),
) -> FileResponse:
    """Generate and return the risk comparison bar chart."""
    latest = storage.latest_result
    if latest is None:
        latest = _execute_simulation(engine, storage)
    output_path = settings.barchart_image_path
    render_risk_barchart(latest, output_path)
    return FileResponse(output_path, media_type="image/png")


@app.post(
    "/export",
    response_model=ExportResponse,
    summary="Export current run to CSV",
    tags=["Insights"],
)
def export_data(
    engine: RiskEngine = Depends(get_engine),
    storage: SimulationStorage = Depends(get_storage),
) -> ExportResponse:
    """Export the latest simulation data to CSV and return file metadata."""
    latest = storage.latest_result
    if latest is None:
        latest = _execute_simulation(engine, storage)
    export_metadata = storage.export(engine, latest)
    return export_metadata


@app.post(
    "/cicd-hook",
    response_model=CICDHookResponse,
    summary="Trigger risk assessment from CI/CD",
    tags=["CI/CD"],
    responses={
        200: {
            "description": "Risk assessment result",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Risk Estimator Hook Triggered → Calculated Risk Score = 82. Deployment Blocked.",
                        "risk_score": 82.0,
                        "decision": "Block Deployment",
                    }
                }
            },
        }
    },
)
def cicd_hook(
    payload: CICDHookRequest,
    engine: RiskEngine = Depends(get_engine),
    storage: SimulationStorage = Depends(get_storage),
) -> CICDHookResponse:
    """Perform a risk assessment for a CI/CD deployment trigger."""
    result = _execute_simulation(engine, storage)
    service_metric = _find_service_metric(result, payload.service_name)

    message = (
        "Risk Estimator Hook Triggered → Calculated Risk Score = "
        f"{service_metric.risk_score:.0f}. {service_metric.decision.value}."
    )
    return CICDHookResponse(
        message=message,
        risk_score=service_metric.risk_score,
        decision=service_metric.decision,
    )


def _execute_simulation(
    engine: RiskEngine,
    storage: SimulationStorage,
    seed: Optional[int] = None,
) -> SimulationResult:
    """Helper to execute a simulation and persist its history."""
    history_snapshot = storage.snapshot()
    result = engine.run_simulation(history_snapshot, seed=seed)
    history_entry = engine.build_history_entry(result)
    storage.record(history_entry, result=result)
    return result


def _find_service_metric(result: SimulationResult, service_name: str) -> ServiceMetrics:
    """Locate metrics for a specific service within a result set."""
    for metric in result.services:
        if metric.service_name == service_name:
            return metric
    # Default to the highest risk service when requested service is absent.
    highest = max(result.services, key=lambda svc: svc.risk_score)
    return highest


