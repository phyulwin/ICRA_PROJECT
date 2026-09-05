from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="ICRA Backend", version="0.1.0")


class HealthResponse(BaseModel):
    status: str
    service: str


@app.get("/health", response_model=HealthResponse)
def healthcheck() -> HealthResponse:
    return {"status": "ok", "service": "icra-backend"}


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "ICRA API is running"}
