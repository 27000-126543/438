from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.routers import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="智能网联汽车测试与运营监管系统",
    description="IVMS - Intelligent Connected Vehicle Testing and Operation Supervision System",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/", tags=["系统"])
async def root():
    return {
        "name": "智能网联汽车测试与运营监管系统",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health", tags=["系统"])
async def health_check():
    return {
        "status": "healthy",
        "database": "connected",
        "timestamp": datetime.utcnow().isoformat()
    }
