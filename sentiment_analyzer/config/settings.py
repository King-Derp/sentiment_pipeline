from typing import Optional, Dict, Any
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn, field_validator
import yaml
from pathlib import Path

# Define the root directory of the sentiment_analyzer service
SERVICE_ROOT_DIR = Path(__file__).parent.parent.resolve()
DEFAULT_CONFIG_PATH = SERVICE_ROOT_DIR / "config" / "app_config.yaml"

class Settings(BaseSettings):
    # Application settings
    APP_NAME: str = "SentimentAnalyzerService"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8001 # Different from potential main app port

    # Database settings
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "user"
    DB_PASSWORD: str = "password"
    DB_NAME: str = "sentiment_db"
    DATABASE_URL: Optional[str] = None # Updated to Optional[str] for Pydantic v2

    @field_validator("DATABASE_URL", mode='before') # Updated for Pydantic v2
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        # Pydantic v2: values.data to access other fields if needed during validation
        # For this validator, direct access to other fields isn't standard without values.data
        # We'll assume direct construction or that other fields are already processed if this were more complex.
        # Simplified for direct construction if v is None:
        db_user = values.data.get("DB_USER")
        db_password = values.data.get("DB_PASSWORD")
        db_host = values.data.get("DB_HOST")
        db_port = values.data.get("DB_PORT")
        db_name = values.data.get("DB_NAME")
        
        return str(PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=db_user,
            password=db_password,
            host=db_host,
            port=str(db_port),
            path=f"/{db_name or ''}",
        ))

    # Model settings
    SPACY_MODEL_NAME: str = "en_core_web_lg"
    FINBERT_MODEL_NAME: str = "ProsusAI/finbert"
    USE_GPU_IF_AVAILABLE: bool = True # For FinBERT

    # Batch processing settings
    EVENT_FETCH_INTERVAL_SECONDS: int = 60
    EVENT_FETCH_BATCH_SIZE: int = 100

    # Logging configuration path (can be overridden by env var)
    LOGGING_CONFIG_PATH: str = str(SERVICE_ROOT_DIR / "config" / "logging_config.yaml")

    # Preprocessor settings
    PREPROCESSOR_TARGET_LANGUAGE: str = "en"

    # Pipeline settings
    PIPELINE_RUN_INTERVAL_SECONDS: int = 60

    model_config = SettingsConfigDict(
        env_file= str(SERVICE_ROOT_DIR / ".env"), # Ensure .env path is a string
        env_file_encoding='utf-8',
        extra='ignore' # Ignore extra fields from env or yaml
    )

    @classmethod
    def load_from_yaml(cls, config_path: Path = DEFAULT_CONFIG_PATH) -> 'Settings':
        # This method is a placeholder for more complex YAML loading logic.
        # Pydantic's BaseSettings primarily loads from .env and class defaults.
        # For true YAML override, a custom settings_customise_sources or pre-initialization logic is needed.
        # For now, we rely on .env for overrides and secrets, and class attributes for defaults.
        # The `app_config.yaml` serves as a reference or for manual configuration comparison.
        
        # Example of how you might load YAML and merge (simplified):
        # initial_data = {}
        # if config_path.exists():
        #     with open(config_path, 'r') as f:
        #         yaml_config = yaml.safe_load(f)
        #     if yaml_config:
        #         initial_data.update(yaml_config)
        # return cls(**initial_data) # This would then be further processed by .env loading via model_config
        
        return cls() # Standard instantiation, .env and defaults will apply

# Instantiate settings
settings = Settings.load_from_yaml()

# Example usage:
if __name__ == "__main__":
    print(f"Running {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"Database URL: {settings.DATABASE_URL}")
    print(f"Spacy Model: {settings.SPACY_MODEL_NAME}")
    print(f"Debug mode: {settings.DEBUG}")
    print(f"Logging config: {settings.LOGGING_CONFIG_PATH}")
