from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Added imports
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line needs to be positioned at the top of the file.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- Custom Alembic Setup Start ---

# Load environment variables from .env file located in the project root
# The .env file should be two levels up from this env.py file (alembic/env.py -> project_root/.env)
project_root_path = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=project_root_path / '.env')

# Add project root to sys.path to allow imports from reddit_scraper module
sys.path.insert(0, str(project_root_path))

# Import Base and specific models for Alembic's autogenerate support
# Ensure all models that should be managed by Alembic are imported here or in an imported module.
from reddit_scraper.reddit_scraper.models.base import Base
from reddit_scraper.reddit_scraper.models.submission import SubmissionORM # Assuming this is your main model
# If you have other models, import them here as well:
# from reddit_scraper.reddit_scraper.models.another_model import AnotherModel

# Set target_metadata for autogenerate support
# This replaces the original 'target_metadata = None'
_target_metadata = Base.metadata # Renamed to avoid conflict if target_metadata is used as a local var later

# --- Modified sqlalchemy.url Configuration --- 
def get_database_url():
    # 1. Try generic DATABASE_URL (ideal for container, set in scraper.env)
    db_url = os.getenv('DATABASE_URL')
    if db_url:
        return db_url

    # 2. Try DATABASE_URL_LOCAL (for host-based alembic runs, set in root .env)
    db_url_local = os.getenv('DATABASE_URL_LOCAL')
    if db_url_local:
        return db_url_local

    # 3. Try to construct from generic PG_HOST, PG_PORT (for container)
    pg_user = os.getenv('PG_USER')
    pg_password = os.getenv('PG_PASSWORD')
    pg_host = os.getenv('PG_HOST') # Generic host, should be 'timescaledb' in container
    pg_port = os.getenv('PG_PORT') # Generic port, should be '5432' in container
    pg_db = os.getenv('PG_DB')

    if all([pg_user, pg_password, pg_host, pg_port, pg_db]):
        return f"postgresql://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_db}"

    # 4. Try to construct from PG_HOST_LOCAL, PG_PORT_HOST (for host as a fallback)
    # These might be set in the root .env for local alembic runs if DATABASE_URL_LOCAL isn't.
    pg_host_local_val = os.getenv('PG_HOST_LOCAL')
    pg_port_host_val = os.getenv('PG_PORT_HOST')
    if all([pg_user, pg_password, pg_host_local_val, pg_port_host_val, pg_db]):
        return f"postgresql://{pg_user}:{pg_password}@{pg_host_local_val}:{pg_port_host_val}/{pg_db}"
    
    raise ValueError(
        "Database URL could not be determined. Set DATABASE_URL (for container), "
        "DATABASE_URL_LOCAL (for host), or ensure PG_USER, PG_PASSWORD, PG_DB and either "
        "(PG_HOST, PG_PORT) or (PG_HOST_LOCAL, PG_PORT_HOST) are set in your .env file(s)."
    )

db_url_to_use = get_database_url()
config.set_main_option('sqlalchemy.url', db_url_to_use)

# --- Custom Alembic Setup End ---


# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
# target_metadata = None # This line is replaced by the _target_metadata assignment above

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


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
        target_metadata=_target_metadata, # Use the correctly set metadata
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=_target_metadata # Use the correctly set metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
