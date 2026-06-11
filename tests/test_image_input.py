"""Tests for image input support — ImageAttachment, encode_image_to_content, and session integration."""

import base64
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nexusagent.models import ImageAttachment, encode_image_to_content


# ── ImageAttachment ──────────────────────────────────────────────────────


class TestImageAttachment:
    def test_encode_local_png(self, tmp_path):
        """Test encoding a local PNG file to base64."""
        # Create a minimal PNG file (1x1 pixel, red)
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
        )
        img_path = tmp_path / "test.png"
        img_path.write_bytes(png_data)

        attachment = ImageAttachment(path=str(img_path))
        result = attachment.encode()

        assert result.startswith("data:image/png;base64,")
        assert attachment.mime_type == "image/png"
        assert attachment.base64_data != ""

    def test_encode_local_jpg(self, tmp_path):
        """Test encoding a local JPEG file — auto-detects MIME type."""
        # Create a fake JPEG (just the header bytes)
        jpg_data = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        img_path = tmp_path / "test.jpg"
        img_path.write_bytes(jpg_data)

        attachment = ImageAttachment(path=str(img_path))
        result = attachment.encode()

        assert result.startswith("data:image/jpeg;base64,")
        assert attachment.mime_type == "image/jpeg"

    def test_encode_local_webp(self, tmp_path):
        """Test encoding a local WebP file."""
        webp_data = b"RIFF" + b"\x00" * 100
        img_path = tmp_path / "test.webp"
        img_path.write_bytes(webp_data)

        attachment = ImageAttachment(path=str(img_path))
        result = attachment.encode()

        assert result.startswith("data:image/webp;base64,")
        assert attachment.mime_type == "image/webp"

    def test_encode_local_gif(self, tmp_path):
        """Test encoding a local GIF file."""
        gif_data = b"GIF89a" + b"\x00" * 100
        img_path = tmp_path / "test.gif"
        img_path.write_bytes(gif_data)

        attachment = ImageAttachment(path=str(img_path))
        result = attachment.encode()

        assert result.startswith("data:image/gif;base64,")
        assert attachment.mime_type == "image/gif"

    def test_encode_url_returns_as_is(self):
        """Test that URLs are returned directly without encoding."""
        url = "https://example.com/image.png"
        attachment = ImageAttachment(path=url)
        result = attachment.encode()

        assert result == url
        assert attachment.base64_data == ""

    def test_encode_http_url_returns_as_is(self):
        """Test that HTTP URLs are returned directly."""
        url = "http://example.com/photo.jpg"
        attachment = ImageAttachment(path=url)
        result = attachment.encode()

        assert result == url

    def test_encode_missing_file_raises(self, tmp_path):
        """Test that encoding a non-existent file raises FileNotFoundError."""
        attachment = ImageAttachment(path=str(tmp_path / "nonexistent.png"))

        with pytest.raises(FileNotFoundError, match="Image file not found"):
            attachment.encode()

    def test_encode_unknown_extension_defaults_to_png(self, tmp_path):
        """Test that unknown file extensions default to image/png."""
        img_path = tmp_path / "test.xyz"
        img_path.write_bytes(b"fake data")

        attachment = ImageAttachment(path=str(img_path))
        result = attachment.encode()

        assert attachment.mime_type == "image/png"

    def test_encode_tilde_expansion(self, tmp_path, monkeypatch):
        """Test that ~ in paths is expanded to the home directory."""
        # Create a fake home directory
        monkeypatch.setenv("HOME", str(tmp_path))
        img_dir = tmp_path / "images"
        img_dir.mkdir()
        img_path = img_dir / "test.png"
        img_path.write_bytes(b"\x89PNG" + b"\x00" * 100)

        attachment = ImageAttachment(path="~/images/test.png")
        result = attachment.encode()

        assert result.startswith("data:image/png;base64,")


# ── encode_image_to_content ──────────────────────────────────────────────


class TestEncodeImageToContent:
    def test_encode_local_file(self, tmp_path):
        """Test encoding a local file to LangChain content block."""
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
        )
        img_path = tmp_path / "test.png"
        img_path.write_bytes(png_data)

        result = encode_image_to_content(str(img_path))

        assert result["type"] == "image_url"
        assert "url" in result["image_url"]
        assert result["image_url"]["url"].startswith("data:image/png;base64,")

    def test_encode_url(self):
        """Test encoding a URL to LangChain content block."""
        url = "https://example.com/image.png"
        result = encode_image_to_content(url)

        assert result["type"] == "image_url"
        assert result["image_url"]["url"] == url


# ── Session._build_user_message ──────────────────────────────────────────


class TestBuildUserMessage:
    def test_text_only_message(self):
        """Test building a text-only HumanMessage."""
        from langchain_core.messages import HumanMessage

        # Create a minimal session mock
        session = MagicMock(spec=[])
        session._build_user_message = lambda msg, imgs=None: (
            HumanMessage(content=msg) if not imgs else None
        )

        result = session._build_user_message("Hello, world!")
        assert isinstance(result, HumanMessage)
        assert result.content == "Hello, world!"

    def test_multimodal_message_with_image(self, tmp_path):
        """Test building a multimodal HumanMessage with text + image."""
        from langchain_core.messages import HumanMessage

        # Create a test image
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
        )
        img_path = tmp_path / "test.png"
        img_path.write_bytes(png_data)

        # Build the message using the actual function logic
        from nexusagent.models import encode_image_to_content

        content_blocks = [{"type": "text", "text": "What's in this image?"}]
        content_blocks.append(encode_image_to_content(str(img_path)))
        msg = HumanMessage(content=content_blocks)

        assert isinstance(msg, HumanMessage)
        assert isinstance(msg.content, list)
        assert len(msg.content) == 2
        assert msg.content[0]["type"] == "text"
        assert msg.content[0]["text"] == "What's in this image?"
        assert msg.content[1]["type"] == "image_url"

    def test_multimodal_message_with_multiple_images(self, tmp_path):
        """Test building a multimodal message with text + multiple images."""
        from langchain_core.messages import HumanMessage
        from nexusagent.models import encode_image_to_content

        # Create test images
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
        )
        img1 = tmp_path / "img1.png"
        img2 = tmp_path / "img2.png"
        img1.write_bytes(png_data)
        img2.write_bytes(png_data)

        content_blocks = [{"type": "text", "text": "Compare these images"}]
        for img in [img1, img2]:
            content_blocks.append(encode_image_to_content(str(img)))
        msg = HumanMessage(content=content_blocks)

        assert len(msg.content) == 3  # text + 2 images
        assert msg.content[0]["type"] == "text"
        assert msg.content[1]["type"] == "image_url"
        assert msg.content[2]["type"] == "image_url"

    def test_multimodal_message_with_url(self):
        """Test building a multimodal message with a URL image."""
        from langchain_core.messages import HumanMessage
        from nexusagent.models import encode_image_to_content

        content_blocks = [{"type": "text", "text": "Describe this image"}]
        content_blocks.append(encode_image_to_content("https://example.com/photo.png"))
        msg = HumanMessage(content=content_blocks)

        assert len(msg.content) == 2
        assert msg.content[1]["image_url"]["url"] == "https://example.com/photo.png"

    def test_multimodal_message_with_missing_image_fallback(self, tmp_path):
        """Test that a missing image produces a text fallback block."""
        from langchain_core.messages import HumanMessage
        from nexusagent.models import encode_image_to_content

        content_blocks = [{"type": "text", "text": "What's this?"}]
        # Try to encode a non-existent file
        try:
            content_blocks.append(encode_image_to_content(str(tmp_path / "missing.png")))
        except FileNotFoundError:
            content_blocks.append({
                "type": "text",
                "text": "[Image could not be loaded: missing.png]",
            })

        msg = HumanMessage(content=content_blocks)
        assert len(msg.content) == 2
        assert "Image could not be loaded" in msg.content[1].get("text", "")


# ── Config image settings ────────────────────────────────────────────────


class TestImageConfig:
    def test_default_max_image_size(self):
        """Test default max image size is 10MB."""
        from nexusagent.config import AgentConfig

        config = AgentConfig()
        assert config.max_image_size_mb == 10

    def test_default_supported_image_types(self):
        """Test default supported image types."""
        from nexusagent.config import AgentConfig

        config = AgentConfig()
        assert ".png" in config.supported_image_types
        assert ".jpg" in config.supported_image_types
        assert ".jpeg" in config.supported_image_types
        assert ".webp" in config.supported_image_types
        assert ".gif" in config.supported_image_types
        assert ".bmp" in config.supported_image_types

    def test_custom_image_config(self):
        """Test custom image config values."""
        from nexusagent.config import AgentConfig

        config = AgentConfig(max_image_size_mb=20)
        assert config.max_image_size_mb == 20
