"""OpenTelemetry setup: traces exported over OTLP/HTTP (e.g. to an ADOT collector -> CloudWatch/X-Ray)."""
from fastapi import FastAPI

from .config import settings


def setup_telemetry(app: FastAPI) -> None:
    if not settings.otel_enabled:
        return
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    from .db import engine

    provider = TracerProvider(resource=Resource.create({"service.name": "deployguard-api"}))
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{settings.otel_endpoint}/v1/traces"))
    )
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument(engine=engine)
