"""API router for demo/testing endpoints."""

from fastapi import APIRouter

demo_router = APIRouter(prefix="/api/v1", tags=["demo"])


@demo_router.get("/hello")
async def hello_endpoint(name: str = "World") -> dict:
    """Simple hello endpoint for testing."""
    return {"message": f"Hello, {name}!", "service": "FlowForge"}


@demo_router.get("/status")
async def status_endpoint() -> dict:
    """Return service status."""
    return {
        "status": "running",
        "service": "FlowForge",
        "version": "0.1.0",
    }
