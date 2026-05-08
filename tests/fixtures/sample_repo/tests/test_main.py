"""Tests for the backend main module."""

from __future__ import annotations

from backend.main import UserService, health_check


def test_health_check_returns_ok():
    assert health_check()["status"] == "ok"


def test_user_service_get_user():
    svc = UserService()
    user = svc.get_user(42)
    assert user["id"] == 42


def test_user_service_create_user():
    svc = UserService()
    user = svc.create_user("Bob")
    assert user["name"] == "Bob"
