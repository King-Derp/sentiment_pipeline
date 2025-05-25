import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Add the project root directory to sys.path
# This allows Alembic to find your application's modules
# The alembic.ini is in the project root, and env.py is in ./alembic/
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata

# Import your Base and specific models
# This assumes your models are defined in a way that Base.metadata will capture them.
# Adjust the import path according to your project structure.
from reddit_scraper.reddit_scraper.config import Config
from reddit_scraper.reddit_scraper.models.base import Base # Ensure Base is imported
from reddit_scraper.reddit_scraper.models.submission import RawEventORM # Updated import

# For TimescaleDB, ensure the models are loaded so metadata is correct
# You might need to import all models that are part of Base.metadata
# For example, if you have other ORM models, import them here as well.

# Define the path to the application's main configuration file
# PROJECT_ROOT is f:\Coding\sentiment_pipeline
# config.yaml is in f:\Coding\sentiment_pipeline\reddit_scraper\
APP_CONFIG_YAML_PATH = os.path.join(PROJECT_ROOT, "reddit_scraper", "config.yaml")

# Load application configuration to get database URL
app_config = Config.from_files(APP_CONFIG_YAML_PATH)

# Construct the database URL from your loaded configuration
# For Alembic, we typically want to connect to the DB as it's exposed on the host machine,
# not necessarily how it's configured for services within a Docker network.
if app_config.postgres and app_config.postgres.enabled:
    DB_USER = os.getenv('PG_USER', app_config.postgres.user)
    DB_PASSWORD = os.getenv('PG_PASSWORD', app_config.postgres.password) # PG_PASSWORD should be loaded by Config.from_files via dotenv
    DB_HOST_FOR_ALEMBIC = "localhost" # Alembic runs on the host, connects to localhost
    DB_PORT_FOR_ALEMBIC = os.getenv('PG_PORT_HOST', '5433') # Use the host-mapped port
    DB_NAME = os.getenv('PG_DB', app_config.postgres.database)
    
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST_FOR_ALEMBIC}:{DB_PORT_FOR_ALEMBIC}/{DB_NAME}"
else:
    # Fallback or error if Postgres is not configured/enabled, 
    # or provide a default URL if appropriate for your setup.
    # For example, you might raise an error or use a dummy URL if DB is essential.
    print("PostgreSQL is not enabled or configured in app_config. Check config.yaml and .env")
    DATABASE_URL = "sqlite:///./alembic_dummy.db" # Example fallback, adjust as needed

# Set the sqlalchemy.url in the Alembic config object
# This will be used by Alembic to connect to the database.
config.set_main_option('sqlalchemy.url', DATABASE_URL)

# Set target_metadata for Alembic
# target_metadata = SubmissionORM.metadata # Old metadata
# target_metadata = RawEventORM.metadata # Use the metadata from your specific model or Base
# If you have multiple models under the same Base, Base.metadata is usually preferred:
target_metadata = Base.metadata # Corrected to use Base.metadata for comprehensive schema detection

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    herein as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Include TimescaleDB specific types if necessary for offline mode
        # This typically involves registering type compilers
        # For example:
        # render_item=render_hypertable_item, # Custom render function for hypertables
        # render_item=render_continuous_aggregate_item # Custom render for continuous aggregates
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # connectable = engine_from_config(
    #     config.get_section(config.config_ini_section, {}),
    #     prefix="sqlalchemy.",
    #     poolclass=pool.NullPool,
    # )
    connectable = engine_from_config(
        {'sqlalchemy.url': DATABASE_URL}, # Pass the URL directly
        prefix="sqlalchemy.",
        poolclass=pool.NullPool
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
