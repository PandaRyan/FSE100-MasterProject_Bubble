from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from video_socket import router as video_router

app = FastAPI(
    title="FSE100 Master Project API",
    description="Backend API for the FSE100 Master Project.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production to your React app's URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(video_router)

@app.get("/")
async def read_root() -> dict[str, str]:
    return {"message": "FSE100 Master Project API"}


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)