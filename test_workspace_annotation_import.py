"""Verify source-bound annotation ZIP imports into the local workspace."""
import base64
import hashlib
import io
import json
import unittest
import zipfile

from PIL import Image

from webapp import APP


def png(mode, color):
    stream = io.BytesIO()
    Image.new(mode, (4, 3), color).save(stream, format="PNG")
    return stream.getvalue()


class WorkspaceAnnotationImportTests(unittest.TestCase):
    def setUp(self):
        self.rgb = png("RGB", (120, 170, 50))
        self.depth = png("I;16", 1000)
        self.labels = png("L", 4)
        self.calibration = dict(fx=600, fy=600, cx=2, cy=1.5, width=4,
                                height=3, depth_scale=.001, depth_type="axial_z")
        report = {
            "sources": {
                key: {"sha256": hashlib.sha256(value).hexdigest()}
                for key, value in (("rgb", self.rgb), ("depth", self.depth),
                                   ("labels", self.labels))
            },
            "calibration": self.calibration,
            "annotation_review": "UNREVIEWED",
        }
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("labels.png", self.labels)
            archive.writestr("qa_report.json", json.dumps(report))
        self.archive = output.getvalue()

    def send(self, archive=None, rgb=None, depth=None):
        return APP.test_client().post(
            "/workspace/import-annotation",
            data={
                "archive": (io.BytesIO(self.archive if archive is None else archive), "annotations.zip"),
                "rgb": (io.BytesIO(self.rgb if rgb is None else rgb), "rgb.png"),
                "depth": (io.BytesIO(self.depth if depth is None else depth), "depth.png"),
            },
            content_type="multipart/form-data",
        )

    def test_matching_source_import_returns_original_labels_and_calibration(self):
        response = self.send()
        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()
        self.assertEqual(base64.b64decode(payload["labels_png_base64"]), self.labels)
        self.assertEqual(payload["calibration"], self.calibration)
        self.assertEqual(payload["review_status"], "UNREVIEWED")

    def test_rejects_different_rgb(self):
        response = self.send(rgb=png("RGB", (1, 2, 3)))
        self.assertEqual(response.status_code, 422)
        self.assertIn("RGB SHA-256", response.get_json()["error"])

    def test_rejects_different_depth(self):
        response = self.send(depth=png("I;16", 500))
        self.assertEqual(response.status_code, 422)
        self.assertIn("Depth SHA-256", response.get_json()["error"])

    def test_rejects_tampered_labels(self):
        tampered = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(self.archive)) as source:
            with zipfile.ZipFile(tampered, "w") as target:
                target.writestr("labels.png", png("L", 2))
                target.writestr("qa_report.json", source.read("qa_report.json"))
        self.assertEqual(self.send(archive=tampered.getvalue()).status_code, 422)

    def test_workspace_import_interface(self):
        markup = APP.test_client().get("/workspace").get_data(as_text=True)
        self.assertIn('id="import-annotation"', markup)
        self.assertIn('/workspace/import-annotation', markup)
        self.assertIn("importedLabels", markup)


if __name__ == "__main__":
    unittest.main()
