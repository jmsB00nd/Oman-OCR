"""Tests for OCR pipeline functions."""

import base64
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestProcessImageWithVision:
    """Tests for the vision processing pipeline."""

    def test_process_image_encodes_base64(self, sample_image, mock_vision_response):
        """Test that image is properly encoded to base64."""
        with patch("main.requests.post") as mock_post:
            mock_post.return_value.json.return_value = mock_vision_response
            mock_post.return_value.raise_for_status = MagicMock()

            from ui import process_image_with_vision

            result = process_image_with_vision(sample_image)

            # Verify the call was made
            mock_post.assert_called_once()

            # Verify base64 encoding in the request
            call_args = mock_post.call_args
            messages = call_args.kwargs["json"]["messages"]
            content = messages[0]["content"]

            # Find the image_url content
            image_content = next(c for c in content if c["type"] == "image_url")
            assert "base64," in image_content["image_url"]["url"]

    def test_process_image_returns_extracted_text(self, sample_image, mock_vision_response):
        """Test that vision processing returns the extracted text."""
        with patch("main.requests.post") as mock_post:
            mock_post.return_value.json.return_value = mock_vision_response
            mock_post.return_value.raise_for_status = MagicMock()

            from ui import process_image_with_vision

            result = process_image_with_vision(sample_image)

            assert result == "السلام عليكم ورحمة الله وبركاته"

    def test_process_image_uses_correct_url(self, sample_image, mock_vision_response, monkeypatch):
        """Test that vision processing uses the configured URL."""
        test_url = "http://test-vision:9000/v1/chat/completions"
        monkeypatch.setattr("main.VISION_URL", test_url)

        with patch("main.requests.post") as mock_post:
            mock_post.return_value.json.return_value = mock_vision_response
            mock_post.return_value.raise_for_status = MagicMock()

            from ui import process_image_with_vision

            process_image_with_vision(sample_image)

            mock_post.assert_called_once()
            assert mock_post.call_args.args[0] == test_url

    def test_process_image_sets_timeout(self, sample_image, mock_vision_response):
        """Test that vision processing sets appropriate timeout."""
        with patch("main.requests.post") as mock_post:
            mock_post.return_value.json.return_value = mock_vision_response
            mock_post.return_value.raise_for_status = MagicMock()

            from ui import process_image_with_vision

            process_image_with_vision(sample_image)

            call_args = mock_post.call_args
            assert call_args.kwargs["timeout"] == 120

    def test_process_image_raises_on_http_error(self, sample_image):
        """Test that HTTP errors are propagated."""
        with patch("main.requests.post") as mock_post:
            mock_post.return_value.raise_for_status.side_effect = requests.HTTPError(
                "500 Server Error"
            )

            from ui import process_image_with_vision

            with pytest.raises(requests.HTTPError):
                process_image_with_vision(sample_image)

    def test_process_image_handles_connection_error(self, sample_image):
        """Test handling of connection errors."""
        with patch("main.requests.post") as mock_post:
            mock_post.side_effect = requests.ConnectionError("Connection refused")

            from ui import process_image_with_vision

            with pytest.raises(requests.ConnectionError):
                process_image_with_vision(sample_image)


class TestCorrectTextWithLLM:
    """Tests for the text correction pipeline."""

    def test_correct_text_sends_raw_text(self, mock_text_response):
        """Test that raw text is sent to the correction model."""
        with patch("main.requests.post") as mock_post:
            mock_post.return_value.json.return_value = mock_text_response
            mock_post.return_value.raise_for_status = MagicMock()

            from ui import correct_text_with_llm

            raw_text = "السلام علیکم"
            correct_text_with_llm(raw_text)

            call_args = mock_post.call_args
            messages = call_args.kwargs["json"]["messages"]
            assert raw_text in messages[0]["content"]

    def test_correct_text_returns_corrected_text(self, mock_text_response):
        """Test that text correction returns the corrected text."""
        with patch("main.requests.post") as mock_post:
            mock_post.return_value.json.return_value = mock_text_response
            mock_post.return_value.raise_for_status = MagicMock()

            from ui import correct_text_with_llm

            result = correct_text_with_llm("السلام علیکم")

            assert result == "السلام عليكم ورحمة الله وبركاته"

    def test_correct_text_uses_correct_url(self, mock_text_response, monkeypatch):
        """Test that text correction uses the configured URL."""
        test_url = "http://test-text:9001/v1/chat/completions"
        monkeypatch.setattr("main.TEXT_URL", test_url)

        with patch("main.requests.post") as mock_post:
            mock_post.return_value.json.return_value = mock_text_response
            mock_post.return_value.raise_for_status = MagicMock()

            from ui import correct_text_with_llm

            correct_text_with_llm("test text")

            assert mock_post.call_args.args[0] == test_url

    def test_correct_text_sets_timeout(self, mock_text_response):
        """Test that text correction sets appropriate timeout."""
        with patch("main.requests.post") as mock_post:
            mock_post.return_value.json.return_value = mock_text_response
            mock_post.return_value.raise_for_status = MagicMock()

            from ui import correct_text_with_llm

            correct_text_with_llm("test text")

            call_args = mock_post.call_args
            assert call_args.kwargs["timeout"] == 60

    def test_correct_text_raises_on_http_error(self):
        """Test that HTTP errors are propagated."""
        with patch("main.requests.post") as mock_post:
            mock_post.return_value.raise_for_status.side_effect = requests.HTTPError(
                "500 Server Error"
            )

            from ui import correct_text_with_llm

            with pytest.raises(requests.HTTPError):
                correct_text_with_llm("test text")

    def test_correct_text_handles_empty_input(self, mock_text_response):
        """Test handling of empty input text."""
        with patch("main.requests.post") as mock_post:
            mock_post.return_value.json.return_value = mock_text_response
            mock_post.return_value.raise_for_status = MagicMock()

            from ui import correct_text_with_llm

            # Should not raise, just process normally
            result = correct_text_with_llm("")

            assert result is not None


class TestFullPipeline:
    """Integration tests for the full OCR pipeline."""

    def test_full_pipeline_vision_to_correction(
        self, sample_image, mock_vision_response, mock_text_response
    ):
        """Test the full pipeline from image to corrected text."""
        with patch("main.requests.post") as mock_post:
            # Configure mock to return different responses based on URL
            def side_effect(*args, **kwargs):
                mock_response = MagicMock()
                mock_response.raise_for_status = MagicMock()

                if "vision" in args[0].lower() or "8000" in args[0]:
                    mock_response.json.return_value = mock_vision_response
                else:
                    mock_response.json.return_value = mock_text_response

                return mock_response

            mock_post.side_effect = side_effect

            from ui import correct_text_with_llm, process_image_with_vision

            # Run pipeline
            raw_text = process_image_with_vision(sample_image)
            corrected_text = correct_text_with_llm(raw_text)

            # Verify results
            assert raw_text == "السلام عليكم ورحمة الله وبركاته"
            assert corrected_text == "السلام عليكم ورحمة الله وبركاته"

            # Verify both APIs were called
            assert mock_post.call_count == 2

    def test_pipeline_preserves_arabic_text(
        self, sample_image, mock_vision_response, mock_text_response
    ):
        """Test that Arabic text is preserved through the pipeline."""
        arabic_text = "بسم الله الرحمن الرحيم"
        custom_vision_response = {
            "choices": [{"message": {"content": arabic_text}}]
        }
        custom_text_response = {
            "choices": [{"message": {"content": arabic_text}}]
        }

        with patch("main.requests.post") as mock_post:
            def side_effect(*args, **kwargs):
                mock_response = MagicMock()
                mock_response.raise_for_status = MagicMock()

                if "vision" in args[0].lower() or "8000" in args[0]:
                    mock_response.json.return_value = custom_vision_response
                else:
                    mock_response.json.return_value = custom_text_response

                return mock_response

            mock_post.side_effect = side_effect

            from ui import correct_text_with_llm, process_image_with_vision

            raw_text = process_image_with_vision(sample_image)
            corrected_text = correct_text_with_llm(raw_text)

            # Verify Arabic text is preserved
            assert raw_text == arabic_text
            assert corrected_text == arabic_text


class TestRequestPayloads:
    """Tests for API request payload structure."""

    def test_vision_payload_structure(self, sample_image, mock_vision_response):
        """Test the structure of vision API request payload."""
        with patch("main.requests.post") as mock_post:
            mock_post.return_value.json.return_value = mock_vision_response
            mock_post.return_value.raise_for_status = MagicMock()

            from ui import process_image_with_vision

            process_image_with_vision(sample_image)

            call_args = mock_post.call_args
            payload = call_args.kwargs["json"]

            # Verify payload structure
            assert "model" in payload
            assert "messages" in payload
            assert len(payload["messages"]) == 1

            message = payload["messages"][0]
            assert message["role"] == "user"
            assert isinstance(message["content"], list)

            # Verify content types
            content_types = [c["type"] for c in message["content"]]
            assert "text" in content_types
            assert "image_url" in content_types

    def test_text_payload_structure(self, mock_text_response):
        """Test the structure of text correction API request payload."""
        with patch("main.requests.post") as mock_post:
            mock_post.return_value.json.return_value = mock_text_response
            mock_post.return_value.raise_for_status = MagicMock()

            from ui import correct_text_with_llm

            correct_text_with_llm("test text")

            call_args = mock_post.call_args
            payload = call_args.kwargs["json"]

            # Verify payload structure
            assert "model" in payload
            assert "messages" in payload
            assert len(payload["messages"]) == 1

            message = payload["messages"][0]
            assert message["role"] == "user"
            assert isinstance(message["content"], str)
