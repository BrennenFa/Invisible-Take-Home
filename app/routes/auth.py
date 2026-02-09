import os
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
from uuid import UUID
from ..security import get_current_user
from ..security import limiter

from ..database import get_db
from ..models import User, Account, Card, AccountStatus, CardStatus
from ..schemas import UserCreate, Token, UserOut, PasswordChange, EmailChange, AccountDelete, AccountDeleteResponse


load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))


# auth routes
router = APIRouter(prefix="/auth", tags=["auth"])

# handle password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# =================================================================
# Auth helper methods
# =================================================================
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def create_access_token(user_id: UUID):
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


# =================================================================
# Auth routes
# =================================================================
@router.post("/signup", response_model=Token)
@limiter.limit("5/minute")
def signup(request: Request, user: UserCreate, db: Session = Depends(get_db)):

    # check if email exists - idempotency
    if db.execute(select(User).filter(User.email == user.email)).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    # create user
    db_user = User(
        email=user.email,
        hashed_password=hash_password(user.password)
    )

    # add user to db
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # user access token
    token = create_access_token(db_user.id)
    return {"access_token": token}


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
def login(request: Request, user: UserCreate, db: Session = Depends(get_db)):


    # ensure user exists and is not soft-deleted
    db_user = db.execute(
            select(User).filter(
                User.email == user.email, 
                User.is_deleted == False
            )
        ).scalar_one_or_none()
    

    # validate user password
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(db_user.id)
    return {"access_token": token}


@router.get("/me", response_model=UserOut)
@limiter.limit("60/minute")
def me(request: Request, current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/password", response_model=dict)
@limiter.limit("5/minute")
def change_password(
    request: Request,
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change current user's password"""
    # Verify current password
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    # Hash and update new password
    current_user.hashed_password = hash_password(password_data.new_password)
    db.commit()

    return {"message": "Password changed successfully"}


@router.patch("/email", response_model=UserOut)
@limiter.limit("3/minute")
def change_email(
    request: Request,
    email_data: EmailChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change current user's email"""
    # Verify password
    if not verify_password(email_data.password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid password")

    # Check if new email already exists
    existing = db.execute(select(User).filter(User.email == email_data.new_email)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Email already in use")

    # Update email
    current_user.email = email_data.new_email
    db.commit()
    db.refresh(current_user)

    return current_user


@router.delete("/account", response_model=AccountDeleteResponse)
@limiter.limit("3/hour")
def delete_account(
    request: Request,
    delete_data: AccountDelete,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete user account (soft delete with email anonymization)"""
    # Verify password
    if not verify_password(delete_data.password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid password")

    # Check for non-zero balances across all accounts
    accounts = db.execute(select(Account).filter(
        Account.user_id == current_user.id,
        Account.status == AccountStatus.ACTIVE
    )).scalars().all()

    total_balance = sum(float(account.balance) for account in accounts)
    if total_balance != 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete account with outstanding balance of ${total_balance}. "
                   "Please transfer or withdraw all funds first."
        )

    # Close all accounts
    accounts_closed = 0
    for account in accounts:
        account.status = AccountStatus.CLOSED
        accounts_closed += 1

    # Cancel all cards
    cards = db.execute(select(Card).filter(
        Card.account_id.in_([a.id for a in accounts]),
        Card.status != CardStatus.CANCELLED
    )).scalars().all()

    cards_cancelled = 0
    for card in cards:
        card.status = CardStatus.CANCELLED
        cards_cancelled += 1

    # Soft delete user and anonymize email
    current_user.is_deleted = True
    current_user.deleted_at = datetime.utcnow()
    current_user.email = f"deleted_{current_user.id}@deleted.local"

    db.commit()

    return AccountDeleteResponse(
        message="Account successfully deleted",
        deleted_at=current_user.deleted_at,
        accounts_closed=accounts_closed,
        cards_cancelled=cards_cancelled
    )


