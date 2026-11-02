"""Incident detection and root-cause correlation against deployment history."""
import re
from collections import Counter
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import cloudwatch
from .config import settings
from .db import Deployment, Incident, LogEntry, Suspect, utcnow

_NORMALIZE = [
    (re.compile(r"0x[0-9a-fA-F]+"), "<hex>"),
    (re.compile(r"[0-9a-f]{8}-[0-9a-f-]{27}"), "<uuid>"),
    (re.compile(r"\d+"), "<n>"),
]
_STOPWORDS = {"the", "a", "an", "of", "in", "to", "for", "and", "is", "on", "at", "py", "js", "ts"}


def normalize(msg: str) -> str:
    """Collapse variable parts so similar errors cluster into one pattern."""
    for rx, repl in _NORMALIZE:
        msg = rx.sub(repl, msg)
    return msg.strip()[:200]


def top_patterns(logs: list[LogEntry], n: int = 5) -> list[dict]:
    counts = Counter(normalize(entry.message) for entry in logs)
    return [{"pattern": p, "count": c} for p, c in counts.most_common(n)]


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-zA-Z_]{3,}", text.lower()) if t not in _STOPWORDS}


def score_deployment(dep: Deployment, incident_time, patterns: list[dict]) -> tuple[float, list[str]]:
    """Heuristic: recency + overlap between changed files and error text."""
    reasons: list[str] = []
    window = settings.correlation_window_minutes
    age_min = (incident_time - dep.deployed_at).total_seconds() / 60
    recency = max(0.0, 1 - age_min / window)
    score = recency * 0.6
    reasons.append(f"Deployed {age_min:.0f} min before incident")

    error_tokens = set().union(*(_tokens(p["pattern"]) for p in patterns)) if patterns else set()
    hits = sorted(
        f for f in dep.changed_files
        if _tokens(f.replace("/", " ").replace(".", " ")) & error_tokens
    )
    if hits:
        score += min(0.4, 0.2 * len(hits))
        reasons.append("Changed files match error text: " + ", ".join(hits[:3]))
    return round(score, 3), reasons


def summarize(service: str, error_count: int, patterns: list[dict], suspects: list[tuple]) -> str:
    base = f"{error_count} errors in {service}. "
    if patterns:
        base += f"Most common: \"{patterns[0]['pattern']}\" ({patterns[0]['count']}x). "
    if suspects:
        dep, score, _ = suspects[0]
        base += f"Likely cause: deploy {dep.version} ({dep.commit_sha[:7] or 'no sha'}, score {score})."
    else:
        base += "No recent deployments found; likely not deploy-related."
    if settings.anthropic_api_key:
        try:
            import anthropic

            resp = anthropic.Anthropic(api_key=settings.anthropic_api_key).messages.create(
                model=settings.llm_model, max_tokens=300,
                messages=[{"role": "user", "content":
                    "You are an SRE assistant. In 3 sentences, explain the likely root cause "
                    f"and a next step.\n\nFacts: {base}\nPatterns: {patterns}"}],
            )
            return resp.content[0].text
        except Exception:
            pass  # fall back to heuristic summary
    return base


def detect_incidents(db: Session) -> list[Incident]:
    """Open an incident for any service whose ERROR count in the window exceeds the threshold."""
    now = utcnow()
    since = now - timedelta(minutes=settings.error_window_minutes)
    rows = db.execute(
        select(LogEntry.service, func.count())
        .where(LogEntry.level == "ERROR", LogEntry.timestamp >= since)
        .group_by(LogEntry.service)
    ).all()
    created = []
    for service, count in rows:
        if count < settings.error_threshold:
            continue
        already = db.scalar(select(Incident).where(Incident.service == service, Incident.status == "open"))
        if already:
            continue
        created.append(analyze(db, service, count, since, now))
    return created


def analyze(db: Session, service: str, count: int, since, now) -> Incident:
    logs = db.scalars(
        select(LogEntry).where(LogEntry.service == service, LogEntry.level == "ERROR", LogEntry.timestamp >= since)
    ).all()
    patterns = top_patterns(list(logs))
    deps = db.scalars(
        select(Deployment).where(
            Deployment.service == service,
            Deployment.deployed_at <= now,
            Deployment.deployed_at >= now - timedelta(minutes=settings.correlation_window_minutes),
        )
    ).all()
    scored = sorted(((d, *score_deployment(d, now, patterns)) for d in deps), key=lambda t: -t[1])
    incident = Incident(
        service=service, error_count=count, detected_at=now, top_patterns=patterns,
        summary=summarize(service, count, patterns, scored),
    )
    incident.suspects = [Suspect(deployment=d, score=s, reasons=r) for d, s, r in scored]
    db.add(incident)
    db.commit()
    cloudwatch.publish_incident_metric(service, count)
    return incident
