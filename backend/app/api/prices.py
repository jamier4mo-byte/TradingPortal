"""Prompt 4: see docs/build/prompt4-api.md."""

from fastapi import APIRouter

router = APIRouter(prefix="/prices", tags=["prices"])
