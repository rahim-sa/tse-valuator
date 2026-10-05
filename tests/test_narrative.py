from unittest.mock import MagicMock, patch

import pytest

from tse_valuator.llm.client import MissingApiKeyError, get_client
from tse_valuator.llm.narrative import generate_qualitative_narrative


def test_get_client_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(MissingApiKeyError):
        get_client()


def test_get_client_succeeds_with_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key-for-testing")
    client = get_client()
    assert client is not None


def test_generate_narrative_includes_context_data_in_prompt(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key-for-testing")

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Mocked narrative response."

    with patch("tse_valuator.llm.narrative.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = generate_qualitative_narrative({"revenue_growth_pct": 73.4, "symbol": "شپدیس"})

        assert result == "Mocked narrative response."

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        user_content = call_kwargs["messages"][1]["content"]
        assert "73.4" in user_content
        assert "شپدیس" in user_content