import hashlib
import io
import json
import unittest
import zipfile

import numpy as np
from PIL import Image

from annotation import build_mask
from review import compare_exports, load_annotation, make_rgb_overlay
from webapp import APP


def make_export(polygons, rgb_hash="a" * 64, depth_hash="b" * 64):
    mask = build_mask(20, 20, polygons)
    stream = io.BytesIO()
    mask.save(stream, format="PNG")
    payload = stream.getvalue()
    annotation = {"provenance": "human_drawn_polygon_annotations", "review_status": "UNREVIEWED",
                  "image_width": 20, "image_height": 20, "polygons": polygons}
    qa = {"sources": {"rgb": {"sha256": rgb_hash}, "depth": {"sha256": depth_hash},
                      "labels": {"sha256": hashlib.sha256(payload).hexdigest()}},
          "calibration": {"fx": 10, "fy": 10, "cx": 10, "cy": 10, "depth_scale": 0.001,
                          "depth_type": "axial_z"}}
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("labels.png", payload)
        z.writestr("annotations.json", json.dumps(annotation))
        z.writestr("qa_report.json", json.dumps(qa))
    return archive.getvalue()


class ReviewTests(unittest.TestCase):
    first = [{"class_id": 4, "vertices": [[2, 2], [10, 2], [2, 10]]}]
    second = [{"class_id": 4, "vertices": [[3, 2], [11, 2], [3, 10]]}]

    @staticmethod
    def source_png():
        stream = io.BytesIO()
        Image.new("RGB", (20, 20), (31, 76, 39)).save(stream, format="PNG")
        return stream.getvalue()

    def test_identical_masks_are_not_ground_truth(self):
        raw = make_export(self.first)
        result, preview = compare_exports(raw, raw)
        self.assertEqual(result["labeled_agreement_iou"], 1)
        self.assertFalse(result["ground_truth_verified"])
        self.assertEqual(result["status"], "NEEDS_HUMAN_ADJUDICATION")
        self.assertEqual(Image.open(io.BytesIO(preview)).size, (20, 20))

    def test_disagreement_and_class_iou(self):
        result, _ = compare_exports(make_export(self.first), make_export(self.second))
        self.assertGreater(result["disagreement_pixels"], 0)
        self.assertGreater(result["class_iou"]["broccoli_head"]["iou"], 0)
        self.assertLess(result["class_iou"]["broccoli_head"]["iou"], 1)

    def test_reject_different_sources(self):
        with self.assertRaisesRegex(ValueError, "different RGB"):
            compare_exports(make_export(self.first), make_export(self.first, rgb_hash="c" * 64))

    def test_reject_tampered_mask(self):
        raw = make_export(self.first)
        with zipfile.ZipFile(io.BytesIO(raw)) as old:
            contents = {name: old.read(name) for name in old.namelist()}
        tampered = Image.fromarray(np.zeros((20, 20), dtype=np.uint8))
        stream = io.BytesIO()
        tampered.save(stream, format="PNG")
        contents["labels.png"] = stream.getvalue()
        modified = io.BytesIO()
        with zipfile.ZipFile(modified, "w") as z:
            for name, data in contents.items():
                z.writestr(name, data)
        with self.assertRaisesRegex(ValueError, "does not match recorded polygons"):
            load_annotation(modified.getvalue())

    def test_http_comparison(self):
        with APP.test_client() as client:
            self.assertEqual(client.get("/review").status_code, 200)
            response = client.post("/review", data={
                "first": (io.BytesIO(make_export(self.first)), "first.zip"),
                "second": (io.BytesIO(make_export(self.second)), "second.zip")})
            self.assertEqual(response.status_code, 200, response.json)
            self.assertEqual(response.json["summary"]["status"], "NEEDS_HUMAN_ADJUDICATION")
            self.assertTrue(response.json["disagreement_preview_base64"])

    def test_verified_rgb_overlay_and_transparent_unknown(self):
        rgb = self.source_png()
        sha = hashlib.sha256(rgb).hexdigest()
        first = make_export(self.first, rgb_hash=sha)
        second = make_export(self.second, rgb_hash=sha)
        summary, preview = compare_exports(first, second)
        verified, alpha_png = make_rgb_overlay(rgb, preview, summary)
        self.assertEqual(Image.open(io.BytesIO(verified)).size, (20, 20))
        overlay = np.array(Image.open(io.BytesIO(alpha_png)))
        self.assertEqual(overlay[19, 19, 3], 0)
        self.assertEqual(overlay[3, 3, 3], 255)
        with APP.test_client() as client:
            response = client.post("/review", data={
                "first": (io.BytesIO(first), "first.zip"),
                "second": (io.BytesIO(second), "second.zip"),
                "rgb": (io.BytesIO(rgb), "original.png")})
            self.assertEqual(response.status_code, 200, response.json)
            self.assertTrue(response.json["transparent_overlay_base64"])

    def test_reject_wrong_rgb_even_when_zip_sources_match(self):
        with APP.test_client() as client:
            response = client.post("/review", data={
                "first": (io.BytesIO(make_export(self.first)), "first.zip"),
                "second": (io.BytesIO(make_export(self.second)), "second.zip"),
                "rgb": (io.BytesIO(self.source_png()), "wrong.png")})
            self.assertEqual(response.status_code, 422)
            self.assertIn("SHA-256", response.json["error"])


if __name__ == "__main__":
    unittest.main()
