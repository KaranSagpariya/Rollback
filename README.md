# Rolling Update Risk Estimator

Pre-deployment risk assessment microservice that models a microservice landscape, analyses historical behaviour, and produces actionable deployment guidance before rolling updates.

## Features

- FastAPI microservice with interactive Swagger UI
- NetworkX-driven dependency graph simulation for ~10 microservices
- Weighted risk scoring aligned with rollback, change frequency, and latency metrics
- Rolling history with simulated learning improvements for blocked services
- Matplotlib visualisations (`/graph.png`, `/barchart.png`)
- CSV export of simulation runs, CI/CD webhook integration, and summary endpoints

## Requirements

- Python 3.11+
- pip
- (Optional) Docker and Docker Compose

Install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
```

## Running the Service

### Local development

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Docker

```bash
docker build -t risk-estimator .
docker run -p 8000:8000 risk-estimator
```

### Docker Compose (with live reloading)

```bash
docker-compose up --build
```

The API documentation is available at `http://localhost:8000/docs`.

## Endpoints Overview

- `POST /simulate` → run a risk simulation (Swagger example provided)
- `POST /simulate/historical` → run simulation and include history payload
- `GET /services` → retrieve the latest computed metrics
- `GET /summary` → aggregate metrics (average risk, highest risk, blocked count)
- `GET /graph.png` / `GET /barchart.png` → visual assets for dashboards
- `POST /export` → export latest run to `exports/` as timestamped CSV
- `POST /cicd-hook` → CI/CD deployment trigger mock (Swagger example provided)
- `GET /health` → service heartbeat

## Historical Improvements

Blocked services from the most recent history entry automatically receive a 15% rollback rate reduction to simulate operational learning in subsequent runs. The rolling history length can be adjusted via environment variables (see `.env.example`).

## Visualisations

Saved assets default to `graph.png` and `barchart.png` in the project root. Each request regenerates the visual based on the latest simulation.

## Data Export

CSV exports are written to `exports/` with ISO timestamped filenames. Example:

```
exports/risk_estimator_20251107T014500Z.csv
```

## Testing

Execute the unit test suite:

```bash
pytest
```

## Environment Configuration

Copy `.env.example` to `.env` and override settings as required:

```env
HISTORY_LIMIT=5
EXPORT_DIRECTORY=exports
```

All configuration values are documented in `app/config.py`.

"# Rollback" 
