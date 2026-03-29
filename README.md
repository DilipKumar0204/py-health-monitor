# py-health-monitor
Infrastructure Health Monitor
A comprehensive Python-based infrastructure monitoring system with automated alerting capabilities, built using pytest for robust testing.
This project demonstrates real-world DevOps skills by implementing a production-ready monitoring system that:

• Monitors system resources (CPU, memory, disk usage)
• Monitors external services via HTTP health checks
• Triggers intelligent alerts based on configurable thresholds
• Provides comprehensive logging and reporting
• Includes full test coverage with pytest
• Supports containerized deployment with Docker
• Offers CI/CD pipeline integration

Libraries used:
FastAPI	- API framework	fastapi==0.110.0
psutil	- System metrics (CPU, memory, disk)	psutil==5.9.8
requests	- Sync external API calls	requests==2.31.0
httpx -	Async API calls	httpx==0.27.0
azure-identity - Azure authentication	azure-identity==1.16.0
azure-monitor-query -	Fetch Azure Monitor metrics & logs	azure-monitor-query==1.3.0
datetime - Timestamp handling (built-in)	✅ Built-in (no install)
uvicorn	- ASGI server to run FastAPI	uvicorn==0.29.0
