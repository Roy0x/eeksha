import tempfile
import unittest
import io
import zipfile
import json
from pathlib import Path
import numpy as np
from PIL import Image
from eeksha import process, make_demo
from viewer import generate_viewer
from webapp import APP
from we3ds import inspect_we3ds, export_calibrated_we3ds


class PipelineTests(unittest.TestCase):
    def test_demo_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            make_demo(root / "sample")
            report = process(*(root / "sample" / f for f in ("rgb.png", "depth.png", "labels.png", "calibration.json")), root / "out")
            with np.load(root / "out" / "semantic_cloud.npz") as data:
                self.assertEqual(len(data["xyz"]), report["points"])
                self.assertEqual(set(np.unique(data["labels"])), {1, 2, 3})
                self.assertAlmostEqual(data["xyz"][0, 2], 1.25)
            self.assertTrue((root / "out" / "semantic_cloud.ply").exists())
            generate_viewer(root / "out" / "semantic_cloud.npz", root / "out" / "qa_report.json", root / "out" / "viewer.html")
            viewer = (root / "out" / "viewer.html").read_text(encoding="utf-8")
            self.assertIn("Semantic 3D Explorer", viewer)
            self.assertIn("10,440 points", viewer)

    def test_viewer_rejects_invalid_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(ValueError, "positive"):
                generate_viewer(root / "data.npz", root / "qa.json", root / "viewer.html", limit=0)

    def test_browser_demo_and_download(self):
        client = APP.test_client()
        self.assertEqual(client.get("/").status_code, 200)
        response = client.post("/process", data={"demo": "true"})
        self.assertEqual(response.status_code, 200)
        token = response.json["id"]
        self.assertTrue(response.json["report"]["synthetic_demo"])
        self.assertIn(b"SYNTHETIC TEST SCENE", client.get(f"/viewer/{token}").data)
        with zipfile.ZipFile(io.BytesIO(client.get(f"/download/{token}").data)) as archive:
            self.assertIn("semantic_cloud.npz", archive.namelist())
            self.assertIn("qa_report.json", archive.namelist())

    def test_browser_requires_four_inputs(self):
        client = APP.test_client()
        response = client.post("/process", data={})
        self.assertEqual(response.status_code, 400)

    def test_browser_uploaded_files(self):
        client = APP.test_client()
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            make_demo(folder)
            files = {
                field: (io.BytesIO((folder / filename).read_bytes()), filename)
                for field, filename in (("rgb", "rgb.png"), ("depth", "depth.png"),
                                        ("labels", "labels.png"), ("calibration", "calibration.json"))
            }
            response = client.post("/process", data=files, content_type="multipart/form-data")
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json["report"]["synthetic_demo"])

    def test_reject_misaligned_input(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            make_demo(root)
            Image.fromarray(np.zeros((2, 3), dtype=np.uint8)).save(root / "labels.png")
            with self.assertRaisesRegex(ValueError, "identical image dimensions"):
                process(*(root / f for f in ("rgb.png", "depth.png", "labels.png", "calibration.json")), root / "out")

    def test_reject_invalid_calibration(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            make_demo(root)
            path = root / "calibration.json"
            path.write_text(path.read_text().replace('"fx": 110', '"fx": 0'))
            with self.assertRaisesRegex(ValueError, "must be positive"):
                process(*(root / f for f in ("rgb.png", "depth.png", "labels.png", "calibration.json")), root / "out")

    def test_ray_distance_conversion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            make_demo(root)
            cal_path = root / "calibration.json"
            cal = json.loads(cal_path.read_text())
            cal["depth_type"] = "ray_distance"
            cal_path.write_text(json.dumps(cal))
            process(*(root / f for f in ("rgb.png", "depth.png", "labels.png", "calibration.json")), root / "out")
            with np.load(root / "out" / "semantic_cloud.npz") as data:
                first = data["xyz"][0]
                self.assertAlmostEqual(float(np.linalg.norm(first)), 1.25, places=5)
                self.assertLess(first[2], 1.25)

    def test_missing_depth_type_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            make_demo(root)
            cal_path = root / "calibration.json"
            cal = json.loads(cal_path.read_text())
            del cal["depth_type"]
            cal_path.write_text(json.dumps(cal))
            with self.assertRaisesRegex(ValueError, "depth_type"):
                process(*(root / f for f in ("rgb.png", "depth.png", "labels.png", "calibration.json")), root / "out")

    def test_we3ds_preserves_species_and_blocks_3d(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rgb = np.zeros((3, 4, 3), dtype=np.uint8)
            depth = np.full((3, 4), 7000, dtype=np.uint16)
            labels = np.ones((3, 4), dtype=np.uint8)
            labels[0, 0] = 11
            Image.fromarray(rgb).save(root / "rgb.png")
            Image.fromarray(depth).save(root / "depth.png")
            Image.fromarray(labels).save(root / "labels.png")
            report = inspect_we3ds(root / "rgb.png", root / "depth.png", root / "labels.png", root / "out")
            self.assertEqual(report["class_counts"]["corn"], 1)
            self.assertAlmostEqual(report["depth_min_m"], 0.7)
            self.assertEqual(report["calibration_status"], "MISSING_INTRINSICS")
            self.assertFalse((root / "out" / "semantic_cloud.ply").exists())
            self.assertTrue((root / "out" / "semantic_overlay.png").exists())

    def test_we3ds_web_requires_three_inputs(self):
        self.assertEqual(APP.test_client().post("/we3ds").status_code, 400)

    def test_we3ds_3d_requires_provenance_and_intrinsics(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            Image.fromarray(np.zeros((2, 3, 3), dtype=np.uint8)).save(root / "rgb.png")
            Image.fromarray(np.full((2, 3), 7000, dtype=np.uint16)).save(root / "depth.png")
            Image.fromarray(np.ones((2, 3), dtype=np.uint8)).save(root / "labels.png")
            calibration = {"fx": 200, "fy": 200, "cx": 1, "cy": 0.5,
                           "width": 3, "height": 2, "depth_type": "ray_distance",
                           "depth_scale": 0.0001}
            (root / "cal.json").write_text(json.dumps(calibration))
            args = (root / "rgb.png", root / "depth.png", root / "labels.png", root / "cal.json", root / "out")
            with self.assertRaisesRegex(ValueError, "source_type"):
                export_calibrated_we3ds(*args)
            calibration.update(source_type="measured_rectified_cropped_intrinsics", source_reference="lab-calibration-record")
            (root / "cal.json").write_text(json.dumps(calibration))
            result = export_calibrated_we3ds(*args)
            self.assertEqual(result["points"], 6)
            self.assertTrue((root / "out" / "semantic_cloud.ply").exists())


if __name__ == "__main__":
    unittest.main()
