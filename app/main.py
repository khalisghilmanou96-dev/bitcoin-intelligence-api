from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.core.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.2.0", description="Self-hosted Bitcoin knowledge and AI API.")
origins = ["*"] if settings.cors_origins.strip() == "*" else [x.strip() for x in settings.cors_origins.split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)

@app.get("/")
def root():
    return {"name": settings.app_name, "version": "0.2.0", "docs": "/docs", "api": "/v1"}
