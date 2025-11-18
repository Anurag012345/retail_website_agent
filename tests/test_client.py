from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tavily_demo import client as client_module
from tavily_demo.client import TavilyTester


def test_search_requires_query():
    tester = TavilyTester(settings=client_module.Settings(api_key="fake"), client=MagicMock())
    with pytest.raises(ValueError):
        tester.search("")


def test_extract_requires_urls():
    tester = TavilyTester(settings=client_module.Settings(api_key="fake"), client=MagicMock())
    with pytest.raises(ValueError):
        tester.extract_urls([])


def test_extract_builds_summaries():
    mock_client = MagicMock()
    mock_client.extract.return_value = {
        "results": [
            {
                "url": "https://example.com",
                "title": "Title",
                "content": "Sentence one. Sentence two. Sentence three.",
            }
        ],
        "failed_results": [],
    }
    tester = TavilyTester(settings=client_module.Settings(api_key="fake"), client=mock_client)

    response = tester.extract_urls(["https://example.com"])

    mock_client.extract.assert_called_once_with(
        urls=["https://example.com"], extract_depth="advanced", format="markdown"
    )
    assert response["summaries"][0]["summary"].startswith("Sentence one")


def test_build_uses_settings_and_client():
    with patch.object(
        client_module, "load_settings", return_value=client_module.Settings(api_key="live")
    ) as mock_settings, patch.object(client_module, "TavilyClient", return_value=MagicMock()) as mock_client:
        tester = TavilyTester.build()

    mock_settings.assert_called_once()
    mock_client.assert_called_once_with(api_key="live")
    assert tester.settings.api_key == "live"
