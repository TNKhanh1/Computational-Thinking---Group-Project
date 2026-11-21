# SmartSchedule Production Container (Web Workbench Port 8000 + Optional member_eval Port 8010)
# Build from repository root:
#   docker build -f group03-smartschedule-baseline/docker/Dockerfile -t smartschedule:latest .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    SMARTSCHEDULE_DB_PATH=/app/group03-smartschedule-baseline/data/local_state.db

WORKDIR /app

# Install core dependencies first for layer caching
COPY group03-smartschedule-baseline/requirements.txt /app/group03-smartschedule-baseline/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/group03-smartschedule-baseline/requirements.txt

# Copy baseline application and read-only Testing_System (needed for live v2.1 health API)
COPY group03-smartschedule-baseline /app/group03-smartschedule-baseline
COPY v1.0-alpha-plan/Testing_System /app/Testing_System

WORKDIR /app/group03-smartschedule-baseline

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "web.api:app", "--host", "0.0.0.0", "--port", "8000"]
