"""SQLAlchemy models package.

Import order matters for Alembic's autogenerate to pick up all tables.
Import all models here so that they are registered on the metadata.
"""

from app.models.audit_log import AuditLog
from app.models.broker_connection import BrokerConnection
from app.models.holding import Holding
from app.models.portfolio import Portfolio
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.user import User

__all__ = [
    "User",
    "BrokerConnection",
    "Portfolio",
    "Holding",
    "PortfolioSnapshot",
    "AuditLog",
]
