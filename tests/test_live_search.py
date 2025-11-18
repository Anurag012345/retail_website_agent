from __future__ import annotations

import os

import pytest

from tavily_demo.client import TavilyTester


@pytest.mark.skipif(not os.getenv("TAVILY_API_KEY"), reason="TAVILY_API_KEY not configured")
def test_live_search_returns_results():
    tester = TavilyTester.build()
    response = tester.search("latest retail AI news", max_results=1)
    assert response["results"], "Expected at least one Tavily result"
