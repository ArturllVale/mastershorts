import os
import shutil
import asyncio
import unittest
from unittest.mock import patch, MagicMock

import httpx

# Mock environment before importing config
os.environ["SHARED_OUTPUT_DIR"] = "/mock/shared/output"
import core.config
core.config.OUTPUT_DIR = "/mock/shared/output"

from services.renderer import call_render_service

class TestRenderFileContract(unittest.IsolatedAsyncioTestCase):
    @patch("httpx.AsyncClient")
    async def test_single_render_success_relative_path(self, mock_client_cls):
        """Testa o contrato de resolução de caminhos relativos de um render."""
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        
        mock_post = MagicMock()
        mock_post.json.return_value = {"renderId": "uuid-1"}
        mock_post.raise_for_status = MagicMock()
        
        mock_get = MagicMock()
        mock_get.json.return_value = {"status": "done", "outputUrl": "job123/remotion_0_uuid-1.mp4"}
        mock_get.raise_for_status = MagicMock()
        
        mock_client.post.return_value = mock_post
        mock_client.get.return_value = mock_get
        
        url = await call_render_service("job123", 0, "vid.mp4", 100, 30, 1080, 1920, {})
        expected_path = os.path.normpath(os.path.join("/mock/shared/output", "job123/remotion_0_uuid-1.mp4"))
        self.assertEqual(url, expected_path)

    @patch("httpx.AsyncClient")
    async def test_simultaneous_renders(self, mock_client_cls):
        """Dois renders concorrentes não devem se chocar pois seus outputUrls mockados diferem."""
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        
        mock_post1, mock_post2 = MagicMock(), MagicMock()
        mock_post1.json.return_value = {"renderId": "uuid-1"}
        mock_post2.json.return_value = {"renderId": "uuid-2"}
        
        mock_get1, mock_get2 = MagicMock(), MagicMock()
        mock_get1.json.return_value = {"status": "done", "outputUrl": "job123/remotion_0_uuid-1.mp4"}
        mock_get2.json.return_value = {"status": "done", "outputUrl": "job123/remotion_0_uuid-2.mp4"}
        
        mock_client.post.side_effect = [mock_post1, mock_post2]
        mock_client.get.side_effect = [mock_get1, mock_get2]
        
        t1 = call_render_service("job123", 0, "vid.mp4", 100, 30, 1080, 1920, {})
        t2 = call_render_service("job123", 1, "vid2.mp4", 100, 30, 1080, 1920, {})
        
        res1, res2 = await asyncio.gather(t1, t2)
        
        self.assertNotEqual(res1, res2)
        self.assertTrue("uuid-1" in res1)
        self.assertTrue("uuid-2" in res2)

    @patch("httpx.AsyncClient")
    async def test_cleanup_on_error(self, mock_client_cls):
        """O backend propaga erro quando o renderer reporta error status."""
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        
        mock_post = MagicMock()
        mock_post.json.return_value = {"renderId": "uuid-err"}
        
        mock_get = MagicMock()
        mock_get.json.return_value = {"status": "error", "error": "Disk full"}
        
        mock_client.post.return_value = mock_post
        mock_client.get.return_value = mock_get
        
        with self.assertRaisesRegex(Exception, "Disk full"):
            await call_render_service("job123", 0, "vid.mp4", 100, 30, 1080, 1920, {})

if __name__ == '__main__':
    unittest.main()
