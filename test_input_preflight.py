"""Tests for read-only input preflight and its local Flask endpoint."""
import io
import json
import unittest

import numpy as np
from PIL import Image

from input_preflight import inspect_inputs
from webapp import APP


def png(array):
    out = io.BytesIO()
    Image.fromarray(array).save(out, format="PNG")
    return out.getvalue()


def example():
    rgb = png(np.zeros((8, 12, 3), dtype=np.uint8))
    depth = png(np.full((8, 12), 1200, dtype=np.uint16))
    labels = png(np.full((8, 12), 2, dtype=np.uint8))
    calibration = json.dumps(dict(fx=100, fy=100, cx=6, cy=4, depth_scale=0.001,
                                  depth_type="axial_z", width=12, height=8)).encode()
    return rgb, depth, labels, calibration


class PreflightTests(unittest.TestCase):
    def test_valid_input_is_structural_only(self):
        result = inspect_inputs(*example())
        self.assertTrue(result["ready"])
        self.assertEqual((result["width"], result["height"]), (12, 8))
        self.assertEqual(result["status"], "STRUCTURAL_INPUT_CHECK_ONLY")
        self.assertTrue(result["warnings"])

    def test_reject_mismatched_dimensions(self):
        rgb, depth, labels, config = example()
        with self.assertRaisesRegex(ValueError, "mismatched dimensions"):
            inspect_inputs(rgb, depth, png(np.ones((4, 12), dtype=np.uint8)), config)

    def test_reject_missing_depth_type(self):
        rgb, depth, labels, config = example()
        cfg = json.loads(config)
        del cfg["depth_type"]
        with self.assertRaisesRegex(ValueError, "depth_type"):
            inspect_inputs(rgb, depth, labels, json.dumps(cfg).encode())

    def test_reject_invalid_label_classes(self):
        rgb, depth, _, config = example()
        with self.assertRaisesRegex(ValueError, "unsupported class IDs"):
            inspect_inputs(rgb, depth, png(np.full((8, 12), 99, dtype=np.uint8)), config)

    def test_preflight_endpoint_accepts_valid_fields(self):
        rgb, depth, labels, cfg = example()
        response = APP.test_client().post("/preflight", data={
            "rgb": (io.BytesIO(rgb), "rgb.png"),
            "depth": (io.BytesIO(depth), "depth.png"),
            "labels": (io.BytesIO(labels), "labels.png"),
            "calibration": (io.BytesIO(cfg), "calibration.json"),
        }, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ready"])

    def test_preflight_endpoint_rejects_missing_files(self):
        response = APP.test_client().post("/preflight", data={})
        self.assertEqual(response.status_code, 400)

    def test_workspace_exposes_preflight_action(self):
        response = APP.test_client().get("/workspace")
        self.assertEqual(response.status_code, 200)
        text = response.get_data(as_text=True)
        self.assertIn("Check input readiness", text)
        self.assertIn("'/preflight'", text)


if __name__ == "__main__":
    unittest.main()
