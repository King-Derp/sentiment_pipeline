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

# Set sqlalchemy.url dynamically from environment variables
# Using DATABASE_URL_LOCAL for alembic operations run from the host machine
db_url = os.getenv('DATABASE_URL_LOCAL')
if not db_url:
    # Fallback or error if DATABASE_URL_LOCAL is not set in .env
    # For safety, you might want to raise an error or log a warning
    # Constructing from individual PG_ variables as a fallback example:
    pg_user = os.getenv('PG_USER')
    pg_password = os.getenv('PG_PASSWORD')
    pg_host_local = os.getenv('PG_HOST_LOCAL')
    pg_port_host = os.getenv('PG_PORT_HOST')
    pg_db = os.getenv('PG_DB')
    if not all([pg_user, pg_password, pg_host_local, pg_port_host, pg_db]):
        raise ValueError(
            "DATABASE_URL_LOCAL not found in .env, and fallback PG_ variables are also incomplete."
        )
    db_url = f"postgresql://{pg_user}:{pg_password}@{pg_host_local}:{pg_port_host}/{pg_db}"

if db_url:
    config.set_main_option('sqlalchemy.url', db_url)
else:
    # This case should ideally be handled by the check above, but as a safeguard:
    raise ValueError("sqlalchemy.url could not be constructed. Check .env file and DATABASE_URL_LOCAL.")

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
