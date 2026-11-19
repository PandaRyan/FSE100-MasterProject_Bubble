# main.py
# FastAPI entry point mounting both the webcam WebSocket router and the Bubble Blitz REST router.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from video_socket import router as video_router
from bubble_router import router as bubble_router

# ---- Constants (with sources from project config & requirements) ----
API_VERSION = "0.1.0"               # Matches version in frontend package.json
DEFAULT_HOST = "0.0.0.0"            # Binds all network interfaces for local dev and free-host deployment
DEFAULT_PORT = 8000                 # Port expected by frontend (ws://localhost:8000 and http://localhost:8000)

app = FastAPI(
    title="FSE100 Master Project API",
    description="Backend API for the FSE100 Master Project.",
    version=API_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows Vite dev server (http://localhost:5173) and deployed frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(video_router)
app.include_router(bubble_router)


@app.get("/")
async def read_root() -> dict[str, str]:
    return {"message": "FSE100 Master Project API"}


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host=DEFAULT_HOST, port=DEFAULT_PORT, reload=True)