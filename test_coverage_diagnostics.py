"""Coverage classification regression tests, including real export count consistency."""
import io
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from coverage_diagnostics import summarize_coverage
from eeksha import make_demo, process
from webapp import APP


class CoverageDiagnosticsTests(unittest.TestCase):
    def test_separates_invalid_depth_from_unknown_labels(self):
        depth = np.array([[0, 1000, 6000], [1000, 1000, 1000]], dtype=np.uint16)
        labels = np.array([[4, 0, 4], [4, 0, 0]], dtype=np.uint8)
        c = summarize_coverage(depth, labels, 0.001, 5)
        self.assertEqual(c["total_image_pixels"], 6)
        self.assertEqual(c["valid_depth_pixels"], 4)
        self.assertEqual(c["missing_or_nonpositive_depth_pixels"], 1)
        self.assertEqual(c["over_max_depth_pixels"], 1)
        self.assertEqual(c["labeled_valid_depth_points"], 1)
        self.assertEqual(c["unknown_valid_depth_points"], 3)
        self.assertAlmostEqual(c["labeled_valid_depth_fraction"], 0.25)
        self.assertIn("LOW_SEMANTIC_COVERAGE_UNDER_50_PERCENT_OF_VALID_DEPTH", c["flags"])

    def test_no_depth_returns_zero_fractions(self):
        depth = np.zeros((2, 2), dtype=np.uint16)
        labels = np.zeros((2, 2), dtype=np.uint8)
        c = summarize_coverage(depth, labels, .001, 5)
        self.assertEqual(c["labeled_valid_depth_fraction"], 0)
        self.assertIn("LOW_DEPTH_COVERAGE_UNDER_50_PERCENT", c["flags"])

    def test_synthetic_processor_exports_diagnostics(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            make_demo(root)
            qa = process(root / "rgb.png", root / "depth.png", root / "labels.png",
                         root / "calibration.json", root / "out")
            c = qa["coverage_diagnostics"]
            self.assertEqual(c["valid_depth_pixels"], qa["points"])
            self.assertEqual(c["unknown_valid_depth_points"] + c["labeled_valid_depth_points"], qa["points"])
            self.assertEqual(sum(qa["class_counts"].values()), qa["points"])
            on_disk = json.loads((root / "out" / "qa_report.json").read_text())
            self.assertEqual(on_disk["coverage_diagnostics"], c)

    def test_workspace_displays_new_qa_fields(self):
        html = APP.test_client().get("/workspace").get_data(as_text=True)
        self.assertIn('id="coverage-details"', html)
        self.assertIn("labeled_valid_depth_fraction", html)
        self.assertIn("nonpositive", html)


if __name__ == "__main__":
    unittest.main()
