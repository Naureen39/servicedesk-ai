"""Unit tests for app.services.llm.factory: builds the process-wide LLMRouter, or returns
None when neither provider has an API key configured (Section 4.3 escalation trigger)."""

from __future__ import annotations

from app.services.llm import factory
from app.services.llm.router import LLMRouter


class _FakeProvider:
    def __init__(self, configured: bool) -> None:
        self._configured = configured

    @property
    def is_configured(self) -> bool:
        return self._configured


def test_get_router_returns_none_when_no_provider_configured(monkeypatch):
    factory.reset_router_for_testing(None)
    monkeypatch.setattr(factory, "GroqProvider", lambda: _FakeProvider(False))
    monkeypatch.setattr(factory, "GeminiProvider", lambda: _FakeProvider(False))

    assert factory.get_router() is None
    factory.reset_router_for_testing(None)


def test_get_router_builds_router_when_a_provider_is_configured(monkeypatch):
    factory.reset_router_for_testing(None)
    monkeypatch.setattr(factory, "GroqProvider", lambda: _FakeProvider(True))
    monkeypatch.setattr(factory, "GeminiProvider", lambda: _FakeProvider(False))

    router = factory.get_router()
    assert isinstance(router, LLMRouter)
    factory.reset_router_for_testing(None)


def test_get_router_caches_the_singleton(monkeypatch):
    factory.reset_router_for_testing(None)
    monkeypatch.setattr(factory, "GroqProvider", lambda: _FakeProvider(True))
    monkeypatch.setattr(factory, "GeminiProvider", lambda: _FakeProvider(True))

    first = factory.get_router()
    second = factory.get_router()
    assert first is second
    factory.reset_router_for_testing(None)


def test_reset_router_for_testing_replaces_the_singleton():
    sentinel = object()
    factory.reset_router_for_testing(sentinel)
    assert factory.get_router() is sentinel
    factory.reset_router_for_testing(None)
