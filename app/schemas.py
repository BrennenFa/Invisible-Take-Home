from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional
from uuid import UUID

"""
Pydantic models for the banking application.
These models are used for request data validation and response serialization."""

class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: UUID
    email: EmailStr

    class Config:
        orm_mode = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AccountCreate(BaseModel):
    type: str


class AccountOut(BaseModel):
    id: UUID
    user_id: UUID
    type: str
    balance: float
    status: str
    overdraft_limit: float
    created_at: datetime

    class Config:
        orm_mode = True


class TransactionOut(BaseModel):
    id: UUID
    account_id: UUID
    type: str
    amount: float
    description: Optional[str]
    reference: Optional[str]
    created_at: datetime
    category: str
    transfer_id: Optional[UUID]
    card_id: Optional[UUID]

    class Config:
        orm_mode = True


class TransferCreate(BaseModel):
    source_account_id: UUID
    destination_account_id: UUID
    amount: float
    description: Optional[str] = None


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
    amount: float
    description: Optional[str] = None


class WithdrawalCreate(BaseModel):
    account_id: UUID
    amount: float
    description: Optional[str] = None


class CardCreate(BaseModel):
    account_id: UUID
    card_holder_name: str
    pin: str
    card_type: str
    spending_limit: Optional[float] = None


class CardOut(BaseModel):
    id: UUID
    account_id: UUID
    card_number: str
    card_holder_name: str
    expiry_date: datetime
    card_type: str
    status: str
    spending_limit: Optional[float]
    created_at: datetime

    class Config:
        orm_mode = True


class CardPaymentCreate(BaseModel):
    card_id: UUID
    amount: float
    description: Optional[str] = None
    merchant: Optional[str] = None
