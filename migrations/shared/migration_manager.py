"""Migration management utility for ACP services."""

import os
import sys
import subprocess
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class MigrationManager:
    """Manager for database migrations across ACP services."""
    
    def __init__(self, project_root: Optional[str] = None):
        """Initialize migration manager.
        
        Args:
            project_root: Path to project root directory
        """
        if project_root:
            self.project_root = Path(project_root)
        else:
            # Find project root by looking for migrations directory
            current = Path(__file__).parent
            while current.parent != current:
                if (current / "migrations").exists():
                    self.project_root = current
                    break
                current = current.parent
            else:
                raise RuntimeError("Could not find project root")
        
        self.migrations_dir = self.project_root / "migrations"
        self.services = ["acp-ingest", "acp-agents"]
    
    def _run_alembic_command(
        self,
        service: str,
        command: List[str],
        capture_output: bool = True
    ) -> subprocess.CompletedProcess:
        """Run an Alembic command for a specific service.
        
        Args:
            service: Service name
            command: Alembic command and arguments
            capture_output: Whether to capture output
            
        Returns:
            Completed process
        """
        service_dir = self.migrations_dir / service
        if not service_dir.exists():
            raise ValueError(f"Migration directory not found for service: {service}")
        
        # Change to service directory
        original_cwd = os.getcwd()
        try:
            os.chdir(self.project_root)
            
            # Build alembic command
            alembic_cmd = [
                sys.executable, "-m", "alembic",
                "-c", str(service_dir / "alembic.ini")
            ] + command
            
            logger.info(f"Running: {' '.join(alembic_cmd)}")
            
            result = subprocess.run(
                alembic_cmd,
                capture_output=capture_output,
                text=True,
                cwd=self.project_root
            )
            
            if result.returncode != 0:
                logger.error(f"Alembic command failed: {result.stderr}")
            
            return result
            
        finally:
            os.chdir(original_cwd)
    
    def create_migration(
        self,
        service: str,
        message: str,
        autogenerate: bool = True
    ) -> bool:
        """Create a new migration for a service.
        
        Args:
            service: Service name
            message: Migration message
            autogenerate: Whether to use autogenerate
            
        Returns:
            True if successful
        """
        if service not in self.services:
            raise ValueError(f"Unknown service: {service}")
        
        command = ["revision"]
        if autogenerate:
            command.append("--autogenerate")
        command.extend(["-m", message])
        
        result = self._run_alembic_command(service, command)
        return result.returncode == 0
    
    def upgrade_database(
        self,
        service: str,
        revision: str = "head"
    ) -> bool:
        """Upgrade database to a specific revision.
        
        Args:
            service: Service name
            revision: Target revision (default: head)
            
        Returns:
            True if successful
        """
        if service not in self.services:
            raise ValueError(f"Unknown service: {service}")
        
        result = self._run_alembic_command(service, ["upgrade", revision])
        return result.returncode == 0
    
    def downgrade_database(
        self,
        service: str,
        revision: str
    ) -> bool:
        """Downgrade database to a specific revision.
        
        Args:
            service: Service name
            revision: Target revision
            
        Returns:
            True if successful
        """
        if service not in self.services:
            raise ValueError(f"Unknown service: {service}")
        
        result = self._run_alembic_command(service, ["downgrade", revision])
        return result.returncode == 0
    
    def get_current_revision(self, service: str) -> Optional[str]:
        """Get current database revision for a service.
        
        Args:
            service: Service name
            
        Returns:
            Current revision or None
        """
        if service not in self.services:
            raise ValueError(f"Unknown service: {service}")
        
        result = self._run_alembic_command(service, ["current"])
        if result.returncode == 0:
            output = result.stdout.strip()
            if output and not output.startswith("INFO"):
                return output.split()[0] if output else None
        return None
    
    def get_migration_history(self, service: str) -> List[Dict[str, Any]]:
        """Get migration history for a service.
        
        Args:
            service: Service name
            
        Returns:
            List of migration information
        """
        if service not in self.services:
            raise ValueError(f"Unknown service: {service}")
        
        result = self._run_alembic_command(service, ["history", "--verbose"])
        migrations = []
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            current_migration = {}
            
            for line in lines:
                line = line.strip()
                if line.startswith("Rev:"):
                    if current_migration:
                        migrations.append(current_migration)
                    current_migration = {"revision": line.split(":")[1].strip()}
                elif line.startswith("Parent:"):
                    current_migration["parent"] = line.split(":")[1].strip()
                elif line.startswith("Branch:"):
                    current_migration["branch"] = line.split(":")[1].strip()
                elif line.startswith("Path:"):
                    current_migration["path"] = line.split(":")[1].strip()
                elif line and not line.startswith("INFO"):
                    current_migration["message"] = line
            
            if current_migration:
                migrations.append(current_migration)
        
        return migrations
    
    def check_migration_status(self, service: str) -> Dict[str, Any]:
        """Check migration status for a service.
        
        Args:
            service: Service name
            
        Returns:
            Migration status information
        """
        if service not in self.services:
            raise ValueError(f"Unknown service: {service}")
        
        current = self.get_current_revision(service)
        history = self.get_migration_history(service)
        
        # Check if there are pending migrations
        result = self._run_alembic_command(service, ["heads"])
        head_revision = None
        if result.returncode == 0:
            output = result.stdout.strip()
            if output and not output.startswith("INFO"):
                head_revision = output.split()[0]
        
        return {
            "service": service,
            "current_revision": current,
            "head_revision": head_revision,
            "up_to_date": current == head_revision,
            "migration_count": len(history),
            "migrations": history
        }
    
    def upgrade_all_services(self) -> Dict[str, bool]:
        """Upgrade all services to head revision.
        
        Returns:
            Results for each service
        """
        results = {}
        for service in self.services:
            try:
                results[service] = self.upgrade_database(service)
            except Exception as e:
                logger.error(f"Failed to upgrade {service}: {e}")
                results[service] = False
        return results
    
    def check_all_services(self) -> Dict[str, Dict[str, Any]]:
        """Check migration status for all services.
        
        Returns:
            Status for each service
        """
        results = {}
        for service in self.services:
            try:
                results[service] = self.check_migration_status(service)
            except Exception as e:
                logger.error(f"Failed to check {service}: {e}")
                results[service] = {
                    "service": service,
                    "error": str(e)
                }
        return results
    
    def create_seed_data(self, service: str) -> bool:
        """Create seed data migration for a service.
        
        Args:
            service: Service name
            
        Returns:
            True if successful
        """
        return self.create_migration(
            service,
            f"Add seed data for {service}",
            autogenerate=False
        )
    
    def validate_migrations(self, service: str) -> Dict[str, Any]:
        """Validate migrations for a service.
        
        Args:
            service: Service name
            
        Returns:
            Validation results
        """
        if service not in self.services:
            raise ValueError(f"Unknown service: {service}")
        
        # Check if migrations directory exists
        service_dir = self.migrations_dir / service
        versions_dir = service_dir / "versions"
        
        validation = {
            "service": service,
            "migrations_dir_exists": service_dir.exists(),
            "versions_dir_exists": versions_dir.exists(),
            "alembic_ini_exists": (service_dir / "alembic.ini").exists(),
            "env_py_exists": (service_dir / "env.py").exists(),
            "migration_files": [],
            "errors": []
        }
        
        if versions_dir.exists():
            migration_files = list(versions_dir.glob("*.py"))
            validation["migration_files"] = [f.name for f in migration_files]
            validation["migration_count"] = len(migration_files)
        
        # Check for common issues
        if not validation["migrations_dir_exists"]:
            validation["errors"].append("Migrations directory does not exist")
        
        if not validation["alembic_ini_exists"]:
            validation["errors"].append("alembic.ini file does not exist")
        
        if not validation["env_py_exists"]:
            validation["errors"].append("env.py file does not exist")
        
        return validation


# Global migration manager instance
migration_manager = MigrationManager()

