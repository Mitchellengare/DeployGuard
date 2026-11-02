from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import analysis, cloudwatch, schemas
from ..db import Deployment, Incident, LogEntry, get_db, utcnow

router = APIRouter(prefix="/api")


@router.post("/deployments", response_model=schemas.DeploymentOut, status_code=201)
def record_deployment(body: schemas.DeploymentIn, db: Session = Depends(get_db)):
    data = body.model_dump()
    data["deployed_at"] = data["deployed_at"] or utcnow()
    dep = Deployment(**data)
    db.add(dep)
    db.commit()
    return dep


@router.get("/deployments", response_model=list[schemas.DeploymentOut])
def list_deployments(service: str | None = None, db: Session = Depends(get_db)):
    q = select(Deployment).order_by(Deployment.deployed_at.desc()).limit(100)
    if service:
        q = q.where(Deployment.service == service)
    return db.scalars(q).all()


@router.post("/logs", status_code=202)
def ingest_logs(body: list[schemas.LogIn], db: Session = Depends(get_db)):
    db.add_all(
        LogEntry(service=e.service, level=e.level.upper(), message=e.message, timestamp=e.timestamp or utcnow())
        for e in body
    )
    db.commit()
    created = analysis.detect_incidents(db)
    return {"ingested": len(body), "incidents_opened": [i.id for i in created]}


@router.post("/logs/sync/{service}")
def sync_cloudwatch(service: str, db: Session = Depends(get_db)):
    """Pull recent logs for a service from CloudWatch and run detection."""
    events = cloudwatch.pull_logs(service)
    db.add_all(LogEntry(**e) for e in events)
    db.commit()
    return {"ingested": len(events), "incidents_opened": [i.id for i in analysis.detect_incidents(db)]}


@router.get("/logs", response_model=list[schemas.LogIn])
def recent_logs(service: str | None = None, level: str | None = None, limit: int = 100, db: Session = Depends(get_db)):
    q = select(LogEntry).order_by(LogEntry.timestamp.desc()).limit(min(limit, 500))
    if service:
        q = q.where(LogEntry.service == service)
    if level:
        q = q.where(LogEntry.level == level.upper())
    return db.scalars(q).all()


@router.get("/incidents", response_model=list[schemas.IncidentOut])
def list_incidents(db: Session = Depends(get_db)):
    return db.scalars(select(Incident).order_by(Incident.detected_at.desc()).limit(50)).all()


@router.get("/incidents/{incident_id}", response_model=schemas.IncidentOut)
def get_incident(incident_id: int, db: Session = Depends(get_db)):
    inc = db.get(Incident, incident_id)
    if not inc:
        raise HTTPException(404, "incident not found")
    return inc


@router.post("/incidents/{incident_id}/resolve", response_model=schemas.IncidentOut)
def resolve_incident(incident_id: int, db: Session = Depends(get_db)):
    inc = db.get(Incident, incident_id)
    if not inc:
        raise HTTPException(404, "incident not found")
    inc.status = "resolved"
    db.commit()
    return inc
