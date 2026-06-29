from fastapi import FastAPI
from app.core.connection import init_database
from app.api.v1.router import router

init_database()

app = FastAPI(title="MVP AKP Backend")

app.include_router(router)

@app.get("/")
def read_root():
    return {"data": "response from default endpoint /"}