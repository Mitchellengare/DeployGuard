"""AWS CloudWatch integration: ship logs/metrics out, and pull logs in."""
import logging
import time
from datetime import datetime, timezone

from .config import settings

log = logging.getLogger("deployguard.cloudwatch")


def _client(name: str):
    import boto3

    return boto3.client(name, region_name=settings.aws_region)


def publish_incident_metric(service: str, error_count: int) -> None:
    if not settings.cloudwatch_enabled:
        return
    try:
        _client("cloudwatch").put_metric_data(
            Namespace=settings.cloudwatch_namespace,
            MetricData=[{
                "MetricName": "IncidentErrorCount",
                "Dimensions": [{"Name": "Service", "Value": service}],
                "Value": error_count,
                "Unit": "Count",
            }],
        )
    except Exception:  # monitoring must never break the app
        log.exception("failed to publish CloudWatch metric")


def pull_logs(service: str, since_minutes: int = 10) -> list[dict]:
    """Fetch recent events from the CloudWatch log group, filtered to a service."""
    if not settings.cloudwatch_enabled:
        return []
    start = int((time.time() - since_minutes * 60) * 1000)
    resp = _client("logs").filter_log_events(
        logGroupName=settings.cloudwatch_log_group, startTime=start, filterPattern=f'"{service}"'
    )
    out = []
    for e in resp.get("events", []):
        msg = e["message"]
        level = "ERROR" if "ERROR" in msg or "Exception" in msg else "INFO"
        out.append({
            "service": service, "level": level, "message": msg,
            "timestamp": datetime.fromtimestamp(e["timestamp"] / 1000, tz=timezone.utc).replace(tzinfo=None),
        })
    return out
