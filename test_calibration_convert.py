"""API regression tests for source camera metadata normalization."""
import io
import json
import unittest

from webapp import APP


def metadata():
    return {
        "usage_notes": {
            "depth_alignment": "Depth is aligned to the RGB image",
            "coordinate_formula": "Z is depth in mm",
        },
        "resolution": {"width": 640, "height": 480},
        "rgb_intrinsics": {
            "fx": 612.3895263671875,
            "fy": 611.5398559570312,
            "cx": 331.8401794433594,
            "cy": 252.8849639892578,
            "distortion_coefficients": [0, 0, 0, 0, 0],
        },
    }


class CalibrationConvertTests(unittest.TestCase):
    def send(self, value):
        return APP.test_client().post(
            "/calibration/convert",
            data={"calibration": (io.BytesIO(json.dumps(value).encode()), "camera_intrinsics.json")},
            content_type="multipart/form-data",
        )

    def test_published_metadata_conversion_preserves_intrinsics(self):
        response = self.send(metadata())
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        converted = result["calibration"]
        self.assertEqual(converted["fx"], metadata()["rgb_intrinsics"]["fx"])
        self.assertEqual(converted["fy"], metadata()["rgb_intrinsics"]["fy"])
        self.assertEqual((converted["width"], converted["height"]), (640, 480))
        self.assertEqual(converted["depth_scale"], 0.001)
        self.assertEqual(converted["depth_type"], "axial_z")
        self.assertIn("not independently", result["warning"])

    def test_rejects_unverified_alignment(self):
        value = metadata()
        value["usage_notes"]["depth_alignment"] = "unknown"
        response = self.send(value)
        self.assertEqual(response.status_code, 422)

    def test_rejects_nonzero_distortion(self):
        value = metadata()
        value["rgb_intrinsics"]["distortion_coefficients"] = [0.1]
        response = self.send(value)
        self.assertEqual(response.status_code, 422)

    def test_rejects_nonpositive_focal_length(self):
        value = metadata()
        value["rgb_intrinsics"]["fx"] = -1
        response = self.send(value)
        self.assertEqual(response.status_code, 422)

    def test_requires_calibration(self):
        response = APP.test_client().post("/calibration/convert", data={})
        self.assertEqual(response.status_code, 400)

    def test_workspace_shows_conversion_action(self):
        html = APP.test_client().get("/workspace").get_data(as_text=True)
        self.assertIn("Convert source camera_intrinsics.json", html)
        self.assertIn("/calibration/convert", html)
        self.assertIn("sceneData()", html)


if __name__ == "__main__":
    unittest.main()
