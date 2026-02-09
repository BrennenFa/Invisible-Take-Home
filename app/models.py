from sqlalchemy import Column, String, DateTime, ForeignKey, Numeric, Enum, Index, Integer, Boolean, LargeBinary
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base
import enum
import uuid
from sqlalchemy.dialects.postgresql import UUID

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


class TransactionDirection(enum.Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class TransactionCategory(enum.Enum):
    TRANSFER = "TRANSFER"
    CARD_PAYMENT = "CARD_PAYMENT"
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"


class RoleType(enum.Enum):
    USER = "USER"
    ADMIN = "ADMIN"


class CardType(enum.Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class CardStatus(enum.Enum):
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"
    CANCELLED = "CANCELLED"


# =================================================================
# Models
# =================================================================
class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    # user, admin
    role = Column(Enum(RoleType), default=RoleType.USER)

    # Soft delete fields
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)

    accounts = relationship("Account", back_populates="owner")


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        Index('ix_account_user_id', 'user_id'),
        Index('ix_account_created_at', 'created_at'),
        Index('ix_account_number_encrypted', 'account_number_encrypted'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    type = Column(Enum(AccountType), nullable=False)
    balance = Column(Numeric(precision=10, scale=2), default=0.0, nullable=False)
    status = Column(Enum(AccountStatus), default=AccountStatus.ACTIVE, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    routing_number = Column(String(9), nullable=True, index=False)
    account_number_encrypted = Column(LargeBinary, nullable=True, unique=True)
    account_number_hash = Column(String(64), nullable=True, unique=True, index=True)  # SHA256 hash for lookups
    account_number_masked = Column(String(12), nullable=True)

    owner = relationship("User", back_populates="accounts")
    transactions = relationship("Transaction", back_populates="account", cascade="all, delete-orphan")
    cards = relationship("Card", back_populates="account", cascade="all, delete-orphan")


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index('ix_transaction_account_id', 'account_id'),
        Index('ix_transaction_created_at', 'created_at'),
        Index('ix_transaction_card_id', 'card_id'),
        Index('ix_transaction_category', 'category'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    type = Column(Enum(TransactionDirection), nullable=False)
    amount = Column(Numeric(precision=10, scale=2), nullable=False)
    description = Column(String, nullable=True)
    reference = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # transfer category and link
    category = Column(Enum(TransactionCategory), nullable=False, default=TransactionCategory.TRANSFER)
    card_id = Column(UUID(as_uuid=True), ForeignKey("cards.id"), nullable=True)
    transfer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("transfers.id", name="fk_transaction_transfer", use_alter=True),
        nullable=True
    )
    account = relationship("Account", back_populates="transactions")
    transfer = relationship("Transfer", foreign_keys=[transfer_id])
    card = relationship("Card", foreign_keys=[card_id])


class Transfer(Base):
    __tablename__ = "transfers"
    __table_args__ = (
        Index('ix_transfer_source_account', 'source_account_id'),
        Index('ix_transfer_dest_account', 'destination_account_id'),
        Index('ix_transfer_created_at', 'created_at'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    destination_account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    amount = Column(Numeric(precision=10, scale=2), nullable=False)
    description = Column(String, nullable=True)
    source_transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=False)
    destination_transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Card(Base):
    __tablename__ = "cards"
    __table_args__ = (
        Index('ix_card_account_id', 'account_id'),
        Index('ix_card_status', 'status'),
        Index('ix_card_expiry_date', 'expiry_date'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    card_number = Column(String, unique=True, nullable=False)
    card_holder_name = Column(String, nullable=False)
    # NO CVV - generated, not stored for compliance
    pin_hash = Column(String, nullable=False)
    card_type = Column(Enum(CardType), nullable=False)
    expiry_date = Column(DateTime, nullable=False)
    status = Column(Enum(CardStatus), default=CardStatus.ACTIVE, nullable=False)
    spending_limit = Column(Numeric(precision=10, scale=2), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    account = relationship("Account", back_populates="cards")
    transactions = relationship("Transaction", back_populates="card", foreign_keys="Transaction.card_id")


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (
        Index('ix_idempotency_user_id', 'user_id'),
        Index('ix_idempotency_created_at', 'created_at'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    idempotency_key = Column(String, unique=True, nullable=False, index=True)

    # Request context
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    endpoint = Column(String, nullable=False)

    # Stored response
    response_code = Column(Integer, nullable=False)
    response_body = Column(String, nullable=False)

    # Reference to created resource (if successful)
    transfer_id = Column(UUID(as_uuid=True), ForeignKey("transfers.id"), nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
