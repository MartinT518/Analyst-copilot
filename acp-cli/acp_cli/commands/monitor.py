"""Monitoring commands for ACP CLI."""

import json
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import typer
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..config import config_manager
from ..utils import print_error, print_info, print_success, print_warning

app = typer.Typer(help="Monitor ACP services")
console = Console()


@app.command()
def logs(
    service: Optional[str] = typer.Option(
        None, "--service", "-s", help="Service to monitor (ingest, agents, postgres, redis)"
    ),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    tail: Optional[int] = typer.Option(100, "--tail", "-n", help="Number of lines to show"),
    level: Optional[str] = typer.Option(
        None, "--level", "-l", help="Filter by log level (DEBUG, INFO, WARNING, ERROR)"
    ),
    search: Optional[str] = typer.Option(None, "--search", help="Search for specific text in logs"),
):
    """View service logs."""

    try:
        project_root = Path.cwd()

        # Build docker-compose logs command
        cmd = ["docker-compose", "logs"]

        if follow:
            cmd.append("-f")

        if tail:
            cmd.extend(["--tail", str(tail)])

        if service:
            cmd.append(service)

        print_info(f"Viewing logs for {service or 'all services'}...")

        if search or level:
            # Use grep to filter logs
            if search and level:
                grep_pattern = f".*{level}.*{search}.*"
            elif search:
                grep_pattern = search
            elif level:
                grep_pattern = level

            # Pipe through grep
            process = subprocess.Popen(
                cmd, cwd=project_root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )

            grep_process = subprocess.Popen(
                ["grep", "-i", grep_pattern],
                stdin=process.stdout,
                stdout=subprocess.PIPE,
                text=True,
            )

            process.stdout.close()

            try:
                for line in iter(grep_process.stdout.readline, ""):
                    if line:
                        console.print(line.rstrip())
            except KeyboardInterrupt:
                print_info("Stopping log monitoring...")
            finally:
                grep_process.terminate()
                process.terminate()
        else:
            # Direct output
            result = subprocess.run(cmd, cwd=project_root)
            if result.returncode != 0:
                print_error("Failed to get logs")
                raise typer.Exit(1)

    except Exception as e:
        print_error(f"Failed to view logs: {e}")
        raise typer.Exit(1)


@app.command()
def metrics(
    service: Optional[str] = typer.Option(
        "ingest", "--service", "-s", help="Service to get metrics from"
    ),
    metric: Optional[str] = typer.Option(None, "--metric", "-m", help="Specific metric to query"),
    duration: Optional[str] = typer.Option(
        "5m", "--duration", "-d", help="Time range for metrics (e.g., 5m, 1h, 1d)"
    ),
):
    """View service metrics."""

    try:
        config = config_manager.load_config()

        # Get service URL
        if service == "ingest":
            base_url = config.ingest_service.url
        elif service == "agents":
            base_url = config.agents_service.url
        else:
            print_error(f"Unknown service: {service}")
            raise typer.Exit(1)

        # Get metrics endpoint
        metrics_url = f"{base_url}/metrics"

        print_info(f"Fetching metrics from {metrics_url}...")

        response = requests.get(metrics_url, timeout=10)
        response.raise_for_status()

        metrics_text = response.text

        if metric:
            # Filter for specific metric
            filtered_lines = []
            for line in metrics_text.split("\n"):
                if metric in line and not line.startswith("#"):
                    filtered_lines.append(line)

            if filtered_lines:
                console.print(f"[bold]Metric: {metric}[/bold]")
                for line in filtered_lines:
                    console.print(line)
            else:
                print_warning(f"Metric '{metric}' not found")
        else:
            # Show all metrics
            console.print(f"[bold]All metrics for {service} service:[/bold]")
            console.print(metrics_text)

    except requests.RequestException as e:
        print_error(f"Failed to fetch metrics: {e}")
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Failed to get metrics: {e}")
        raise typer.Exit(1)


@app.command()
def dashboard(
    refresh: int = typer.Option(5, "--refresh", "-r", help="Refresh interval in seconds"),
    duration: int = typer.Option(
        300, "--duration", "-d", help="How long to run dashboard in seconds"
    ),
):
    """Show real-time monitoring dashboard."""

    try:
        config = config_manager.load_config()

        def get_service_status(service_name: str, url: str) -> Dict[str, Any]:
            """Get service status and basic metrics."""
            try:
                # Health check
                health_response = requests.get(f"{url}/health", timeout=5)
                health_status = "healthy" if health_response.status_code == 200 else "unhealthy"

                # Basic metrics
                try:
                    metrics_response = requests.get(f"{url}/metrics", timeout=5)
                    metrics_text = metrics_response.text

                    # Parse some basic metrics
                    request_count = 0
                    error_count = 0

                    for line in metrics_text.split("\n"):
                        if "acp_requests_total" in line and not line.startswith("#"):
                            try:
                                value = float(line.split()[-1])
                                request_count += value
                            except:
                                pass
                        elif "acp_errors_total" in line and not line.startswith("#"):
                            try:
                                value = float(line.split()[-1])
                                error_count += value
                            except:
                                pass

                    return {
                        "status": health_status,
                        "requests": int(request_count),
                        "errors": int(error_count),
                        "error_rate": (error_count / max(request_count, 1)) * 100,
                    }
                except:
                    return {
                        "status": health_status,
                        "requests": "N/A",
                        "errors": "N/A",
                        "error_rate": "N/A",
                    }

            except:
                return {
                    "status": "unreachable",
                    "requests": "N/A",
                    "errors": "N/A",
                    "error_rate": "N/A",
                }

        def create_dashboard() -> Layout:
            """Create the dashboard layout."""
            layout = Layout()

            # Get service statuses
            ingest_status = get_service_status("ingest", config.ingest_service.url)
            agents_status = get_service_status("agents", config.agents_service.url)

            # Create services table
            services_table = Table(title="Service Status")
            services_table.add_column("Service", style="cyan")
            services_table.add_column("Status", style="green")
            services_table.add_column("Requests", style="blue")
            services_table.add_column("Errors", style="red")
            services_table.add_column("Error Rate", style="yellow")

            # Add service rows
            for service_name, status in [("Ingest", ingest_status), ("Agents", agents_status)]:
                status_color = "green" if status["status"] == "healthy" else "red"
                services_table.add_row(
                    service_name,
                    f"[{status_color}]{status['status']}[/{status_color}]",
                    str(status["requests"]),
                    str(status["errors"]),
                    (
                        f"{status['error_rate']:.1f}%"
                        if isinstance(status["error_rate"], (int, float))
                        else str(status["error_rate"])
                    ),
                )

            # Create system info
            try:
                # Get docker-compose status
                result = subprocess.run(
                    ["docker-compose", "ps", "--format", "json"],
                    capture_output=True,
                    text=True,
                    cwd=Path.cwd(),
                )

                if result.returncode == 0:
                    containers = []
                    for line in result.stdout.strip().split("\n"):
                        if line:
                            try:
                                container = json.loads(line)
                                containers.append(container)
                            except:
                                pass

                    containers_table = Table(title="Containers")
                    containers_table.add_column("Name", style="cyan")
                    containers_table.add_column("Status", style="green")
                    containers_table.add_column("Ports", style="blue")

                    for container in containers:
                        status = container.get("State", "unknown")
                        status_color = "green" if status == "running" else "red"

                        containers_table.add_row(
                            container.get("Name", "unknown"),
                            f"[{status_color}]{status}[/{status_color}]",
                            (
                                container.get("Publishers", [{}])[0].get("PublishedPort", "N/A")
                                if container.get("Publishers")
                                else "N/A"
                            ),
                        )
                else:
                    containers_table = Panel("Failed to get container status", title="Containers")
            except:
                containers_table = Panel("Docker not available", title="Containers")

            # Split layout
            layout.split_column(
                Layout(services_table, name="services"), Layout(containers_table, name="containers")
            )

            return layout

        # Run dashboard
        start_time = time.time()

        with Live(create_dashboard(), refresh_per_second=1 / refresh, screen=True) as live:
            while time.time() - start_time < duration:
                time.sleep(refresh)
                live.update(create_dashboard())

        print_success("Dashboard monitoring completed")

    except KeyboardInterrupt:
        print_info("Dashboard monitoring stopped")
    except Exception as e:
        print_error(f"Failed to run dashboard: {e}")
        raise typer.Exit(1)


@app.command()
def health(
    service: Optional[str] = typer.Option(None, "--service", "-s", help="Check specific service")
):
    """Check health of ACP services."""

    try:
        config = config_manager.load_config()

        services = []
        if service:
            if service == "ingest":
                services = [("Ingest", config.ingest_service.url)]
            elif service == "agents":
                services = [("Agents", config.agents_service.url)]
            else:
                print_error(f"Unknown service: {service}")
                raise typer.Exit(1)
        else:
            services = [
                ("Ingest", config.ingest_service.url),
                ("Agents", config.agents_service.url),
            ]

        all_healthy = True

        for service_name, url in services:
            try:
                response = requests.get(f"{url}/health", timeout=10)

                if response.status_code == 200:
                    health_data = response.json()
                    print_success(f"{service_name} service: {health_data.get('status', 'healthy')}")

                    # Show additional health info if available
                    if "checks" in health_data:
                        for check_name, check_result in health_data["checks"].items():
                            status = check_result.get("status", "unknown")
                            if status == "healthy":
                                console.print(f"  ✓ {check_name}: {status}")
                            else:
                                console.print(f"  ✗ {check_name}: {status}")
                                all_healthy = False
                else:
                    print_error(f"{service_name} service: HTTP {response.status_code}")
                    all_healthy = False

            except requests.RequestException as e:
                print_error(f"{service_name} service: Connection failed - {e}")
                all_healthy = False

        if not all_healthy:
            raise typer.Exit(1)

    except Exception as e:
        print_error(f"Health check failed: {e}")
        raise typer.Exit(1)


@app.command()
def traces(
    service: Optional[str] = typer.Option(None, "--service", "-s", help="Filter by service"),
    operation: Optional[str] = typer.Option(None, "--operation", "-o", help="Filter by operation"),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of traces to show"),
    duration: Optional[str] = typer.Option(
        "1h", "--duration", "-d", help="Time range (e.g., 1h, 30m)"
    ),
):
    """View distributed traces."""

    try:
        # This would integrate with Jaeger API in a real implementation
        print_info("Trace viewing requires Jaeger integration")
        print_info("Jaeger UI available at: http://localhost:16686")

        # For now, show trace IDs from logs
        print_info("Recent trace IDs from logs:")

        # Get recent logs and extract trace IDs
        result = subprocess.run(
            ["docker-compose", "logs", "--tail", "100"],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )

        if result.returncode == 0:
            trace_ids = set()
            for line in result.stdout.split("\n"):
                if "trace_id" in line:
                    try:
                        # Extract trace ID from JSON log
                        if '"trace_id"' in line:
                            parts = line.split('"trace_id":"')
                            if len(parts) > 1:
                                trace_id = parts[1].split('"')[0]
                                trace_ids.add(trace_id)
                    except:
                        pass

            if trace_ids:
                console.print("Found trace IDs:")
                for trace_id in list(trace_ids)[:limit]:
                    console.print(f"  {trace_id}")
            else:
                print_warning("No trace IDs found in recent logs")
        else:
            print_error("Failed to get logs for trace extraction")

    except Exception as e:
        print_error(f"Failed to view traces: {e}")
        raise typer.Exit(1)


@app.command()
def alerts(
    active_only: bool = typer.Option(True, "--active-only", help="Show only active alerts"),
    severity: Optional[str] = typer.Option(
        None, "--severity", help="Filter by severity (critical, warning, info)"
    ),
):
    """View active alerts."""

    try:
        # This would integrate with Alertmanager API in a real implementation
        print_info("Alert viewing requires Alertmanager integration")
        print_info("Alertmanager UI available at: http://localhost:9093")

        # For now, check basic service health as alerts
        config = config_manager.load_config()

        alerts = []

        # Check service health
        services = [("ingest", config.ingest_service.url), ("agents", config.agents_service.url)]

        for service_name, url in services:
            try:
                response = requests.get(f"{url}/health", timeout=5)
                if response.status_code != 200:
                    alerts.append(
                        {
                            "service": service_name,
                            "severity": "critical",
                            "message": f"Service {service_name} is unhealthy (HTTP {response.status_code})",
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
            except:
                alerts.append(
                    {
                        "service": service_name,
                        "severity": "critical",
                        "message": f"Service {service_name} is unreachable",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

        # Check docker containers
        try:
            result = subprocess.run(
                ["docker-compose", "ps", "--format", "json"],
                capture_output=True,
                text=True,
                cwd=Path.cwd(),
            )

            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        try:
                            container = json.loads(line)
                            if container.get("State") != "running":
                                alerts.append(
                                    {
                                        "service": container.get("Name", "unknown"),
                                        "severity": "warning",
                                        "message": f'Container {container.get("Name")} is {container.get("State")}',
                                        "timestamp": datetime.now().isoformat(),
                                    }
                                )
                        except:
                            pass
        except:
            pass

        # Filter alerts
        if severity:
            alerts = [a for a in alerts if a["severity"] == severity]

        # Display alerts
        if alerts:
            table = Table(title="Active Alerts")
            table.add_column("Service", style="cyan")
            table.add_column("Severity", style="red")
            table.add_column("Message", style="white")
            table.add_column("Time", style="blue")

            for alert in alerts:
                severity_color = {"critical": "red", "warning": "yellow", "info": "blue"}.get(
                    alert["severity"], "white"
                )

                table.add_row(
                    alert["service"],
                    f"[{severity_color}]{alert['severity']}[/{severity_color}]",
                    alert["message"],
                    alert["timestamp"],
                )

            console.print(table)
        else:
            print_success("No active alerts")

    except Exception as e:
        print_error(f"Failed to get alerts: {e}")
        raise typer.Exit(1)
