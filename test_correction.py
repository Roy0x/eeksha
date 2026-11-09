import hashlib
import io
import json
import unittest
import zipfile

import numpy as np
from PIL import Image

from correction import correct_mask
from correction_quality import summarize_correction
from test_review import make_export
from webapp import APP


class CorrectionTests(unittest.TestCase):
    polygon = [{"class_id": 4, "vertices": [[2, 2], [10, 2], [2, 10]]}]

    def test_brush_and_eraser_provenance(self):
        original = make_export(self.polygon)
        strokes = [{"class_id": 0, "radius": 2, "points": [[3, 3]]},
                   {"class_id": 4, "radius": 2, "points": [[16, 16], [17, 17]]}]
        corrected, audit, _ = correct_mask(original, strokes, "human-01")
        labels = np.asarray(corrected)
        self.assertEqual(int(labels[3, 3]), 0)
        self.assertEqual(int(labels[16, 16]), 4)
        self.assertEqual(audit["review_status"], "HUMAN_REVIEWED_NOT_GROUND_TRUTH")
        self.assertFalse(audit["ground_truth_verified"])
        self.assertEqual(audit["original_annotation_sha256"], hashlib.sha256(original).hexdigest())

    def test_invalid_stroke_rejected(self):
        original = make_export(self.polygon)
        for stroke in ({"class_id": 4, "radius": 101, "points": [[3, 3]]},
                       {"class_id": 4, "radius": 2, "points": [[999, 3]]},
                       {"class_id": 99, "radius": 2, "points": [[3, 3]]}):
            with self.assertRaises(ValueError):
                correct_mask(original, [stroke], "human-01")

    def test_quality_counts_valid_and_missing_depth(self):
        before = np.array([[4, 4, 0], [0, 0, 0]], dtype=np.uint8)
        after = Image.fromarray(np.array([[4, 0, 4], [0, 0, 0]], dtype=np.uint8))
        depth = np.array([[800, 0, 900], [0, 0, 0]], dtype=np.uint16)
        q = summarize_correction(before, after, depth, 0.001, 5.0)
        self.assertEqual(q["changed_pixels"], 2)
        self.assertEqual(q["changed_pixels_with_valid_depth"], 1)
        self.assertEqual(q["changed_pixels_without_valid_depth"], 1)
        self.assertEqual(q["classes"]["broccoli_head"]["after_valid_3d_points"], 2)
        self.assertFalse(q["ground_truth_verified"])

    def test_reviewed_3d_export(self):
        rgb = io.BytesIO()
        depth = io.BytesIO()
        Image.fromarray(np.zeros((10, 10, 3), dtype=np.uint8)).save(rgb, "PNG")
        Image.fromarray(np.full((10, 10), 800, dtype=np.uint16)).save(depth, "PNG")
        calibration = {"resolution": {"width": 10, "height": 10},
                       "rgb_intrinsics": {"fx": 10, "fy": 10, "cx": 4.5, "cy": 4.5,
                                          "distortion_coefficients": [0, 0, 0, 0, 0]},
                       "usage_notes": {"depth_alignment": "Depth aligned to the RGB image",
                                       "coordinate_formula": "Z is depth in mm"}}
        raw_calibration = json.dumps(calibration).encode()
        polygons = [{"class_id": 4, "vertices": [[2, 2], [8, 2], [2, 8]]}]
        with APP.test_client() as client:
            first = client.post("/annotate", data={"rgb": (io.BytesIO(rgb.getvalue()), "rgb.png"),
                "depth": (io.BytesIO(depth.getvalue()), "depth.png"),
                "calibration": (io.BytesIO(raw_calibration), "camera_intrinsics.json"),
                "annotations": json.dumps(polygons)})
            self.assertEqual(first.status_code, 200, first.json)
            archive = client.get("/download/" + first.json["id"]).data
            prepared = client.post("/correction/prepare", data={
                "archive": (io.BytesIO(archive), "first.zip"),
                "rgb": (io.BytesIO(rgb.getvalue()), "rgb.png")})
            self.assertEqual(prepared.status_code, 200, prepared.json)
            corrected = client.post("/correction/export", data={
                "archive": (io.BytesIO(archive), "first.zip"),
                "rgb": (io.BytesIO(rgb.getvalue()), "rgb.png"),
                "depth": (io.BytesIO(depth.getvalue()), "depth.png"),
                "calibration": (io.BytesIO(raw_calibration), "camera_intrinsics.json"),
                "strokes": json.dumps([{"class_id": 0, "radius": 2, "points": [[3, 3]]}]),
                "reviewer": "manoj"})
            self.assertEqual(corrected.status_code, 200, corrected.json)
            self.assertFalse(corrected.json["ground_truth_verified"])
            exported = client.get("/download/" + corrected.json["id"])
            with zipfile.ZipFile(io.BytesIO(exported.data)) as zipped:
                audit = json.loads(zipped.read("correction_audit.json"))
                self.assertEqual(audit["reviewer"], "manoj")
                self.assertEqual(zipped.read("original_annotation.zip"), archive)
                self.assertIn("semantic_cloud.ply", zipped.namelist())
                quality = json.loads(zipped.read("correction_quality.json"))
                self.assertEqual(quality["changed_pixels"], audit["changed_pixels"])
                self.assertEqual(quality["total_valid_depth_pixels"], 100)
                self.assertFalse(quality["ground_truth_verified"])

    def test_blank_annotation_form_needs_no_zip(self):
        with APP.test_client() as client:
            response = client.get("/correct")
            self.assertEqual(response.status_code, 200)
            page = response.data.decode("utf-8")
            self.assertIn("function readyForLoad(){return Boolean(source('rgb'));}", page)
            self.assertIn("function readyForExport()", page)
            self.assertNotIn('id="archive"', page)
            self.assertIn("Blank mask ready", page)
            self.assertIn("previewRGB", page)

    def test_start_blank_and_export_without_annotation_zip(self):
        rgb, depth = io.BytesIO(), io.BytesIO()
        Image.fromarray(np.zeros((10, 10, 3), dtype=np.uint8)).save(rgb, "PNG")
        Image.fromarray(np.full((10, 10), 800, dtype=np.uint16)).save(depth, "PNG")
        calibration = {"resolution": {"width": 10, "height": 10},
                       "rgb_intrinsics": {"fx": 10, "fy": 10, "cx": 4.5, "cy": 4.5,
                                          "distortion_coefficients": [0, 0, 0, 0, 0]},
                       "usage_notes": {"depth_alignment": "Depth aligned to the RGB image",
                                       "coordinate_formula": "Z is depth in mm"}}
        with APP.test_client() as client:
            prep = client.post("/correction/prepare", data={"rgb": (io.BytesIO(rgb.getvalue()), "rgb.png")})
            self.assertEqual(prep.status_code, 200, prep.json)
            result = client.post("/correction/export", data={
                "rgb": (io.BytesIO(rgb.getvalue()), "rgb.png"),
                "depth": (io.BytesIO(depth.getvalue()), "depth.png"),
                "calibration": (io.BytesIO(json.dumps(calibration).encode()), "camera_intrinsics.json"),
                "strokes": json.dumps([{"class_id": 4, "radius": 2, "points": [[4, 4]]}]),
                "reviewer": "manoj"})
            self.assertEqual(result.status_code, 200, result.json)
            self.assertEqual(result.json["review_status"], "UNREVIEWED")
            with zipfile.ZipFile(io.BytesIO(client.get("/download/" + result.json["id"]).data)) as zipped:
                self.assertNotIn("original_annotation.zip", zipped.namelist())
                self.assertEqual(json.loads(zipped.read("correction_audit.json"))["provenance"],
                                 "human_brush_annotation")
                with Image.open(io.BytesIO(zipped.read("labels.png"))) as labels:
                    arr = np.asarray(labels)
                self.assertEqual(int(arr[4, 4]), 4)
                self.assertEqual(int(arr[9, 9]), 0)


if __name__ == "__main__":
    unittest.main()
