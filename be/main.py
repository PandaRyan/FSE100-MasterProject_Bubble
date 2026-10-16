from fastapi import FastAPI

app = FastAPI(
    title="FSE100 Master Project API",
    description="Backend API for the FSE100 Master Project.",
    version="0.1.0",
)


@app.get("/")
async def read_root() -> dict[str, str]:
    return {"message": "FSE100 Master Project API"}


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
