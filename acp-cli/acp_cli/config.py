"""Configuration management for ACP CLI."""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv


class ServiceConfig(BaseModel):
    """Configuration for a service endpoint."""
    url: str
    api_key: Optional[str] = None
    timeout: int = 30


class CLIConfig(BaseModel):
    """Main CLI configuration."""
    
    # Service endpoints
    ingest_service: ServiceConfig = Field(
        default_factory=lambda: ServiceConfig(url="http://localhost:8000")
    )
    agents_service: ServiceConfig = Field(
        default_factory=lambda: ServiceConfig(url="http://localhost:8001")
    )
    code_analyzer_service: ServiceConfig = Field(
        default_factory=lambda: ServiceConfig(url="http://localhost:8002")
    )
    
    # CLI settings
    output_format: str = "table"  # table, json, yaml
    verbose: bool = False
    debug: bool = False
    
    # File paths
    config_dir: str = Field(default_factory=lambda: str(Path.home() / ".acp"))
    log_file: Optional[str] = None


class ConfigManager:
    """Manages CLI configuration loading and saving."""
    
    def __init__(self):
        """Initialize configuration manager."""
        self.config_file = Path.home() / ".acp" / "config.yaml"
        self.config_dir = Path.home() / ".acp"
        self._config: Optional[CLIConfig] = None
    
    def load_config(self) -> CLIConfig:
        """Load configuration from file and environment.
        
        Returns:
            Loaded configuration
        """
        if self._config is not None:
            return self._config
        
        # Load from environment first
        load_dotenv()
        
        # Create config directory if it doesn't exist
        self.config_dir.mkdir(exist_ok=True)
        
        # Load from file if it exists
        config_data = {}
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                config_data = yaml.safe_load(f) or {}
        
        # Override with environment variables
        env_overrides = self._get_env_overrides()
        config_data.update(env_overrides)
        
        self._config = CLIConfig(**config_data)
        return self._config
    
    def save_config(self, config: CLIConfig) -> None:
        """Save configuration to file.
        
        Args:
            config: Configuration to save
        """
        self.config_dir.mkdir(exist_ok=True)
        
        with open(self.config_file, 'w') as f:
            yaml.dump(config.dict(), f, default_flow_style=False)
        
        self._config = config
    
    def _get_env_overrides(self) -> Dict[str, Any]:
        """Get configuration overrides from environment variables.
        
        Returns:
            Environment variable overrides
        """
        overrides = {}
        
        # Service URLs
        if os.getenv("ACP_INGEST_URL"):
            overrides.setdefault("ingest_service", {})["url"] = os.getenv("ACP_INGEST_URL")
        
        if os.getenv("ACP_AGENTS_URL"):
            overrides.setdefault("agents_service", {})["url"] = os.getenv("ACP_AGENTS_URL")
        
        if os.getenv("ACP_CODE_ANALYZER_URL"):
            overrides.setdefault("code_analyzer_service", {})["url"] = os.getenv("ACP_CODE_ANALYZER_URL")
        
        # API Keys
        if os.getenv("ACP_INGEST_API_KEY"):
            overrides.setdefault("ingest_service", {})["api_key"] = os.getenv("ACP_INGEST_API_KEY")
        
        if os.getenv("ACP_AGENTS_API_KEY"):
            overrides.setdefault("agents_service", {})["api_key"] = os.getenv("ACP_AGENTS_API_KEY")
        
        if os.getenv("ACP_CODE_ANALYZER_API_KEY"):
            overrides.setdefault("code_analyzer_service", {})["api_key"] = os.getenv("ACP_CODE_ANALYZER_API_KEY")
        
        # CLI settings
        if os.getenv("ACP_OUTPUT_FORMAT"):
            overrides["output_format"] = os.getenv("ACP_OUTPUT_FORMAT")
        
        if os.getenv("ACP_VERBOSE"):
            overrides["verbose"] = os.getenv("ACP_VERBOSE").lower() in ("true", "1", "yes")
        
        if os.getenv("ACP_DEBUG"):
            overrides["debug"] = os.getenv("ACP_DEBUG").lower() in ("true", "1", "yes")
        
        if os.getenv("ACP_LOG_FILE"):
            overrides["log_file"] = os.getenv("ACP_LOG_FILE")
        
        return overrides
    
    def get_service_config(self, service_name: str) -> ServiceConfig:
        """Get configuration for a specific service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Service configuration
        """
        config = self.load_config()
        
        if service_name == "ingest":
            return config.ingest_service
        elif service_name == "agents":
            return config.agents_service
        elif service_name == "code-analyzer":
            return config.code_analyzer_service
        else:
            raise ValueError(f"Unknown service: {service_name}")


# Global configuration manager instance
config_manager = ConfigManager()

