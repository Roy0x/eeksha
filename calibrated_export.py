"""Explicit WE3DS point-cloud export once calibrated image intrinsics are available."""
import argparse
from pathlib import Path
from we3ds import export_calibrated_we3ds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rgb", type=Path, required=True)
    parser.add_argument("--depth", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("we3ds_3d_output"))
    args = parser.parse_args()
    report = export_calibrated_we3ds(args.rgb, args.depth, args.labels, args.calibration, args.output)
    print(f"Exported {report['points']} points to {args.output}; independent metric accuracy still unverified.")


if __name__ == "__main__":
    main()
