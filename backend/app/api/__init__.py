"""API router aggregation."""

from fastapi import APIRouter

from app.api import auth, chapters, chat, demo, health, plans, quizzes, review, stats, tasks

api_router = APIRouter()
api_router.include_router(auth.auth_router)
api_router.include_router(auth.me_router)
api_router.include_router(plans.router)
api_router.include_router(chapters.router)
api_router.include_router(quizzes.router)
api_router.include_router(tasks.router)
api_router.include_router(chat.router)
api_router.include_router(review.router)
api_router.include_router(stats.router)
api_router.include_router(demo.router)

health_router = health.router
