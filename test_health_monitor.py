# test_health_monitor.py
import pytest
import json
import tempfile
import os
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime
from health_monitor import (
    HealthStatus, HealthCheck, SystemMonitor, ServiceMonitor,
    AlertManager, HealthMonitorOrchestrator
)


class TestSystemMonitor:
    """Test system monitoring functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.monitor = SystemMonitor(cpu_threshold=80.0, memory_threshold=85.0, disk_threshold=90.0)

    @patch('health_monitor.psutil.cpu_percent')
    def test_cpu_check_healthy(self, mock_cpu_percent):
        """Test CPU check returns healthy status for normal usage."""
        mock_cpu_percent.return_value = 50.0

        result = self.monitor.check_cpu_usage()

        assert result.name == "cpu_usage"
        assert result.status == HealthStatus.HEALTHY
        assert "CPU usage normal: 50.0%" in result.message
        assert result.metrics["cpu_percent"] == 50.0

    @patch('health_monitor.psutil.cpu_percent')
    def test_cpu_check_warning(self, mock_cpu_percent):
        """Test CPU check returns warning status for high usage."""
        mock_cpu_percent.return_value = 85.0

        result = self.monitor.check_cpu_usage()

        assert result.status == HealthStatus.WARNING
        assert "High CPU usage: 85.0%" in result.message

    @patch('health_monitor.psutil.cpu_percent')
    def test_cpu_check_critical(self, mock_cpu_percent):
        """Test CPU check returns critical status for very high usage."""
        mock_cpu_percent.return_value = 98.0

        result = self.monitor.check_cpu_usage()

        assert result.status == HealthStatus.CRITICAL
        assert "High CPU usage: 98.0%" in result.message

    @patch('health_monitor.psutil.virtual_memory')
    def test_memory_check_healthy(self, mock_memory):
        """Test memory check returns healthy status for normal usage."""
        mock_memory.return_value = Mock(percent=60.0, available=8 * 1024 ** 3)

        result = self.monitor.check_memory_usage()

        assert result.status == HealthStatus.HEALTHY
        assert "Memory usage normal: 60.0%" in result.message
        assert result.metrics["memory_percent"] == 60.0
        assert result.metrics["available_gb"] == 8.0

    @patch('health_monitor.psutil.disk_usage')
    def test_disk_check_healthy(self, mock_disk_usage):
        """Test disk check returns healthy status for normal usage."""
        mock_disk_usage.return_value = Mock(
            total=100 * 1024 ** 3,
            used=60 * 1024 ** 3,
            free=40 * 1024 ** 3
        )

        result = self.monitor.check_disk_usage("/")

        assert result.status == HealthStatus.HEALTHY
        assert "Disk usage normal: 60.0%" in result.message
        assert abs(result.metrics["disk_percent"] - 60.0) < 0.1
        assert result.metrics["free_gb"] == 40.0

    @patch('health_monitor.psutil.disk_usage')
    def test_disk_check_exception(self, mock_disk_usage):
        """Test disk check handles exceptions properly."""
        mock_disk_usage.side_effect = Exception("Permission denied")

        result = self.monitor.check_disk_usage("/")

        assert result.status == HealthStatus.CRITICAL
        assert "Failed to check disk usage" in result.message


class TestServiceMonitor:
    """Test service monitoring functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.monitor = ServiceMonitor(timeout=5)

    @patch('health_monitor.requests.get')
    def test_http_check_healthy(self, mock_get):
        """Test HTTP endpoint check returns healthy for good response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.elapsed.total_seconds.return_value = 0.5
        mock_get.return_value = mock_response

        result = self.monitor.check_http_endpoint("https://example.com")

        assert result.status == HealthStatus.HEALTHY
        assert "Endpoint healthy" in result.message
        assert result.metrics["response_time"] == 0.5
        assert result.metrics["status_code"] == 200

    @patch('health_monitor.requests.get')
    def test_http_check_slow_response(self, mock_get):
        """Test HTTP endpoint check returns warning for slow response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.elapsed.total_seconds.return_value = 6.0
        mock_get.return_value = mock_response

        result = self.monitor.check_http_endpoint("https://example.com")

        assert result.status == HealthStatus.WARNING
        assert "Endpoint slow" in result.message

    @patch('health_monitor.requests.get')
    def test_http_check_wrong_status(self, mock_get):
        """Test HTTP endpoint check returns critical for wrong status code."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.elapsed.total_seconds.return_value = 0.5
        mock_get.return_value = mock_response

        result = self.monitor.check_http_endpoint("https://example.com")

        assert result.status == HealthStatus.CRITICAL
        assert "Unexpected status code: 500" in result.message

    @patch('health_monitor.requests.get')
    def test_http_check_timeout(self, mock_get):
        """Test HTTP endpoint check handles timeout."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()

        result = self.monitor.check_http_endpoint("https://example.com")

        assert result.status == HealthStatus.CRITICAL
        assert "Request timeout" in result.message

    @patch('health_monitor.requests.get')
    def test_http_check_connection_error(self, mock_get):
        """Test HTTP endpoint check handles connection error."""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError()

        result = self.monitor.check_http_endpoint("https://example.com")

        assert result.status == HealthStatus.CRITICAL
        assert "Connection failed" in result.message


class TestAlertManager:
    """Test alert management functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log')
        self.temp_file.close()
        self.alert_manager = AlertManager(log_file=self.temp_file.name)

    def teardown_method(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)

    def test_process_healthy_alert(self, caplog):
        """Test processing healthy status doesn't trigger alerts."""
        health_check = HealthCheck(
            name="test_service",
            status=HealthStatus.HEALTHY,
            message="All good",
            timestamp=datetime.now()
        )

        self.alert_manager.process_alert(health_check)

        # Check that info level log was created
        assert "HEALTHY: test_service - All good" in caplog.text

    def test_process_warning_alert(self, caplog, capsys):
        """Test processing warning status triggers warning alert."""
        health_check = HealthCheck(
            name="test_service",
            status=HealthStatus.WARNING,
            message="Something's not right",
            timestamp=datetime.now(),
            metrics={"response_time": 6.0}
        )

        self.alert_manager.process_alert(health_check)

        captured = capsys.readouterr()
        assert "⚠️ WARNING:" in captured.out
        assert "test_service" in captured.out

    def test_process_critical_alert(self, capsys):
        """Test processing critical status triggers critical alert."""
        health_check = HealthCheck(
            name="test_service",
            status=HealthStatus.CRITICAL,
            message="System down!",
            timestamp=datetime.now(),
            metrics={"cpu_percent": 99.0}
        )

        self.alert_manager.process_alert(health_check)

        captured = capsys.readouterr()
        assert "🚨 CRITICAL ALERT:" in captured.out
        assert "test_service" in captured.out


class TestHealthMonitorOrchestrator:
    """Test orchestrator functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.orchestrator = HealthMonitorOrchestrator()

    def test_default_config(self):
        """Test default configuration is properly set."""
        config = self.orchestrator.config

        assert config["system_checks"]["cpu_enabled"] is True
        assert config["system_checks"]["memory_enabled"] is True
        assert config["system_checks"]["disk_enabled"] is True
        assert len(config["service_checks"]["endpoints"]) >= 1

    def test_load_config_from_file(self):
        """Test loading configuration from file."""
        config_data = {
            "system_checks": {
                "cpu_enabled": False,
                "memory_enabled": True,
                "disk_enabled": False
            },
            "service_checks": {
                "endpoints": ["https://test.com"]
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name

        try:
            orchestrator = HealthMonitorOrchestrator(config_file=config_file)
            assert orchestrator.config["system_checks"]["cpu_enabled"] is False
            assert orchestrator.config["service_checks"]["endpoints"] == ["https://test.com"]
        finally:
            os.unlink(config_file)

    def test_load_invalid_config_file(self):
        """Test handling of invalid config file."""
        orchestrator = HealthMonitorOrchestrator(config_file="non_existent_file.json")

        # Should fall back to default config
        assert orchestrator.config["system_checks"]["cpu_enabled"] is True

    @patch('health_monitor.SystemMonitor.check_cpu_usage')
    @patch('health_monitor.SystemMonitor.check_memory_usage')
    @patch('health_monitor.SystemMonitor.check_disk_usage')
    @patch('health_monitor.ServiceMonitor.check_http_endpoint')
    def test_run_all_checks(self, mock_http_check, mock_disk_check,
                            mock_memory_check, mock_cpu_check):
        """Test running all configured health checks."""
        # Mock return values
        mock_cpu_check.return_value = HealthCheck(
            "cpu", HealthStatus.HEALTHY, "OK", datetime.now()
        )
        mock_memory_check.return_value = HealthCheck(
            "memory", HealthStatus.HEALTHY, "OK", datetime.now()
        )
        mock_disk_check.return_value = HealthCheck(
            "disk", HealthStatus.HEALTHY, "OK", datetime.now()
        )
        mock_http_check.return_value = HealthCheck(
            "http", HealthStatus.HEALTHY, "OK", datetime.now()
        )

        results = self.orchestrator.run_all_checks()

        # Should have system checks + service checks
        expected_count = 3 + len(self.orchestrator.config["service_checks"]["endpoints"])
        assert len(results) == expected_count

        # Verify all mocks were called
        mock_cpu_check.assert_called_once()
        mock_memory_check.assert_called_once()
        mock_disk_check.assert_called_once()

    def test_generate_report(self):
        """Test report generation."""
        test_results = [
            HealthCheck("test1", HealthStatus.HEALTHY, "OK", datetime.now()),
            HealthCheck("test2", HealthStatus.WARNING, "Warning", datetime.now()),
            HealthCheck("test3", HealthStatus.CRITICAL, "Critical", datetime.now()),
        ]

        report = self.orchestrator.generate_report(test_results)

        assert report["total_checks"] == 3
        assert report["healthy"] == 1
        assert report["warnings"] == 1
        assert report["critical"] == 1
        assert report["overall_status"] == "critical"
        assert len(report["checks"]) == 3


@pytest.fixture
def sample_health_check():
    """Fixture providing a sample health check."""
    return HealthCheck(
        name="sample_check",
        status=HealthStatus.HEALTHY,
        message="Sample message",
        timestamp=datetime.now(),
        metrics={"sample_metric": 42.0}
    )


class TestIntegration:
    """Integration tests."""

    @patch('health_monitor.psutil.cpu_percent')
    @patch('health_monitor.psutil.virtual_memory')
    @patch('health_monitor.psutil.disk_usage')
    @patch('health_monitor.requests.get')
    def test_full_monitoring_cycle(self, mock_get, mock_disk_usage,
                                   mock_memory, mock_cpu_percent):
        """Test complete monitoring cycle with mocked dependencies."""
        # Mock system resources
        mock_cpu_percent.return_value = 45.0
        mock_memory.return_value = Mock(percent=55.0, available=6 * 1024 ** 3)
        mock_disk_usage.return_value = Mock(
            total=100 * 1024 ** 3, used=40 * 1024 ** 3, free=60 * 1024 ** 3
        )

        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.elapsed.total_seconds.return_value = 0.3
        mock_get.return_value = mock_response

        orchestrator = HealthMonitorOrchestrator()
        results = orchestrator.run_all_checks()
        report = orchestrator.generate_report(results)

        # Verify all checks passed
        assert report["critical"] == 0
        assert report["warnings"] == 0
        assert report["healthy"] > 0
        assert report["overall_status"] == "healthy"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])