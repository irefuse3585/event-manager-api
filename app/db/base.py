from sqlalchemy.orm import declarative_base

# Base class for all ORM models.
# All mapped classes must inherit from this, so that
# SQLAlchemy collects their metadata in one place.
Base = declarative_base()
