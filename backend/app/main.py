from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.endpoints import router
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the embedding model + open Chroma once at startup so the first query isn't slow
    from app.ingestion.vector_indexer import default_collection

    default_collection()
    yield
    from app import observability

    observability.flush()


app = FastAPI(title="FinSentinel API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api/v1")
