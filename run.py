import argparse
from pathlib import Path
from eeksha import process, make_demo
from viewer import generate_viewer

parser = argparse.ArgumentParser(description="Eeksha MVP — measured depth to labeled 3D point cloud")
parser.add_argument("--input", type=Path, default=Path("sample"))
parser.add_argument("--output", type=Path, default=Path("output"))
parser.add_argument("--demo", action="store_true", help="Generate explicitly synthetic test input")
args = parser.parse_args()
if args.demo:
    make_demo(args.input)
report = process(args.input / "rgb.png", args.input / "depth.png", args.input / "labels.png",
                 args.input / "calibration.json", args.output)
if args.demo:
    report["synthetic_demo"] = True
    import json
    (args.output / "qa_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
generate_viewer(args.output / "semantic_cloud.npz", args.output / "qa_report.json", args.output / "viewer.html")
print(f"{report['status']}: {report['points']} points, depth coverage {report['depth_coverage']:.1%}")
print(f"Exported {args.output / 'semantic_cloud.ply'}, semantic_cloud.npz, qa_report.json")
print(f"Open {args.output / 'viewer.html'} in Chrome to explore the point cloud")
