import unittest

from fastapi.testclient import TestClient

from foofie.main import app


class UiShellTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_base_pages_use_refined_visual_shell(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("app-shell", html)
        self.assertIn("/static/css/style.css?v=", html)
        self.assertIn("view-toolbar", html)
        self.assertIn("lucide", html)

    def test_add_page_uses_form_panel(self):
        response = self.client.get("/add")

        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("form-panel", html)
        self.assertIn("location-panel", html)

    def test_globe_page_uses_refined_overlay_controls(self):
        response = self.client.get("/globe")

        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("globe-control-shell", html)
        self.assertIn("layer-panel", html)


if __name__ == "__main__":
    unittest.main()
