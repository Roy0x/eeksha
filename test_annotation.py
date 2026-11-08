import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

from annotation import build_mask, record_annotations
from webapp import APP


class AnnotationTests(unittest.TestCase):
    def test_polygon_and_unknown_pixels(self):
        mask = np.asarray(build_mask(20, 20, [
            {"class_id": 4, "vertices": [[2, 2], [10, 2], [2, 10]]}]))
        self.assertEqual(int(mask[3, 3]), 4)
        self.assertEqual(int(mask[19, 19]), 0)

    def test_invalid_polygons_rejected(self):
        for value in ([], [{"class_id": 0, "vertices": [[1, 1], [2, 1], [1, 2]]}],
                      [{"class_id": 4, "vertices": [[1, 1], [1, 1], [1, 1]]}],
                      [{"class_id": 4, "vertices": [[-1, 1], [1, 2], [2, 1]]}]):
            with self.assertRaises(ValueError):
                build_mask(10, 10, value)

    def test_record_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            data = record_annotations(Path(temp), [
                {"class_id": 5, "vertices": [[1, 1], [6, 1], [1, 6]]}], 10, 10)
            self.assertEqual(data["review_status"], "UNREVIEWED")
            self.assertGreater(data["pixel_counts"]["broccoli_leaf"], 0)

    def test_annotator_http_export(self):
        with APP.test_client() as client:
            self.assertEqual(client.get("/annotator").status_code, 200)
            rgb = io.BytesIO()
            depth = io.BytesIO()
            Image.fromarray(np.zeros((10, 10, 3), dtype=np.uint8)).save(rgb, format="PNG")
            Image.fromarray(np.full((10, 10), 800, dtype=np.uint16)).save(depth, format="PNG")
            rgb.seek(0)
            depth.seek(0)
            calibration = {
                "resolution": {"width": 10, "height": 10},
                "rgb_intrinsics": {"fx": 10, "fy": 10, "cx": 4.5, "cy": 4.5,
                                   "distortion_coefficients": [0, 0, 0, 0, 0]},
                "usage_notes": {"depth_alignment": "Depth aligned to the RGB image",
                                "coordinate_formula": "Z is depth in mm"}}
            polygons = [{"class_id": 4, "vertices": [[2, 2], [8, 2], [2, 8]]}]
            response = client.post("/annotate", data={
                "rgb": (rgb, "rgb.png"), "depth": (depth, "depth.png"),
                "calibration": (io.BytesIO(json.dumps(calibration).encode()), "camera_intrinsics.json"),
                "annotations": json.dumps(polygons)})
            self.assertEqual(response.status_code, 200, response.json)
            self.assertFalse(response.json["report"]["labels_predicted_by_ai"])
            exported = client.get("/download/" + response.json["id"])
            with zipfile.ZipFile(io.BytesIO(exported.data)) as z:
                self.assertIn("annotations.json", z.namelist())
                self.assertIn("semantic_cloud.ply", z.namelist())
                self.assertEqual(json.loads(z.read("annotations.json"))["review_status"], "UNREVIEWED")


if __name__ == "__main__":
    unittest.main()
