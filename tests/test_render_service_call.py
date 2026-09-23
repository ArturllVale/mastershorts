import asyncio
import pytest
import httpx
from unittest.mock import patch, MagicMock
from services.renderer import call_render_service

@pytest.fixture
def mock_httpx_client():
    with patch("httpx.AsyncClient") as mock_client:
        yield mock_client

def test_call_render_service_success(mock_httpx_client):
    async def _run():
        mock_post_res = MagicMock()
        mock_post_res.json.return_value = {"renderId": "123-abc"}
        mock_post_res.raise_for_status = MagicMock()

        mock_get_res = MagicMock()
        mock_get_res.json.return_value = {"status": "done", "outputUrl": "http://localhost/output.mp4"}
        mock_get_res.raise_for_status = MagicMock()

        mock_client_instance = mock_httpx_client.return_value.__aenter__.return_value
        mock_client_instance.post.return_value = mock_post_res
        mock_client_instance.get.return_value = mock_get_res

        url = await call_render_service("job-1", 0, "http://vid.mp4", 300, 30, 1080, 1920, {})
        assert url == "http://localhost/output.mp4"
        mock_client_instance.post.assert_called_once()
        mock_client_instance.get.assert_called_once()

    asyncio.run(_run())

def test_call_render_service_unavailable(mock_httpx_client):
    async def _run():
        mock_client_instance = mock_httpx_client.return_value.__aenter__.return_value
        mock_client_instance.post.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(Exception, match="unavailable"):
            await call_render_service("job-1", 0, "http://vid.mp4", 300, 30, 1080, 1920, {})

    asyncio.run(_run())

def test_call_render_service_invalid_json(mock_httpx_client):
    async def _run():
        mock_post_res = MagicMock()
        mock_post_res.json.side_effect = ValueError("Invalid JSON")
        mock_post_res.raise_for_status = MagicMock()
        
        mock_client_instance = mock_httpx_client.return_value.__aenter__.return_value
        mock_client_instance.post.return_value = mock_post_res

        with pytest.raises(Exception, match="invalid JSON"):
            await call_render_service("job-1", 0, "http://vid.mp4", 300, 30, 1080, 1920, {})

    asyncio.run(_run())

def test_call_render_service_render_error(mock_httpx_client):
    async def _run():
        mock_post_res = MagicMock()
        mock_post_res.json.return_value = {"renderId": "123-abc"}
        mock_post_res.raise_for_status = MagicMock()

        mock_get_res = MagicMock()
        mock_get_res.json.return_value = {"status": "error", "error": "Out of memory"}
        mock_get_res.raise_for_status = MagicMock()

        mock_client_instance = mock_httpx_client.return_value.__aenter__.return_value
        mock_client_instance.post.return_value = mock_post_res
        mock_client_instance.get.return_value = mock_get_res

        with pytest.raises(Exception, match="Render failed: Out of memory"):
            await call_render_service("job-1", 0, "http://vid.mp4", 300, 30, 1080, 1920, {})

    asyncio.run(_run())
