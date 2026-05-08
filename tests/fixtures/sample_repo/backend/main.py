"""Backend API module for the sample application."""

from __future__ import annotations


class UserService:
    """Service for managing users."""

    def get_user(self, user_id: int) -> dict:
        """Return a user record by ID."""
        return {"id": user_id, "name": "Alice"}

    def create_user(self, name: str) -> dict:
        """Create a new user and return the record."""
        return {"id": 1, "name": name}


def health_check() -> dict:
    """Return API health status."""
    return {"status": "ok"}


# FastAPI route (inline for fixture simplicity)
def get_users_route(service: UserService) -> list[dict]:
    """GET /users endpoint handler."""
    return [service.get_user(1)]
