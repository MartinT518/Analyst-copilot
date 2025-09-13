"""Service for monitoring system performance and generating dashboards."""

import asyncio
from typing import Any, Dict, List, Optional

import structlog
from grafana_client import GrafanaApi
from prometheus_client import Counter, Gauge, Histogram

from ..config import get_settings

logger = structlog.get_logger(__name__)


class MonitoringService:
    """Service for system monitoring and dashboard management."""

    def __init__(self):
        """Initialize the monitoring service."""
        self.settings = get_settings()
        self.logger = logger.bind(service="monitoring_service")

        # Initialize Grafana client
        self.grafana_client = None
        if self.settings.grafana_url and self.settings.grafana_api_key:
            self.grafana_client = GrafanaApi.from_url(
                url=self.settings.grafana_url, credential=self.settings.grafana_api_key
            )

        # Prometheus metrics
        self.edit_rate = Gauge(
            "acp_edit_rate", "Rate of edits to agent-generated content", ["agent_name"]
        )
        self.task_acceptance_rate = Gauge(
            "acp_task_acceptance_rate", "Rate of acceptance for generated tasks", ["agent_name"]
        )
        self.hallucination_incidents = Counter(
            "acp_hallucination_incidents",
            "Number of hallucination incidents reported",
            ["agent_name"],
        )
        self.workflow_duration = Histogram(
            "acp_workflow_duration_seconds",
            "Duration of analysis workflows",
            ["agent_name", "status"],
        )

    async def update_monitoring_metrics(self, metrics_data: Dict[str, Any]) -> Dict[str, str]:
        """Update monitoring metrics based on feedback and system events.

        Args:
            metrics_data: Metrics data to update

        Returns:
            Status of metrics update
        """
        self.logger.info("Updating monitoring metrics", metrics_data=metrics_data)

        try:
            agent_name = metrics_data.get("agent_name", "unknown")

            if "edit_rate" in metrics_data:
                self.edit_rate.labels(agent_name=agent_name).set(metrics_data["edit_rate"])

            if "task_acceptance_rate" in metrics_data:
                self.task_acceptance_rate.labels(agent_name=agent_name).set(
                    metrics_data["task_acceptance_rate"]
                )

            if "hallucination_incident" in metrics_data:
                self.hallucination_incidents.labels(agent_name=agent_name).inc()

            if "workflow_duration" in metrics_data:
                self.workflow_duration.labels(
                    agent_name=agent_name, status=metrics_data.get("status", "completed")
                ).observe(metrics_data["workflow_duration"])

            self.logger.info("Monitoring metrics updated successfully")
            return {"status": "success"}

        except Exception as e:
            self.logger.error("Failed to update metrics", error=str(e))
            raise

    async def create_grafana_dashboard(self, dashboard_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Grafana dashboard for monitoring.

        Args:
            dashboard_config: Dashboard configuration

        Returns:
            Created dashboard information
        """
        if not self.grafana_client:
            raise ValueError("Grafana client not configured")

        self.logger.info("Creating Grafana dashboard", title=dashboard_config.get("title"))

        try:
            # Create dashboard
            dashboard = self.grafana_client.dashboard.update_dashboard(dashboard=dashboard_config)

            self.logger.info("Grafana dashboard created successfully", uid=dashboard["uid"])
            return dashboard

        except Exception as e:
            self.logger.error("Failed to create Grafana dashboard", error=str(e))
            raise

    async def get_default_dashboard_config(self) -> Dict[str, Any]:
        """Get the default dashboard configuration.

        Returns:
            Default dashboard configuration
        """
        return {
            "dashboard": {
                "id": None,
                "uid": None,
                "title": "Analyst Copilot - Continuous Improvement",
                "tags": ["analyst-copilot", "ai-monitoring"],
                "timezone": "browser",
                "schemaVersion": 16,
                "version": 0,
                "refresh": "10s",
                "panels": [
                    {
                        "title": "Edit Rate by Agent",
                        "type": "gauge",
                        "targets": [{"expr": "acp_edit_rate", "legendFormat": "{{agent_name}}"}],
                        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
                    },
                    {
                        "title": "Task Acceptance Rate by Agent",
                        "type": "gauge",
                        "targets": [
                            {"expr": "acp_task_acceptance_rate", "legendFormat": "{{agent_name}}"}
                        ],
                        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
                    },
                    {
                        "title": "Hallucination Incidents",
                        "type": "stat",
                        "targets": [
                            {
                                "expr": "sum(rate(acp_hallucination_incidents[5m])) by (agent_name)",
                                "legendFormat": "{{agent_name}}",
                            }
                        ],
                        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
                    },
                    {
                        "title": "Workflow Duration (p95)",
                        "type": "histogram",
                        "targets": [
                            {
                                "expr": "histogram_quantile(0.95, sum(rate(acp_workflow_duration_seconds_bucket[5m])) by (le, agent_name))",
                                "legendFormat": "{{agent_name}}",
                            }
                        ],
                        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
                    },
                ],
            },
            "folderId": 0,
            "overwrite": False,
        }
