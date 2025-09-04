# health_monitor.py
import requests
import psutil
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class HealthStatus(Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class HealthCheck:
    name: str
    status: HealthStatus
    message: str
    timestamp: datetime
    metrics: Dict[str, float] = None


class SystemMonitor:
    """Monitor system resources like CPU, memory, and disk usage."""

    def __init__(self, cpu_threshold: float = 80.0, memory_threshold: float = 85.0, disk_threshold: float = 90.0):
        self.cpu_threshold = cpu_threshold
        self.memory_threshold = memory_threshold
        self.disk_threshold = disk_threshold

    def check_cpu_usage(self) -> HealthCheck:
        """Check CPU usage percentage."""
        cpu_percent = psutil.cpu_percent(interval=1)

        if cpu_percent >= self.cpu_threshold:
            status = HealthStatus.CRITICAL if cpu_percent >= 95 else HealthStatus.WARNING
            message = f"High CPU usage: {cpu_percent}%"
        else:
            status = HealthStatus.HEALTHY
            message = f"CPU usage normal: {cpu_percent}%"

        return HealthCheck(
            name="cpu_usage",
            status=status,
            message=message,
            timestamp=datetime.now(),
            metrics={"cpu_percent": cpu_percent}
        )

    def check_memory_usage(self) -> HealthCheck:
        """Check memory usage percentage."""
        memory = psutil.virtual_memory()
        memory_percent = memory.percent

        if memory_percent >= self.memory_threshold:
            status = HealthStatus.CRITICAL if memory_percent >= 95 else HealthStatus.WARNING
            message = f"High memory usage: {memory_percent}%"
        else:
            status = HealthStatus.HEALTHY
            message = f"Memory usage normal: {memory_percent}%"

        return HealthCheck(
            name="memory_usage",
            status=status,
            message=message,
            timestamp=datetime.now(),
            metrics={"memory_percent": memory_percent, "available_gb": memory.available / (1024 ** 3)}
        )

    def check_disk_usage(self, path: str = "/") -> HealthCheck:
        """Check disk usage percentage."""
        try:
            disk = psutil.disk_usage(path)
            disk_percent = (disk.used / disk.total) * 100

            if disk_percent >= self.disk_threshold:
                status = HealthStatus.CRITICAL if disk_percent >= 95 else HealthStatus.WARNING
                message = f"High disk usage: {disk_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk usage normal: {disk_percent:.1f}%"

            return HealthCheck(
                name="disk_usage",
                status=status,
                message=message,
                timestamp=datetime.now(),
                metrics={"disk_percent": disk_percent, "free_gb": disk.free / (1024 ** 3)}
            )
        except Exception as e:
            return HealthCheck(
                name="disk_usage",
                status=HealthStatus.CRITICAL,
                message=f"Failed to check disk usage: {str(e)}",
                timestamp=datetime.now()
            )


class ServiceMonitor:
    """Monitor external services and endpoints."""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    def check_http_endpoint(self, url: str, expected_status: int = 200) -> HealthCheck:
        """Check if an HTTP endpoint is responding correctly."""
        try:
            response = requests.get(url, timeout=self.timeout)
            response_time = response.elapsed.total_seconds()

            if response.status_code == expected_status:
                if response_time > 5.0:
                    status = HealthStatus.WARNING
                    message = f"Endpoint slow: {response_time:.2f}s response time"
                else:
                    status = HealthStatus.HEALTHY
                    message = f"Endpoint healthy: {response_time:.2f}s response time"
            else:
                status = HealthStatus.CRITICAL
                message = f"Unexpected status code: {response.status_code}"

            return HealthCheck(
                name=f"http_check_{url}",
                status=status,
                message=message,
                timestamp=datetime.now(),
                metrics={"response_time": response_time, "status_code": response.status_code}
            )

        except requests.exceptions.Timeout:
            return HealthCheck(
                name=f"http_check_{url}",
                status=HealthStatus.CRITICAL,
                message="Request timeout",
                timestamp=datetime.now()
            )
        except requests.exceptions.ConnectionError:
            return HealthCheck(
                name=f"http_check_{url}",
                status=HealthStatus.CRITICAL,
                message="Connection failed",
                timestamp=datetime.now()
            )
        except Exception as e:
            return HealthCheck(
                name=f"http_check_{url}",
                status=HealthStatus.CRITICAL,
                message=f"Unexpected error: {str(e)}",
                timestamp=datetime.now()
            )


class AlertManager:
    """Handle alerting based on health check results."""

    def __init__(self, log_file: str = "health_alerts.log"):
        self.log_file = log_file
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def process_alert(self, health_check: HealthCheck) -> None:
        """Process a health check result and trigger alerts if needed."""
        if health_check.status == HealthStatus.CRITICAL:
            self.logger.critical(f"CRITICAL: {health_check.name} - {health_check.message}")
            self._send_critical_alert(health_check)
        elif health_check.status == HealthStatus.WARNING:
            self.logger.warning(f"WARNING: {health_check.name} - {health_check.message}")
            self._send_warning_alert(health_check)
        else:
            self.logger.info(f"HEALTHY: {health_check.name} - {health_check.message}")

    def _send_critical_alert(self, health_check: HealthCheck) -> None:
        """Send critical alert (in real scenario, this would send to Slack/email/PagerDuty)."""
        alert_data = {
            "level": "critical",
            "service": health_check.name,
            "message": health_check.message,
            "timestamp": health_check.timestamp.isoformat(),
            "metrics": health_check.metrics
        }
        # In a real scenario, you'd send this to your alerting system
        print(f"🚨 CRITICAL ALERT: {json.dumps(alert_data, indent=2)}")

    def _send_warning_alert(self, health_check: HealthCheck) -> None:
        """Send warning alert."""
        alert_data = {
            "level": "warning",
            "service": health_check.name,
            "message": health_check.message,
            "timestamp": health_check.timestamp.isoformat(),
            "metrics": health_check.metrics
        }
        print(f"⚠️ WARNING: {json.dumps(alert_data, indent=2)}")


class HealthMonitorOrchestrator:
    """Main orchestrator that coordinates all monitoring activities."""

    def __init__(self, config_file: Optional[str] = None):
        self.system_monitor = SystemMonitor()
        self.service_monitor = ServiceMonitor()
        self.alert_manager = AlertManager()
        self.config = self._load_config(config_file) if config_file else self._default_config()

    def _default_config(self) -> Dict:
        """Default monitoring configuration."""
        return {
            "system_checks": {
                "cpu_enabled": True,
                "memory_enabled": True,
                "disk_enabled": True
            },
            "service_checks": {
                "endpoints": [
                    "https://httpbin.org/status/200",
                    "https://api.github.com/status"
                ]
            }
        }

    def _load_config(self, config_file: str) -> Dict:
        """Load configuration from file."""
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load config file {config_file}: {e}")
            return self._default_config()

    def run_all_checks(self) -> List[HealthCheck]:
        """Run all configured health checks."""
        results = []

        # System checks
        if self.config["system_checks"]["cpu_enabled"]:
            results.append(self.system_monitor.check_cpu_usage())

        if self.config["system_checks"]["memory_enabled"]:
            results.append(self.system_monitor.check_memory_usage())

        if self.config["system_checks"]["disk_enabled"]:
            results.append(self.system_monitor.check_disk_usage())

        # Service checks
        for endpoint in self.config["service_checks"]["endpoints"]:
            results.append(self.service_monitor.check_http_endpoint(endpoint))

        # Process alerts
        for result in results:
            self.alert_manager.process_alert(result)

        return results

    def generate_report(self, results: List[HealthCheck]) -> Dict:
        """Generate a summary report of all health checks."""
        healthy_count = sum(1 for r in results if r.status == HealthStatus.HEALTHY)
        warning_count = sum(1 for r in results if r.status == HealthStatus.WARNING)
        critical_count = sum(1 for r in results if r.status == HealthStatus.CRITICAL)

        return {
            "timestamp": datetime.now().isoformat(),
            "total_checks": len(results),
            "healthy": healthy_count,
            "warnings": warning_count,
            "critical": critical_count,
            "overall_status": "critical" if critical_count > 0 else "warning" if warning_count > 0 else "healthy",
            "checks": [
                {
                    "name": r.name,
                    "status": r.status.value,
                    "message": r.message,
                    "metrics": r.metrics
                } for r in results
            ]
        }


if __name__ == "__main__":
    # Example usage
    monitor = HealthMonitorOrchestrator()
    results = monitor.run_all_checks()
    report = monitor.generate_report(results)

    print("\n" + "=" * 50)
    print("INFRASTRUCTURE HEALTH REPORT")
    print("=" * 50)
    print(json.dumps(report, indent=2))