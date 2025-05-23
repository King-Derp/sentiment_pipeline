"""Configuration handling for the Reddit Finance Scraper."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml
from dotenv import load_dotenv


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""

    max_requests_per_minute: int = 100
    min_remaining_calls: int = 5
    sleep_buffer_sec: int = 2


@dataclass
class AlertConfig:
    """Alert thresholds configuration."""
    
    max_fetch_age_sec: int = 1200  # 20 minutes
    max_disk_usage_percent: int = 90


@dataclass
class MonitoringConfig:
    """Monitoring configuration."""
    
    enable_prometheus: bool = True
    prometheus_port: int = 8000
    alerts: AlertConfig = field(default_factory=AlertConfig)


@dataclass
class PostgresConfig:
    """PostgreSQL connection configuration."""
    
    host: str = "localhost"
    port: int = 5432
    database: str = "marketdb"
    user: str = "postgres"
    password: str = ""
    enabled: bool = True
    
    # Alias for database to handle config files that use 'dbname' instead
    @property
    def dbname(self) -> str:
        """Alias for database field for compatibility with configs that use 'dbname'."""
        return self.database
        
    @dbname.setter
    def dbname(self, value: str) -> None:
        """Set database via dbname alias."""
        self.database = value


@dataclass
class Config:
    """Application configuration combining environment variables and YAML config."""

    # Reddit API credentials from environment
    client_id: str = ""
    client_secret: str = ""
    username: str = ""
    password: str = ""
    user_agent: str = "finance_scraper/0.1"

    # YAML config values with defaults
    subreddits: List[str] = field(default_factory=list)
    window_days: int = 30
    csv_path: str = "data/reddit_finance.csv"
    initial_backfill: bool = True
    failure_threshold: int = 5
    maintenance_interval_sec: int = 600
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    
    # Initialize postgres as an empty dict, we'll set it properly in from_files
    postgres: PostgresConfig = None

    @classmethod
    def from_files(cls, config_path: str, env_path: Optional[str] = None) -> "Config":
        """
        Load configuration from YAML file and environment variables.
        
        Args:
            config_path: Path to YAML configuration file
            env_path: Optional path to .env file (defaults to .env in current directory)
            
        Returns:
            Config instance with merged configuration
        """
        # Load environment variables
        if env_path:
            load_dotenv(env_path)
        else:
            load_dotenv()

        # Create config with empty values
        config = cls()
        
        # Set basic configuration
        # Update Reddit API credentials from environment variables
        config.client_id = os.getenv("REDDIT_CLIENT_ID", "")
        config.client_secret = os.getenv("REDDIT_CLIENT_SECRET", "")
        config.username = os.getenv("REDDIT_USERNAME", "")
        config.password = os.getenv("REDDIT_PASSWORD", "")
        config.user_agent = os.getenv("REDDIT_USER_AGENT", "finance_scraper/0.1")
        
        # Create a PostgresConfig object directly without accessing config.postgres first
        postgres_config = PostgresConfig(
            host=os.getenv("PG_HOST", "localhost"),
            port=int(os.getenv("PG_PORT", "5432")),
            database=os.getenv("PG_DB", "marketdb"),
            user=os.getenv("PG_USER", "postgres"),
            password=os.getenv("PG_PASSWORD", ""),
            enabled=os.getenv("USE_POSTGRES", "true").lower() == "true",
        )
        
        # Set the postgres attribute directly
        config.postgres = postgres_config

        # Load and merge YAML config
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as file:
                yaml_config = yaml.safe_load(file)
                
                if yaml_config:
                    # Update top-level attributes
                    for key, value in yaml_config.items():
                        if key != "rate_limit" and hasattr(config, key):
                            setattr(config, key, value)
                    
                    # Handle nested rate_limit config if present
                    if "rate_limit" in yaml_config and isinstance(yaml_config["rate_limit"], dict):
                        rate_limit_config = RateLimitConfig()
                        for key, value in yaml_config["rate_limit"].items():
                            if hasattr(rate_limit_config, key):
                                setattr(rate_limit_config, key, value)
                        config.rate_limit = rate_limit_config
                        
                    # Handle nested monitoring config if present
                    if "monitoring" in yaml_config and isinstance(yaml_config["monitoring"], dict):
                        monitoring_config = MonitoringConfig()
                        
                        # Set top-level monitoring attributes
                        for key, value in yaml_config["monitoring"].items():
                            if key != "alerts" and hasattr(monitoring_config, key):
                                setattr(monitoring_config, key, value)
                        
                        # Handle nested alerts config if present
                        if "alerts" in yaml_config["monitoring"] and isinstance(yaml_config["monitoring"]["alerts"], dict):
                            alerts_config = AlertConfig()
                            for key, value in yaml_config["monitoring"]["alerts"].items():
                                if hasattr(alerts_config, key):
                                    setattr(alerts_config, key, value)
                            monitoring_config.alerts = alerts_config
                            
                        config.monitoring = monitoring_config
                        
                    # Handle nested postgres config if present
                    if "postgres" in yaml_config and isinstance(yaml_config["postgres"], dict):
                        # Get the postgres dict from YAML
                        postgres_dict = yaml_config["postgres"]
                        
                        # Handle special case for 'dbname' vs 'database'
                        if "dbname" in postgres_dict and "database" not in postgres_dict:
                            postgres_dict["database"] = postgres_dict["dbname"]
                        
                        # Get current postgres values safely
                        current_postgres = config.postgres
                        current_host = getattr(current_postgres, "host", "localhost")
                        current_port = getattr(current_postgres, "port", 5432)
                        current_database = getattr(current_postgres, "database", "marketdb")
                        current_user = getattr(current_postgres, "user", "postgres")
                        current_password = getattr(current_postgres, "password", "")
                        current_enabled = getattr(current_postgres, "enabled", True)
                        
                        # Create a new PostgresConfig with the combined values
                        config.postgres = PostgresConfig(
                            host=postgres_dict.get("host", current_host),
                            port=postgres_dict.get("port", current_port),
                            database=postgres_dict.get("database", current_database),
                            user=postgres_dict.get("user", current_user),
                            password=postgres_dict.get("password", current_password),
                            enabled=postgres_dict.get("enabled", current_enabled)
                        )

        # Ensure CSV directory exists
        csv_dir = os.path.dirname(config.csv_path)
        if csv_dir:
            os.makedirs(csv_dir, exist_ok=True)

        return config

    def validate(self) -> List[str]:
        """
        Validate configuration and return a list of validation errors.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        # Check Reddit API credentials
        if not self.client_id:
            errors.append("Missing REDDIT_CLIENT_ID in environment")
        if not self.client_secret:
            errors.append("Missing REDDIT_CLIENT_SECRET in environment")
        if not self.username:
            errors.append("Missing REDDIT_USERNAME in environment")
        if not self.password:
            errors.append("Missing REDDIT_PASSWORD in environment")
            
        # Check subreddits list
        if not self.subreddits:
            errors.append("No subreddits specified in configuration")
            
        # Check window days
        if self.window_days <= 0:
            errors.append("window_days must be greater than 0")
            
        # Check maintenance interval
        if self.maintenance_interval_sec < 60:
            errors.append("maintenance_interval_sec must be at least 60 seconds")
            
        # Check failure threshold
        if self.failure_threshold <= 0:
            errors.append("failure_threshold must be greater than 0")
            
        # Check PostgreSQL configuration if enabled
        if self.postgres.enabled:
            if not self.postgres.host:
                errors.append("PG_HOST must be specified when PostgreSQL is enabled")
            if self.postgres.port <= 0:
                errors.append("PG_PORT must be a positive integer")
            if not self.postgres.database:
                errors.append("PG_DB must be specified when PostgreSQL is enabled")
            if not self.postgres.user:
                errors.append("PG_USER must be specified when PostgreSQL is enabled")
            # Password can be empty for local development with peer authentication
            
        return errors
