from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from .database import Base, engine
from .security import limiter
from .routes.auth import router as auth_router
from .routes.accounts import router as accounts_router
from .routes.transfers import router as transfers_router
from .routes.transactions import router as transactions_router
from .routes.cards import router as cards_router
from .routes.statements import router as statements_router


# create database tables ---- remove!!!!!
# Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Banking REST API",
    description="A comprehensive banking API with accounts, transfers, cards, and admin features",
    version="2.0.0"
)


# Configure rate limiting with fastapi
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# include routes
app.include_router(auth_router)
app.include_router(accounts_router)
app.include_router(transfers_router)
app.include_router(transactions_router)
app.include_router(cards_router)
app.include_router(statements_router)

# ensure api works
@app.get("/")
def health_check():
    return {"status": "ok"}
