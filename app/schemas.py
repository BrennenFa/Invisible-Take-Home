from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime
from typing import Optional
from uuid import UUID
import re
from .models import AccountType, CardType, AccountStatus, CardStatus, TransactionDirection, TransactionCategory

"""
Pydantic models for the banking application.
These models are used for request data validation and response serialization."""

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=100,
        description="Password must be at least 8 characters"
    )
    
    # validate password strength
    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v):
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        return v


class UserOut(BaseModel):
    id: UUID
    email: EmailStr

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AccountCreate(BaseModel):
    type: AccountType = Field(
        description="Account type: CHECKING or SAVINGS"
    )


class AccountOut(BaseModel):
    id: UUID
    user_id: UUID
    type: AccountType
    balance: float
    status: AccountStatus
    created_at: datetime

    class Config:
        from_attributes = True


class TransactionOut(BaseModel):
    id: UUID
    account_id: UUID
    type: TransactionDirection
    amount: float
    description: Optional[str]
    reference: Optional[str]
    created_at: datetime
    category: TransactionCategory
    transfer_id: Optional[UUID]
    card_id: Optional[UUID]

    class Config:
        from_attributes = True


class TransferCreate(BaseModel):
    source_account_id: UUID
    destination_account_id: UUID
    amount: float = Field(
        gt=0,
        le=1000000,
        description="Transfer amount must be positive and not exceed $1,000,000"
    )
    description: Optional[str] = Field(None, max_length=500)

    # valute amount (must have at most 2 decimal places)
    @field_validator('amount')
    @classmethod
    def validate_decimal_places(cls, v):
        if round(v, 2) != v:
            raise ValueError('Amount must have at most 2 decimal places')
        return v

    # validate that source and destination accounts are different
    @field_validator('destination_account_id')
    @classmethod
    def validate_accounts_different(cls, v, info):
        if 'source_account_id' in info.data and v == info.data['source_account_id']:
            raise ValueError('Source and destination accounts must be different')
        return v


class TransferOut(BaseModel):
    id: UUID
    source_account_id: UUID
    destination_account_id: UUID
    amount: float
    description: Optional[str]
    created_at: datetime
    source_transaction_id: UUID
    destination_transaction_id: UUID


class DepositCreate(BaseModel):
    account_id: UUID
    amount: float = Field(
        gt=0,
        le=100000,
        description="Deposit amount must be positive and not exceed $100,000"
    )
    description: Optional[str] = Field(None, max_length=500)

    # validate amount (must have at most 2 decimal places)
    @field_validator('amount')
    @classmethod
    def validate_decimal_places(cls, v):
        if round(v, 2) != v:
            raise ValueError('Amount must have at most 2 decimal places')
        return v


class WithdrawalCreate(BaseModel):
    account_id: UUID
    amount: float = Field(
        gt=0,
        le=50000,
        description="Withdrawal amount must be positive and not exceed $50,000"
    )
    description: Optional[str] = Field(None, max_length=500)

    # validate amount (must have at most 2 decimal places)
    @field_validator('amount')
    @classmethod
    def validate_decimal_places(cls, v):
        if round(v, 2) != v:
            raise ValueError('Amount must have at most 2 decimal places')
        return v


class CardCreate(BaseModel):
    account_id: UUID
    card_holder_name: str = Field(
        min_length=2,
        max_length=50,
        description="Cardholder name (2-50 characters)"
    )

    # validate pin -> must be 4 digits
    pin: str = Field(
        min_length=4,
        max_length=4,
        pattern=r'^\d{4}$',
        description="4-digit PIN"
    )
    card_type: CardType = Field(
        description="Card type: DEBIT or CREDIT"
    )


    # enforce optional spending limit between 0 and 50,000
    spending_limit: Optional[float] = Field(None, gt=0, le=50000)

    @field_validator('card_holder_name')
    @classmethod
    def validate_card_holder_name(cls, v):
        # Only allow letters, spaces, hyphens, and periods
        if not re.match(r'^[A-Za-z\s\-\.]+$', v):
            raise ValueError('Card holder name can only contain letters, spaces, hyphens, and periods')
        return v.strip()


    # enforce spending limit to have at most 2 decimal places
    @field_validator('spending_limit')
    @classmethod
    def validate_decimal_places(cls, v):
        if v is not None and round(v, 2) != v:
            raise ValueError('Spending limit must have at most 2 decimal places')
        return v


class CardOut(BaseModel):
    id: UUID
    account_id: UUID
    card_number_masked: str  # Only last 4 digits shown
    card_holder_name: str
    expiry_date: datetime
    card_type: CardType
    status: CardStatus
    spending_limit: Optional[float]
    created_at: datetime

    @classmethod
    def from_card(cls, card):
        """Create CardOut from Card model with masked card number."""
        return cls(
            id=card.id,
            account_id=card.account_id,
            # mask card for security: show only last 4 digits
            card_number_masked=f"****-****-****-{card.card_number[-4:]}",
            card_holder_name=card.card_holder_name,
            expiry_date=card.expiry_date,
            card_type=card.card_type,
            status=card.status,
            spending_limit=card.spending_limit,
            created_at=card.created_at
        )

    class Config:
        from_attributes = True


class CardCreateResponse(BaseModel):
    """Response when creating a new card -- only instance where cvv is shared ."""
    id: UUID
    account_id: UUID
    card_number: str
    card_holder_name: str
    # Only returned at creation, never stored or retrievable again (compliance)
    cvv: str  
    expiry_date: datetime
    card_type: CardType
    status: CardStatus
    spending_limit: Optional[float]
    created_at: datetime
    message: str = "IMPORTANT: Save your CVV securely. It cannot be retrieved later."

    class Config:
        from_attributes = True


class CardPaymentCreate(BaseModel):
    card_id: UUID
    
    # enforce amount between 0 and 10,000
    amount: float = Field(
        gt=0,
        le=10000,
        description="Payment amount must be positive and not exceed $10,000"
    )
    description: Optional[str] = Field(None, max_length=500)
    merchant: Optional[str] = Field(None, max_length=100)

    # enforce amount to have at most 2 decimal places
    @field_validator('amount')
    @classmethod
    def validate_decimal_places(cls, v):
        if round(v, 2) != v:
            raise ValueError('Amount must have at most 2 decimal places')
        return v
