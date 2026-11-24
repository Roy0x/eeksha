"""Tests for source-matched comparison of baseline and corrected exports."""
import io
import json
import unittest
import zipfile

from qa_compare import compare_qa
from webapp import APP

CLASSES = ("unknown", "soil", "crop", "weed", "broccoli_head", "broccoli_leaf")


def report(*, rgb="a", depth="b", label="c", head=2, unknown=8, calibration=None):
    counts = {name: 0 for name in CLASSES}
    counts["unknown"] = unknown
    counts["broccoli_head"] = head
    return {
        "points": unknown + head, "depth_coverage": 0.5,
        "max_depth_m": 5.0,
        "class_counts": counts,
        "calibration": calibration or dict(fx=100, fy=100, cx=2, cy=2, depth_scale=.001, depth_type="axial_z"),
        "sources": {
            "rgb": {"sha256": rgb * 64},
            "depth": {"sha256": depth * 64},
            "labels": {"sha256": label * 64},
        },
    }


def archive(data):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zip_file:
        zip_file.writestr("qa_report.json", json.dumps(data))
    return buf.getvalue()


class QaCompareTests(unittest.TestCase):
    def test_source_matched_delta(self):
        before = archive(report())
        after = archive(report(label="d", head=5, unknown=5))
        result = compare_qa(before, after)
        self.assertEqual(result["labeled_valid_points_before"], 2)
        self.assertEqual(result["labeled_valid_points_after"], 5)
        self.assertEqual(result["class_deltas"]["broccoli_head"], 3)
        self.assertEqual(result["class_deltas"]["unknown"], -3)
        self.assertTrue(result["source_labels_changed"])
        self.assertFalse(result["ground_truth_verified"])

    def test_rejects_different_rgb(self):
        with self.assertRaisesRegex(ValueError, "different source RGB"):
            compare_qa(archive(report()), archive(report(rgb="f")))

    def test_rejects_different_depth(self):
        with self.assertRaisesRegex(ValueError, "different source DEPTH"):
            compare_qa(archive(report()), archive(report(depth="f")))

    def test_rejects_different_calibration(self):
        with self.assertRaisesRegex(ValueError, "different camera calibrations"):
            compare_qa(archive(report()), archive(report(calibration={"fx": 200})))

    def test_rejects_tampered_counts(self):
        bad = report()
        bad["points"] = 999
        with self.assertRaisesRegex(ValueError, "Class counts disagree"):
            compare_qa(archive(bad), archive(report()))

    def test_rejects_duplicate_report_members(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("qa_report.json", "{}")
            z.writestr("qa_report.json", "{}")
        with self.assertRaisesRegex(ValueError, "exactly one"):
            compare_qa(buf.getvalue(), archive(report()))

    def test_endpoint_and_workspace(self):
        a, b = archive(report()), archive(report(label="d", head=5, unknown=5))
        response = APP.test_client().post(
            "/workspace/compare-qa",
            data={"before": (io.BytesIO(a), "baseline.zip"),
                  "after": (io.BytesIO(b), "corrected.zip")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        html = APP.test_client().get("/workspace").get_data(as_text=True)
        self.assertIn("Compare QA reports", html)
        self.assertIn("/workspace/compare-qa", html)


if __name__ == "__main__":
    unittest.main()
