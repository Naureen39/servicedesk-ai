"""Aggregates all v1 routers (Section 2.5)."""

from __future__ import annotations

from fastapi import APIRouter

from . import admin, analytics, appointments, auth, chat, public, staff, test_console, voice

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(chat.router)
api_router.include_router(voice.router)
api_router.include_router(public.router)
api_router.include_router(appointments.router)
api_router.include_router(staff.router)
api_router.include_router(analytics.router)
api_router.include_router(admin.router)
api_router.include_router(test_console.router)
