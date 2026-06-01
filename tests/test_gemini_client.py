from unittest.mock import MagicMock, patch

import pytest
from google.genai import errors as genai_errors

from gemini_client import _call_with_503_retry, generate_questions


def _make_server_error(code: int) -> genai_errors.ServerError:
    err = genai_errors.ServerError.__new__(genai_errors.ServerError)
    err.code = code
    return err


def test_call_with_503_retry_succeeds_first_try():
    fn = MagicMock(return_value="ok")
    result = _call_with_503_retry(fn, "arg1", key="val")
    assert result == "ok"
    fn.assert_called_once_with("arg1", key="val")


def test_call_with_503_retry_retries_once_on_503():
    err = _make_server_error(503)
    fn = MagicMock(side_effect=[err, "ok"])
    with patch("gemini_client.time.sleep") as mock_sleep:
        result = _call_with_503_retry(fn, "arg")
    assert result == "ok"
    mock_sleep.assert_called_once_with(60)


def test_call_with_503_retry_raises_non_503():
    err = _make_server_error(500)
    fn = MagicMock(side_effect=err)
    with pytest.raises(genai_errors.ServerError):
        _call_with_503_retry(fn)


def test_call_with_503_retry_raises_after_all_retries():
    err = _make_server_error(503)
    fn = MagicMock(side_effect=[err, err, err])
    with patch("gemini_client.time.sleep") as mock_sleep:
        with pytest.raises(genai_errors.ServerError):
            _call_with_503_retry(fn)
    assert mock_sleep.call_count == 2
    mock_sleep.assert_any_call(60)
    mock_sleep.assert_any_call(300)


def test_generate_questions_returns_parsed_dict():
    mock_response = MagicMock()
    mock_response.text = '{"mock_exam_batch": []}'

    with patch("gemini_client.genai.Client") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.models.generate_content.return_value = mock_response
        with patch("gemini_client._call_with_503_retry") as mock_retry:
            mock_retry.side_effect = lambda fn, *args, **kwargs: fn(*args, **kwargs)
            result = generate_questions("prompt text", "fake-api-key", "gemini-2.5-pro")

    assert result == {"mock_exam_batch": []}
    MockClient.assert_called_once_with(api_key="fake-api-key")


def test_generate_questions_raises_on_empty_response():
    mock_response = MagicMock()
    mock_response.text = None

    with patch("gemini_client.genai.Client") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.models.generate_content.return_value = mock_response
        with patch("gemini_client._call_with_503_retry") as mock_retry:
            mock_retry.side_effect = lambda fn, *args, **kwargs: fn(*args, **kwargs)
            with pytest.raises(ValueError, match="Empty response"):
                generate_questions("prompt", "key", "model")


def test_generate_questions_raises_on_invalid_json():
    mock_response = MagicMock()
    mock_response.text = "not valid json"

    with patch("gemini_client.genai.Client") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.models.generate_content.return_value = mock_response
        with patch("gemini_client._call_with_503_retry") as mock_retry:
            mock_retry.side_effect = lambda fn, *args, **kwargs: fn(*args, **kwargs)
            with pytest.raises(ValueError, match="non-JSON"):
                generate_questions("prompt", "key", "model")
