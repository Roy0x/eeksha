"""Exercise the real Eeksha resume -> erase -> export HTTP workflow locally.

Usage: python scripts/smoke_resume_export.py ORIGINAL.zip RGB.png DEPTH.png INTRINSICS.json OUTPUT.zip
This creates a separate output; input files are never modified.
"""
from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from webapp import APP


def main(source: Path, rgb: Path, depth: Path, intrinsics: Path, output: Path) -> None:
    original = source.read_bytes()
    rgb_bytes = rgb.read_bytes()
    depth_bytes = depth.read_bytes()
    camera_bytes = intrinsics.read_bytes()
    with APP.test_client() as client:
        prepared = client.post('/correction/prepare', data={
            'archive': (io.BytesIO(original), source.name),
            'rgb': (io.BytesIO(rgb_bytes), rgb.name),
        })
        if prepared.status_code != 200 or not prepared.json.get('resumed'):
            raise ValueError(f'Unable to resume archive: {prepared.json}')

        response = client.post('/correction/export', data={
            'archive': (io.BytesIO(original), source.name),
            'rgb': (io.BytesIO(rgb_bytes), rgb.name),
            'depth': (io.BytesIO(depth_bytes), depth.name),
            'calibration': (io.BytesIO(camera_bytes), intrinsics.name),
            'reviewer': 'automated-smoke-review-candidate',
            'strokes': json.dumps([{'class_id': 0, 'radius': 24, 'points': [[604, 155]]}]),
        })
        if response.status_code != 200:
            raise ValueError(f'Re-export failed: {response.json}')
        result = client.get('/download/' + response.json['id'])
        if result.status_code != 200:
            raise ValueError('Generated archive is not downloadable')
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(result.data)

    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError('Generated archive CRC failure')
        report = json.loads(archive.read('qa_report.json'))
        quality = json.loads(archive.read('correction_quality.json'))
        audit = json.loads(archive.read('correction_audit.json'))
        if archive.read('original_annotation.zip') != original:
            raise ValueError('Export did not preserve the original dataset')
        if quality['broccoli_head_regions']['significant_region_count'] != 4:
            raise ValueError('Expected four significant broccoli-head regions after erasure')
        if report['annotation_review'] != 'HUMAN_REVIEWED_NOT_GROUND_TRUTH':
            raise ValueError('Unexpected review status')
        print(json.dumps({
            'resumed': True,
            'changed_pixels': audit['changed_pixels'],
            'significant_head_regions': quality['broccoli_head_regions']['significant_region_count'],
            'head_points_with_depth': quality['classes']['broccoli_head']['after_valid_3d_points'],
            'all_depth_points': report['points'],
            'ground_truth_verified': False,
            'output': str(output),
        }, indent=2))


if __name__ == '__main__':
    if len(sys.argv) != 6:
        raise SystemExit('Usage: smoke_resume_export.py original.zip rgb.png depth.png intrinsics.json output.zip')
    main(*(Path(arg) for arg in sys.argv[1:]))
