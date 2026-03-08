from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.auth import router as auth_router
from app.routers import router as api_router

app = FastAPI(title="UAV Platform API Gateway", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, tags=["Authentication"])
app.include_router(api_router, tags=["Proxy to Internal Services"])

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "api_gateway"}
