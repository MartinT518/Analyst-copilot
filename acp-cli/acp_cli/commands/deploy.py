"""Deployment commands for ACP CLI."""

import os
import sys
import subprocess
import typer
from pathlib import Path
from typing import Optional, List

from ..utils import print_success, print_error, print_info, print_warning

app = typer.Typer(help="Deploy ACP services")


@app.command()
def staging(
    build: bool = typer.Option(False, "--build", help="Build images before deployment"),
    pull: bool = typer.Option(False, "--pull", help="Pull latest images before deployment"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be deployed without actually deploying"),
    force: bool = typer.Option(False, "--force", help="Force deployment even if services are running")
):
    """Deploy ACP stack to staging environment."""
    
    try:
        project_root = Path.cwd()
        
        # Check if docker-compose file exists
        compose_file = project_root / 'docker-compose.staging.yml'
        if not compose_file.exists():
            compose_file = project_root / 'docker-compose.yml'
            if not compose_file.exists():
                print_error("No docker-compose file found")
                raise typer.Exit(1)
        
        # Check if environment file exists
        env_file = project_root / '.env.staging'
        if not env_file.exists():
            env_file = project_root / '.env'
            if not env_file.exists():
                print_warning("No environment file found, using defaults")
        
        print_info("Deploying to staging environment...")
        
        # Build docker-compose command
        cmd = ['docker-compose']
        
        if compose_file.name != 'docker-compose.yml':
            cmd.extend(['-f', str(compose_file)])
        
        if env_file.exists():
            cmd.extend(['--env-file', str(env_file)])
        
        if dry_run:
            cmd.extend(['config'])
            print_info("Dry run - showing configuration:")
        else:
            # Check if services are already running
            if not force:
                status_cmd = cmd + ['ps', '-q']
                result = subprocess.run(status_cmd, cwd=project_root, capture_output=True)
                if result.stdout.strip():
                    print_warning("Services are already running. Use --force to redeploy.")
                    if not typer.confirm("Continue with deployment?"):
                        print_info("Deployment cancelled")
                        return
            
            if pull:
                print_info("Pulling latest images...")
                pull_cmd = cmd + ['pull']
                result = subprocess.run(pull_cmd, cwd=project_root)
                if result.returncode != 0:
                    print_error("Failed to pull images")
                    raise typer.Exit(1)
            
            if build:
                print_info("Building images...")
                build_cmd = cmd + ['build']
                result = subprocess.run(build_cmd, cwd=project_root)
                if result.returncode != 0:
                    print_error("Failed to build images")
                    raise typer.Exit(1)
            
            cmd.extend(['up', '-d'])
        
        # Execute deployment
        result = subprocess.run(cmd, cwd=project_root)
        
        if result.returncode != 0:
            print_error("Deployment to staging failed")
            raise typer.Exit(1)
        
        if not dry_run:
            print_success("Successfully deployed to staging")
            
            # Wait a bit and check health
            import time
            print_info("Waiting for services to start...")
            time.sleep(10)
            
            # Check service health
            _check_deployment_health(cmd[:-2], project_root)
            
    except Exception as e:
        print_error(f"Failed to deploy to staging: {e}")
        raise typer.Exit(1)


@app.command()
def production(
    build: bool = typer.Option(False, "--build", help="Build images before deployment"),
    pull: bool = typer.Option(False, "--pull", help="Pull latest images before deployment"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be deployed without actually deploying"),
    backup: bool = typer.Option(True, "--backup/--no-backup", help="Create database backup before deployment")
):
    """Deploy ACP stack to production environment."""
    
    try:
        project_root = Path.cwd()
        
        # Production deployment requires confirmation
        if not dry_run:
            print_warning("⚠️  PRODUCTION DEPLOYMENT ⚠️")
            print_info("This will deploy to the production environment.")
            if not typer.confirm("Are you sure you want to continue?"):
                print_info("Production deployment cancelled")
                return
        
        # Check if docker-compose file exists
        compose_file = project_root / 'docker-compose.production.yml'
        if not compose_file.exists():
            compose_file = project_root / 'docker-compose.yml'
            if not compose_file.exists():
                print_error("No docker-compose file found")
                raise typer.Exit(1)
        
        # Check if environment file exists
        env_file = project_root / '.env.production'
        if not env_file.exists():
            env_file = project_root / '.env'
            if not env_file.exists():
                print_error("No production environment file found")
                raise typer.Exit(1)
        
        print_info("Deploying to production environment...")
        
        # Create backup if requested
        if backup and not dry_run:
            print_info("Creating database backup...")
            _create_database_backup(project_root)
        
        # Build docker-compose command
        cmd = ['docker-compose']
        
        if compose_file.name != 'docker-compose.yml':
            cmd.extend(['-f', str(compose_file)])
        
        if env_file.exists():
            cmd.extend(['--env-file', str(env_file)])
        
        if dry_run:
            cmd.extend(['config'])
            print_info("Dry run - showing configuration:")
        else:
            if pull:
                print_info("Pulling latest images...")
                pull_cmd = cmd + ['pull']
                result = subprocess.run(pull_cmd, cwd=project_root)
                if result.returncode != 0:
                    print_error("Failed to pull images")
                    raise typer.Exit(1)
            
            if build:
                print_info("Building images...")
                build_cmd = cmd + ['build']
                result = subprocess.run(build_cmd, cwd=project_root)
                if result.returncode != 0:
                    print_error("Failed to build images")
                    raise typer.Exit(1)
            
            cmd.extend(['up', '-d'])
        
        # Execute deployment
        result = subprocess.run(cmd, cwd=project_root)
        
        if result.returncode != 0:
            print_error("Deployment to production failed")
            raise typer.Exit(1)
        
        if not dry_run:
            print_success("Successfully deployed to production")
            
            # Wait a bit and check health
            import time
            print_info("Waiting for services to start...")
            time.sleep(30)  # Production needs more time
            
            # Check service health
            _check_deployment_health(cmd[:-2], project_root)
            
    except Exception as e:
        print_error(f"Failed to deploy to production: {e}")
        raise typer.Exit(1)


@app.command()
def status(
    environment: Optional[str] = typer.Option(None, "--env", "-e", help="Environment to check (staging, production)")
):
    """Show deployment status."""
    
    try:
        project_root = Path.cwd()
        
        # Determine compose file
        if environment == "staging":
            compose_file = project_root / 'docker-compose.staging.yml'
        elif environment == "production":
            compose_file = project_root / 'docker-compose.production.yml'
        else:
            compose_file = project_root / 'docker-compose.yml'
        
        if not compose_file.exists():
            print_error(f"Compose file not found: {compose_file}")
            raise typer.Exit(1)
        
        # Build command
        cmd = ['docker-compose']
        if compose_file.name != 'docker-compose.yml':
            cmd.extend(['-f', str(compose_file)])
        
        # Check docker-compose status
        print_info(f"Docker Compose Services ({compose_file.name}):")
        ps_cmd = cmd + ['ps']
        result = subprocess.run(ps_cmd, cwd=project_root)
        
        if result.returncode != 0:
            print_error("Failed to get service status")
            raise typer.Exit(1)
        
        # Check individual service health
        print_info("\nService Health Checks:")
        _check_deployment_health(cmd, project_root)
        
    except Exception as e:
        print_error(f"Failed to get deployment status: {e}")
        raise typer.Exit(1)


@app.command()
def stop(
    environment: Optional[str] = typer.Option(None, "--env", "-e", help="Environment to stop (staging, production)"),
    remove_volumes: bool = typer.Option(False, "--volumes", "-v", help="Remove volumes as well")
):
    """Stop deployment."""
    
    try:
        project_root = Path.cwd()
        
        # Determine compose file
        if environment == "staging":
            compose_file = project_root / 'docker-compose.staging.yml'
        elif environment == "production":
            compose_file = project_root / 'docker-compose.production.yml'
            # Production requires confirmation
            print_warning("⚠️  STOPPING PRODUCTION SERVICES ⚠️")
            if not typer.confirm("Are you sure you want to stop production services?"):
                print_info("Operation cancelled")
                return
        else:
            compose_file = project_root / 'docker-compose.yml'
        
        if not compose_file.exists():
            print_error(f"Compose file not found: {compose_file}")
            raise typer.Exit(1)
        
        # Build command
        cmd = ['docker-compose']
        if compose_file.name != 'docker-compose.yml':
            cmd.extend(['-f', str(compose_file)])
        
        cmd.append('down')
        
        if remove_volumes:
            cmd.append('-v')
        
        print_info(f"Stopping services...")
        result = subprocess.run(cmd, cwd=project_root)
        
        if result.returncode == 0:
            print_success("Services stopped successfully")
        else:
            print_error("Failed to stop services")
            raise typer.Exit(1)
        
    except Exception as e:
        print_error(f"Failed to stop deployment: {e}")
        raise typer.Exit(1)


@app.command()
def logs(
    service: Optional[str] = typer.Option(None, "--service", "-s", help="Show logs for specific service"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    tail: Optional[int] = typer.Option(None, "--tail", "-n", help="Number of lines to show from end of logs"),
    environment: Optional[str] = typer.Option(None, "--env", "-e", help="Environment (staging, production)")
):
    """Show deployment logs."""
    
    try:
        project_root = Path.cwd()
        
        # Determine compose file
        if environment == "staging":
            compose_file = project_root / 'docker-compose.staging.yml'
        elif environment == "production":
            compose_file = project_root / 'docker-compose.production.yml'
        else:
            compose_file = project_root / 'docker-compose.yml'
        
        if not compose_file.exists():
            print_error(f"Compose file not found: {compose_file}")
            raise typer.Exit(1)
        
        # Build command
        cmd = ['docker-compose']
        if compose_file.name != 'docker-compose.yml':
            cmd.extend(['-f', str(compose_file)])
        
        cmd.append('logs')
        
        if follow:
            cmd.append('-f')
        
        if tail:
            cmd.extend(['--tail', str(tail)])
        
        if service:
            cmd.append(service)
        
        # Execute command
        result = subprocess.run(cmd, cwd=project_root)
        
        if result.returncode != 0:
            print_error("Failed to get logs")
            raise typer.Exit(1)
        
    except Exception as e:
        print_error(f"Failed to get logs: {e}")
        raise typer.Exit(1)


def _check_deployment_health(base_cmd: List[str], project_root: Path):
    """Check health of deployed services."""
    
    # Get list of running services
    ps_cmd = base_cmd + ['ps', '--services', '--filter', 'status=running']
    result = subprocess.run(ps_cmd, cwd=project_root, capture_output=True, text=True)
    
    if result.returncode != 0:
        print_error("Failed to get running services")
        return
    
    services = result.stdout.strip().split('\n')
    services = [s for s in services if s]  # Remove empty lines
    
    if not services:
        print_warning("No services are running")
        return
    
    # Check health of each service
    for service in services:
        try:
            # Get service health status
            health_cmd = base_cmd + ['ps', service]
            result = subprocess.run(health_cmd, cwd=project_root, capture_output=True, text=True)
            
            if result.returncode == 0:
                if 'healthy' in result.stdout.lower():
                    print_success(f"{service}: healthy")
                elif 'unhealthy' in result.stdout.lower():
                    print_error(f"{service}: unhealthy")
                elif 'up' in result.stdout.lower():
                    print_info(f"{service}: running (no health check)")
                else:
                    print_warning(f"{service}: unknown status")
            else:
                print_error(f"{service}: failed to check status")
                
        except Exception as e:
            print_error(f"{service}: error checking health - {e}")


def _create_database_backup(project_root: Path):
    """Create a database backup before production deployment."""
    
    try:
        import datetime
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"backup_production_{timestamp}.sql"
        
        # Create backups directory
        backup_dir = project_root / 'backups'
        backup_dir.mkdir(exist_ok=True)
        
        backup_path = backup_dir / backup_file
        
        # Run pg_dump via docker-compose
        dump_cmd = [
            'docker-compose', '-f', 'docker-compose.production.yml',
            'exec', '-T', 'postgres',
            'pg_dump', '-U', 'acp_user', '-d', 'acp_db'
        ]
        
        with open(backup_path, 'w') as f:
            result = subprocess.run(dump_cmd, cwd=project_root, stdout=f, stderr=subprocess.PIPE)
        
        if result.returncode == 0:
            print_success(f"Database backup created: {backup_path}")
        else:
            print_error(f"Failed to create database backup: {result.stderr.decode()}")
            # Don't fail deployment for backup failure, just warn
            print_warning("Continuing with deployment despite backup failure")
        
    except Exception as e:
        print_error(f"Failed to create database backup: {e}")
        print_warning("Continuing with deployment despite backup failure")

