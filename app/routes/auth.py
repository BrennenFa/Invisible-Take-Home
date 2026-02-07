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
from ..models import User
from ..schemas import UserCreate, Token, UserOut


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

    db_user = db.execute(select(User).filter(User.email == user.email)).scalar_one_or_none()

    # validate user password
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(db_user.id)
    return {"access_token": token}


@router.get("/me", response_model=UserOut)
@limiter.limit("60/minute")
def me(request: Request, current_user: User = Depends(get_current_user)):
    return current_user


