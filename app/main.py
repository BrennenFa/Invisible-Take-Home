from fastapi import FastAPI
from .database import Base, engine
from .auth import router as auth_router


# create database tables ---- remove!!!!!
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Banking REST API")

# include routes from auth
app.include_router(auth_router)


@app.get("/")
def health_check():
    return {"status": "ok"}
