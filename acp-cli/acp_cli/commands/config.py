"""Commands for managing CLI configuration."""

from typing import Optional

import typer

from ..config import CLIConfig, ServiceConfig, config_manager
from ..utils import format_output, print_error, print_info, print_success

app = typer.Typer(help="Manage CLI configuration")


@app.command()
def show(
    output_format: Optional[str] = typer.Option(
        None, "--format", "-f", help="Output format (table, json, yaml)"
    )
):
    """Show current configuration."""

    try:
        config = config_manager.load_config()
        print_info("Current configuration:")
        print(format_output(config.dict(), output_format))

    except Exception as e:
        print_error(f"Failed to load configuration: {str(e)}")
        raise typer.Exit(1)


@app.command()
def set_service(
    service: str = typer.Argument(..., help="Service name (ingest, agents, code-analyzer)"),
    url: str = typer.Option(..., "--url", "-u", help="Service URL"),
    api_key: Optional[str] = typer.Option(None, "--api-key", "-k", help="API key"),
    timeout: Optional[int] = typer.Option(
        None, "--timeout", "-t", help="Request timeout in seconds"
    ),
):
    """Set service configuration."""

    valid_services = ["ingest", "agents", "code-analyzer"]
    if service not in valid_services:
        print_error(f"Invalid service. Must be one of: {', '.join(valid_services)}")
        raise typer.Exit(1)

    try:
        config = config_manager.load_config()

        # Create service config
        service_config = ServiceConfig(url=url, api_key=api_key, timeout=timeout or 30)

        # Update configuration
        if service == "ingest":
            config.ingest_service = service_config
        elif service == "agents":
            config.agents_service = service_config
        elif service == "code-analyzer":
            config.code_analyzer_service = service_config

        # Save configuration
        config_manager.save_config(config)

        print_success(f"Service '{service}' configuration updated")
        print_info(f"URL: {url}")
        if api_key:
            print_info(f"API Key: {'*' * (len(api_key) - 4) + api_key[-4:]}")
        print_info(f"Timeout: {timeout or 30}s")

    except Exception as e:
        print_error(f"Failed to update service configuration: {str(e)}")
        raise typer.Exit(1)


@app.command()
def set_output(format_type: str = typer.Argument(..., help="Output format (table, json, yaml)")):
    """Set default output format."""

    valid_formats = ["table", "json", "yaml"]
    if format_type not in valid_formats:
        print_error(f"Invalid format. Must be one of: {', '.join(valid_formats)}")
        raise typer.Exit(1)

    try:
        config = config_manager.load_config()
        config.output_format = format_type
        config_manager.save_config(config)

        print_success(f"Default output format set to: {format_type}")

    except Exception as e:
        print_error(f"Failed to update output format: {str(e)}")
        raise typer.Exit(1)


@app.command()
def set_verbose(enabled: bool = typer.Argument(..., help="Enable verbose output")):
    """Set verbose output mode."""

    try:
        config = config_manager.load_config()
        config.verbose = enabled
        config_manager.save_config(config)

        if enabled:
            print_success("Verbose output enabled")
        else:
            print_success("Verbose output disabled")

    except Exception as e:
        print_error(f"Failed to update verbose setting: {str(e)}")
        raise typer.Exit(1)


@app.command()
def set_debug(enabled: bool = typer.Argument(..., help="Enable debug mode")):
    """Set debug mode."""

    try:
        config = config_manager.load_config()
        config.debug = enabled
        config_manager.save_config(config)

        if enabled:
            print_success("Debug mode enabled")
        else:
            print_success("Debug mode disabled")

    except Exception as e:
        print_error(f"Failed to update debug setting: {str(e)}")
        raise typer.Exit(1)


@app.command()
def reset():
    """Reset configuration to defaults."""

    try:
        # Create default configuration
        default_config = CLIConfig()
        config_manager.save_config(default_config)

        print_success("Configuration reset to defaults")

    except Exception as e:
        print_error(f"Failed to reset configuration: {str(e)}")
        raise typer.Exit(1)


@app.command()
def validate():
    """Validate current configuration."""

    try:
        config = config_manager.load_config()

        print_info("Validating configuration...")

        # Test service connections
        from ..client import AgentsClient, CodeAnalyzerClient, IngestClient

        services = [
            ("Ingest", IngestClient),
            ("Agents", AgentsClient),
            ("Code Analyzer", CodeAnalyzerClient),
        ]

        all_healthy = True

        for service_name, client_class in services:
            try:
                with client_class() as client:
                    health = client.health_check()
                    if health.get("status") == "healthy":
                        print_success(f"{service_name} service: OK")
                    else:
                        print_error(f"{service_name} service: {health.get('status', 'Unknown')}")
                        all_healthy = False
            except Exception as e:
                print_error(f"{service_name} service: Connection failed - {str(e)}")
                all_healthy = False

        if all_healthy:
            print_success("All services are healthy")
        else:
            print_error("Some services are not healthy")
            raise typer.Exit(1)

    except Exception as e:
        print_error(f"Configuration validation failed: {str(e)}")
        raise typer.Exit(1)
