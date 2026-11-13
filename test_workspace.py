"""Regression checks for the Eeksha local Dataset Workspace."""
import unittest

from webapp import APP


class WorkspaceRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = APP.test_client()

    def test_workspace_responds_with_html_and_navigation(self):
        response = self.client.get("/workspace")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)
        markup = response.get_data(as_text=True)
        for route in ("/annotator", "/correct", "/review", "/process"):
            self.assertIn(route, markup)
        self.assertIn("Dataset workspace", markup)
        self.assertIn("Synthetic demo", markup)
        self.assertIn("No accuracy certification", markup)

    def test_original_processor_still_links_to_workspace(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('href="/workspace"', response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
