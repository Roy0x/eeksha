import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image
import numpy as np

from real_field_demo import convert_intrinsics, run


class TestRealFieldDemo(unittest.TestCase):
    def metadata(self, root):
        source = root / "camera_intrinsics.json"
        source.write_text(json.dumps({
            "resolution": {"width": 4, "height": 3},
            "rgb_intrinsics": {"fx": 3, "fy": 3, "cx": 1.5, "cy": 1,
                               "distortion_coefficients": [0, 0, 0, 0, 0]},
            "usage_notes": {"depth_alignment": "Depth aligned to the RGB image",
                            "coordinate_formula": "X and Y are derived from Z is depth in mm"}
        }), encoding="utf-8")
        return source

    def test_import_preserves_unknown_labels(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.metadata(root)
            Image.fromarray(np.full((3, 4, 3), 120, np.uint8)).save(root / "day_rgb_0001.png")
            Image.fromarray(np.array([[0, 800, 900, 1000]] * 3, np.uint16)).save(root / "day_depth_0001.png")
            report = run(root, root / "out")
            self.assertEqual(report["semantic_status"], "UNLABELED_ALL_UNKNOWN")
            self.assertEqual(report["processed_pairs"][0]["points"], 9)
            self.assertEqual(report["processed_pairs"][0]["valid_depth_coverage"], 0.75)
            qa = json.loads((root / "out/0001/qa_report.json").read_text())
            self.assertEqual(qa["class_counts"]["unknown"], 9)
            self.assertEqual(qa["class_counts"]["crop"], 0)

    def test_missing_alignment_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.metadata(root)
            data = json.loads(source.read_text())
            data["usage_notes"]["depth_alignment"] = "unclear"
            source.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                convert_intrinsics(source, root / "calibration.json")


if __name__ == "__main__":
    unittest.main()
