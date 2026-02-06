from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base
import enum

"""
Database models for the banking application.
"""


# =================================================================
# Enums - enforce specificicity
# =================================================================


# Account types
class AccountType(enum.Enum):
    CHECKING = "CHECKING"
    SAVINGS = "SAVINGS"


class AccountStatus(enum.Enum):
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"
    CLOSED = "CLOSED"


class TransactionType(enum.Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class RoleType(enum.Enum):
    USER = "USER"
    ADMIN = "ADMIN"


# =================================================================
# Models
# =================================================================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    # user, admin
    role = Column(Enum(RoleType), default=RoleType.USER)

    accounts = relationship("Account", back_populates="owner")


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(Enum(AccountType), nullable=False)
    balance = Column(Numeric(precision=10, scale=2), default=0.0, nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    status = Column(Enum(AccountStatus), default=AccountStatus.ACTIVE, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    owner = relationship("User", back_populates="accounts")
    transactions = relationship("Transaction", back_populates="account", cascade="all, delete-orphan")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    type = Column(Enum(TransactionType), nullable=False)
    amount = Column(Numeric(precision=10, scale=2), nullable=False)
    description = Column(String, nullable=True)
    reference = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    account = relationship("Account", back_populates="transactions")


class Transfer(Base):
    __tablename__ = "transfers"

    id = Column(String, primary_key=True)
    source_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    destination_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    amount = Column(Numeric(precision=10, scale=2), nullable=False)
    description = Column(String, nullable=True)
    source_transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)
    destination_transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
