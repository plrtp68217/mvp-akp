from fastapi import FastAPI
from app.core.connection import init_database;
from app.api import rules;

init_database()

app = FastAPI(title="MVP AKP Backend")

app.include_router(rules.router)

@app.get("/")
def read_root():
    return {"Hello": "World"}