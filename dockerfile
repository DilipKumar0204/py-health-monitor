FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m monitor
USER monitor

# Run health checks every 5 minutes
CMD ["python", "-c", "import time; from health_monitor import HealthMonitorOrchestrator; monitor = HealthMonitorOrchestrator(); [monitor.run_all_checks() or time.sleep(300) for _ in iter(int, 1)]"]
