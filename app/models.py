"""Pydantic data models describing request and response payloads."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class DeploymentDecision(str, Enum):
    """Categorical outcome for a simulated deployment."""

    AUTO_APPROVE = "Auto Approve"
    MANUAL_REVIEW = "Manual Review"
    BLOCK_DEPLOYMENT = "Block Deployment"


class ServiceMetrics(BaseModel):
    """Aggregated risk metrics for an individual microservice node."""

    service_name: str = Field(..., description="Unique service identifier")
    dependency_impact_score: float = Field(..., ge=0, le=100)
    rollback_rate: float = Field(..., ge=0, le=100)
    change_frequency: float = Field(..., ge=0, le=100)
    error_spike_history: float = Field(..., ge=0, le=100)
    latency_instability: float = Field(..., ge=0, le=100)
    risk_score: float = Field(..., ge=0, le=100)
    decision: DeploymentDecision

    class Config:
        """Model configuration."""

        json_schema_extra = {
            "example": {
                "service_name": "orders-service",
                "dependency_impact_score": 65.2,
                "rollback_rate": 40.5,
                "change_frequency": 55.0,
                "error_spike_history": 38.1,
                "latency_instability": 42.7,
                "risk_score": 54.8,
                "decision": "Manual Review",
            }
        }


class GraphEdge(BaseModel):
    """Directed relationship between two services in the dependency graph."""

    source: str = Field(..., description="Upstream dependency")
    target: str = Field(..., description="Downstream dependent service")


class SimulationSummary(BaseModel):
    """High-level summary for a simulation run."""

    average_risk: float = Field(..., ge=0, le=100)
    highest_risk_service: str
    highest_risk_score: float = Field(..., ge=0, le=100)
    blocked_services: List[str]
    blocked_count: int = Field(..., ge=0)
    timestamp_utc: datetime


class SimulationResult(BaseModel):
    """Response payload describing a single simulation run."""

    summary: SimulationSummary
    services: List[ServiceMetrics]
    edges: List[GraphEdge]


class HistoricalRecord(BaseModel):
    """Stored history entry representing a past simulation result."""

    summary: SimulationSummary
    services: List[ServiceMetrics]


class HistoricalSimulationResult(SimulationResult):
    """Simulation result that also exposes past runs."""

    history: List[HistoricalRecord]


class ExportResponse(BaseModel):
    """Metadata returned after exporting the current run as CSV."""

    export_path: str
    record_count: int
    generated_at_utc: datetime


class CICDHookRequest(BaseModel):
    """Payload accepted by the CI/CD hook endpoint."""

    pipeline_id: str = Field(..., description="Identifier for the calling pipeline")
    service_name: str = Field(..., description="Service requesting deployment")
    requested_by: Optional[str] = Field(
        None, description="Optional username that triggered the pipeline"
    )


class CICDHookResponse(BaseModel):
    """Response object communicating the hook decision."""

    message: str
    risk_score: float = Field(..., ge=0, le=100)
    decision: DeploymentDecision


class HealthResponse(BaseModel):
    """Response contract for the /health endpoint."""

    status: Literal["ok"]
    timestamp_utc: datetime


class SummaryResponse(BaseModel):
    """Payload returned by the /summary endpoint."""

    average_risk: float = Field(..., ge=0, le=100)
    highest_risk_service: str
    highest_risk_score: float = Field(..., ge=0, le=100)
    blocked_count: int = Field(..., ge=0)


