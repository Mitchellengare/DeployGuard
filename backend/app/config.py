from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DG_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./deployguard.db"
    # Incident detection
    error_window_minutes: int = 5
    error_threshold: int = 10          # ERROR logs per window per service
    correlation_window_minutes: int = 60  # deploys this far before an incident are suspects
    # AWS
    aws_region: str = "us-east-1"
    cloudwatch_enabled: bool = False
    cloudwatch_log_group: str = "/deployguard/app"
    cloudwatch_namespace: str = "DeployGuard"
    # OpenTelemetry
    otel_enabled: bool = False
    otel_endpoint: str = "http://localhost:4318"
    # Optional LLM summaries
    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-5-5"


settings = Settings()
