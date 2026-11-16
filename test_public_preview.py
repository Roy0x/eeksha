"""Contract test: public preview must stay a self-contained, honest static demo."""
import unittest
from pathlib import Path
from html.parser import HTMLParser


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class PublicPreviewTests(unittest.TestCase):
    def test_static_preview_has_no_server_upload_dependency(self):
        content = (Path(__file__).parent / "docs" / "index.html").read_text(encoding="utf-8")
        tags = Tags()
        tags.feed(content)
        self.assertTrue(any(tag == "canvas" for tag, _ in tags.tags))
        self.assertFalse(any(tag == "iframe" for tag, _ in tags.tags))
        self.assertFalse(any(tag == "form" for tag, _ in tags.tags))
        self.assertFalse(any(tag == "script" and attrs.get("src") for tag, attrs in tags.tags))
        self.assertFalse(any(tag == "link" and attrs.get("rel") == "stylesheet" and attrs.get("href", "").startswith("http") for tag, attrs in tags.tags))
        self.assertNotIn("fetch(", content)
        self.assertIn("SYNTHETIC DATA ONLY", content)
        self.assertIn("not AI segmentation", content)
        self.assertIn("http://127.0.0.1:8012/workspace", content)


if __name__ == "__main__":
    unittest.main()
