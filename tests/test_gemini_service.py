from unittest.mock import Mock, patch

import pytest

from main.services.gemini_service import available_models, generate_content


@patch("main.services.gemini_service.requests.get")
def test_model_list_paginates_and_filters_generation_models(mock_get):
    first = Mock(status_code=200)
    first.json.return_value = {
        "models": [
            {"name": "models/gemini-first", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-embedding", "supportedGenerationMethods": ["embedContent"]},
        ],
        "nextPageToken": "next",
    }
    second = Mock(status_code=200)
    second.json.return_value = {
        "models": [{"name": "models/gemini-second", "supportedGenerationMethods": ["generateContent"]}]
    }
    mock_get.side_effect = [first, second]

    assert available_models("fake-key") == ["gemini-first", "gemini-second"]
    assert mock_get.call_args.kwargs["params"]["pageToken"] == "next"
    assert mock_get.call_args.kwargs["allow_redirects"] is False
    first.close.assert_called_once()
    second.close.assert_called_once()


@patch("main.services.gemini_service.requests.post")
def test_gemini_does_not_follow_redirect_or_accept_incomplete_response(mock_post):
    mock_post.return_value.status_code = 302
    with pytest.raises(RuntimeError, match="unexpected redirect"):
        generate_content("fake-key", "gemini-test", [{"role": "user", "content": "Hello"}])
    mock_post.return_value.close.assert_called_once()

    mock_post.reset_mock()
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "partial"}]}}]
    }
    with pytest.raises(RuntimeError, match="could not complete"):
        generate_content("fake-key", "gemini-test", [{"role": "user", "content": "Hello"}])
    mock_post.return_value.close.assert_called_once()
