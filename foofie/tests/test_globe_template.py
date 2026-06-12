import unittest

from fastapi.testclient import TestClient

from foofie.main import app


class GlobeTemplateTests(unittest.TestCase):
    def test_globe_uses_cesium_stack(self):
        response = TestClient(app).get("/globe")

        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("Cesium.js", html)
        self.assertIn("new Cesium.Viewer", html)
        self.assertIn("imageryLayers", html)
        self.assertIn("/api/records", html)
        self.assertIn("const FLY_TO_HEIGHT = 1200", html)
        self.assertIn("minimumZoomDistance = 200", html)
        self.assertNotIn("maplibre-gl", html.lower())
        self.assertNotIn("three.min.js", html.lower())


if __name__ == "__main__":
    unittest.main()
