from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from ramus_api.infrastructure.database import Base
from ramus_api.infrastructure.receipts import ReceiptRow  # noqa: F401
from ramus_api.modules.access.infrastructure import MembershipRow, ProjectRow, SessionRow, UserRow  # noqa: F401
from ramus_api.modules.conversations.infrastructure import ConversationRow, MessageRow  # noqa: F401
from ramus_api.settings import Settings

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", Settings().database_url.replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
