# SmartSchedule Production Container (Web Workbench Port 8000 + Optional member_eval Port 8010)
# Build from repository root:
#   docker build -f tools/docker/Dockerfile -t smartschedule:latest .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    SMARTSCHEDULE_DB_PATH=/app/data/runtime/local_state.db

WORKDIR /app

COPY environments/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

COPY environments/pyproject.toml /app/pyproject.toml
COPY smartschedule /app/smartschedule
COPY data /app/data
COPY tools /app/tools
COPY v1.0-alpha-plan/Testing_System /app/v1.0-alpha-plan/Testing_System

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "smartschedule.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
