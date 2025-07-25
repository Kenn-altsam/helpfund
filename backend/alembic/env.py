from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- Added project-specific configuration ---
import os
import sys
from pathlib import Path

# Add project root to PYTHONPATH so that imports work correctly
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

# Import project settings and models
from src.core.config import get_settings
from src.core.database import Base

# Import all model modules so that Alembic can detect them
import src.auth.models  # noqa: F401
import src.companies.models  # noqa: F401
import src.funds.models  # noqa: F401
import src.chats.models # noqa: F401

# Ensure any percent signs are escaped for ConfigParser interpolation safety
settings = get_settings()
# Override the SQLAlchemy URL in Alembic configuration (escape "%" -> "%%")
escaped_db_url = str(settings.DATABASE_URL).replace("%", "%%")
config.set_main_option("sqlalchemy.url", escaped_db_url)

# Set target metadata for 'autogenerate'
target_metadata = Base.metadata
# --- End added configuration ---

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    # url = config.get_main_option("sqlalchemy.url")
    escaped_db_url = str(settings.DATABASE_URL).replace("%", "%%")
    context.configure(
        url=escaped_db_url,
        target_metadata=target_metadata,
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
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = str(settings.DATABASE_URL).replace("%", "%%")
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
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
