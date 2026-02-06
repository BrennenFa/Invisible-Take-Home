from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

"""
Pydantic models for the banking application.
These models are used for request data validation and response serialization."""

class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr

    class Config:
        orm_mode = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AccountCreate(BaseModel):
    type: str
    currency: Optional[str] = "USD"


class AccountOut(BaseModel):
    id: int
    user_id: int
    type: str
    balance: float
    currency: str
    status: str
    created_at: datetime

    class Config:
        orm_mode = True


class TransactionOut(BaseModel):
    id: int
    account_id: int
    type: str
    amount: float
    description: Optional[str]
    reference: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True


class TransferCreate(BaseModel):
    source_account_id: int
    destination_account_id: int
    amount: float
    description: Optional[str] = None


class TransferOut(BaseModel):
    id: str
    source_account_id: int
    destination_account_id: int
    amount: float
    description: Optional[str]
    created_at: datetime
    source_transaction_id: int
    destination_transaction_id: int
