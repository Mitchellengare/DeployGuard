from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeploymentIn(BaseModel):
    service: str
    version: str
    commit_sha: str = ""
    author: str = ""
    changed_files: list[str] = Field(default_factory=list)
    deployed_at: datetime | None = None


class DeploymentOut(DeploymentIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    deployed_at: datetime


class LogIn(BaseModel):
    service: str
    level: str = "INFO"
    message: str
    timestamp: datetime | None = None


class SuspectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    score: float
    reasons: list[str]
    deployment: DeploymentOut


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    service: str
    status: str
    error_count: int
    detected_at: datetime
    summary: str
    top_patterns: list[dict]
    suspects: list[SuspectOut]
