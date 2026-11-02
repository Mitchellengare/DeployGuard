# DeployGuard

AI-assisted cloud monitoring: detects application failures, clusters error logs into patterns, and
correlates incidents with deployment history to surface the most likely root-cause deploy.

**Stack:** Python, FastAPI, React, Docker, GitHub Actions, AWS CloudWatch, OpenTelemetry

## How it works
1. CI/CD posts each deploy to `POST /api/deployments` (see `.github/workflows/deploy.yml`).
2. Apps (or CloudWatch via `POST /api/logs/sync/{service}`) send logs to `POST /api/logs`.
3. When a service exceeds `DG_ERROR_THRESHOLD` ERRORs in `DG_ERROR_WINDOW_MINUTES`, an incident opens.
4. Errors are normalized/clustered (`<n>`, `<uuid>` placeholders) and each recent deploy is scored on
   recency + overlap between changed files and error text. Optional Claude summary if `DG_ANTHROPIC_API_KEY` is set.
5. Incident count is published as a CloudWatch metric; API traces go out via OpenTelemetry (OTLP).

## Run
```
docker compose up --build        # UI :8080, API :8000/docs
# or
cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/uvicorn app.main:app --reload
cd frontend && npm install && npm run dev
```
Tests: `cd backend && pytest`. Config via `DG_*` env vars (`backend/app/config.py`).

## Try it
```
curl -XPOST localhost:8000/api/deployments -H 'content-type: application/json' \
  -d '{"service":"checkout","version":"v2","commit_sha":"abc1234","changed_files":["src/payment_gateway.py"]}'
python3 -c "import json;print(json.dumps([{'service':'checkout','level':'ERROR','message':f'payment gateway timeout order {i}'} for i in range(12)]))" \
 | curl -XPOST localhost:8000/api/logs -H 'content-type: application/json' -d @-
```
