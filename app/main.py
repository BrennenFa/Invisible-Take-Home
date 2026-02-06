from fastapi import FastAPI
from .database import Base, engine
from .routes.auth import router as auth_router
from .routes.accounts import router as accounts_router
from .routes.transfers import router as transfers_router


# create database tables ---- remove!!!!!
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Banking REST API")

# include routes from auth
app.include_router(auth_router)
app.include_router(accounts_router)
app.include_router(transfers_router)


@app.get("/")
def health_check():
    return {"status": "ok"}
