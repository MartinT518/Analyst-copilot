"""Main CLI application for Analyst Copilot."""

from typing import Optional

import typer

from .commands import agents
from .commands import config as config_cmd
from .commands import deploy, ingest, monitor, scan, test
from .config import config_manager
from .utils import print_error, print_info

app = typer.Typer(
    name="acp",
    help="Analyst Copilot CLI - Command-line interface for ACP services",
    no_args_is_help=True,
)

# Add subcommands
app.add_typer(ingest.app, name="ingest", help="Interact with the ingest service")
app.add_typer(agents.app, name="agents", help="Interact with the agents service")
app.add_typer(config_cmd.app, name="config", help="Manage CLI configuration")
app.add_typer(test.app, name="test", help="Run tests for ACP services")
app.add_typer(deploy.app, name="deploy", help="Deploy ACP services")
app.add_typer(monitor.app, name="monitor", help="Monitor ACP services")
app.add_typer(scan.app, name="scan", help="Security scanning for ACP services")


@app.command()
def version():
    """Show CLI version information."""
    print_info("Analyst Copilot CLI v1.0.0")
    print_info("Copyright (c) 2024 ACP Development Team")


@app.command()
def status():
    """Check status of all ACP services."""

    try:
        from .client import AgentsClient, IngestClient

        print_info("Checking ACP services status...")

        services = [
            ("Ingest Service", IngestClient),
            ("Agents Service", AgentsClient),
        ]

        all_healthy = True

        for service_name, client_class in services:
            try:
                with client_class() as client:
                    health = client.health_check()
                    status = health.get("status", "unknown")

                    if status == "healthy":
                        print_info(f"✅ {service_name}: {status}")
                    else:
                        print_error(f"❌ {service_name}: {status}")
                        all_healthy = False

                        if "error" in health:
                            print_error(f"   Error: {health['error']}")

            except Exception as e:
                print_error(f"❌ {service_name}: Connection failed")
                print_error(f"   Error: {str(e)}")
                all_healthy = False

        if all_healthy:
            print_info("\n🎉 All services are healthy!")
        else:
            print_error(
                "\n⚠️  Some services are not healthy. Check configuration with 'acp config validate'"
            )
            raise typer.Exit(1)

    except Exception as e:
        print_error(f"Status check failed: {str(e)}")
        raise typer.Exit(1)


@app.command()
def init():
    """Initialize ACP CLI configuration."""

    print_info("Initializing ACP CLI configuration...")

    try:
        # Load or create default configuration
        config = config_manager.load_config()

        print_info("Configuration initialized successfully!")
        print_info(f"Config directory: {config.config_dir}")
        print_info("Use 'acp config show' to view current configuration")
        print_info("Use 'acp config set-service' to configure service endpoints")

    except Exception as e:
        print_error(f"Initialization failed: {str(e)}")
        raise typer.Exit(1)


@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode"),
    config_file: Optional[str] = typer.Option(None, "--config", help="Path to configuration file"),
):
    """
    Analyst Copilot CLI - Command-line interface for ACP services.

    The ACP CLI provides commands to interact with the Analyst Copilot services:
    - ingest: Upload documents and search the knowledge base
    - agents: Start workflows and interact with AI agents
    - config: Manage CLI configuration

    Examples:
        acp ingest upload document.pdf
        acp agents clarify "Analyze user authentication flow"
        acp config set-service ingest --url http://localhost:8000
    """

    # Update configuration with command-line options
    if verbose or debug:
        try:
            config = config_manager.load_config()
            if verbose:
                config.verbose = True
            if debug:
                config.debug = True
            config_manager.save_config(config)
        except Exception:
            # Ignore configuration errors during startup
            pass


if __name__ == "__main__":
    app()
