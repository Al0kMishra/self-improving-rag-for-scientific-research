from fastapi import APIRouter

from app.api import arxiv, experiments, feedback, improvement, metrics, papers, queries, retrieval, system

api_router = APIRouter(prefix="/api")
for module in (system, retrieval, queries, feedback, papers, arxiv, metrics, improvement, experiments):
    api_router.include_router(module.router)
