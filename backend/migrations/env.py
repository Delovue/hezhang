import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv

from app.database import build_engine
from app.models import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name, disable_existing_loggers=False)
load_dotenv()
url = config.attributes.get("database_url") or os.getenv(
    "HEZHANG_DATABASE_URL", "sqlite:///./data/hezhang.db"
)

if context.is_offline_mode():
    context.configure(
        url=url,
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        transactional_ddl=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = build_engine(url)
    try:
        with engine.connect().execution_options(transaction_mode="IMMEDIATE") as connection:
            context.configure(
                connection=connection,
                target_metadata=Base.metadata,
                render_as_batch=True,
                compare_type=True,
                transactional_ddl=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()
