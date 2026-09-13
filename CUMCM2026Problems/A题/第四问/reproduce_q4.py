"""Reproduce key Q4 checks from frozen numerical archives; --recompute reruns PDE.

The default verifies source/input/archive hashes, reruns short independent checks,
and recomputes the workbook/table comparison from full-precision cached arrays.
It does not repeat the expensive PDE trajectories or alter delivered files.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import numpy as np
import openpyxl
import solve_q4 as q
from verify_q4 import checks


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--recompute', action='store_true')
    args = p.parse_args()
    root = q.ROOT
    manifest = json.loads((root/'results/复现清单.json').read_text())
    for relative, sha in manifest['files_sha256'].items():
        path = root/relative
        assert path.exists() and q.digest(path) == sha, f'changed file: {relative}'
    checks()
    for case in manifest['cases']:
        label = case['label']
        with np.load(root/'runs'/f'{label}.npz') as f:
            before = dict(f)
        if args.recompute:
            target = f'recomputed_{label}'
            subprocess.run([sys.executable, str(root/'solve_q4.py'), '--mode', 'case',
                            '--geometry', case['geometry'], '--n', str(case['N']),
                            '--dt', str(case['dt_s']), '--early-dt', str(case['early_dt_s']),
                            '--extension', 'mean', '--label', target, '--no-cache'], check=True)
            with np.load(root/'runs'/f'{target}.npz') as f:
                assert np.array_equal(before['C'], f['C'], equal_nan=True)
                assert np.array_equal(before['event'], f['event'])
        assert np.isfinite(before['relative_T']).all() and np.isfinite(before['relative_C']).all()
        assert 0 < before['event'][3] < .15
        assert 0 < before['event'][1]-before['event'][0] <= .001
        assert before['event'][2] >= before['event'][1]
        assert before['times'][-1]-before['event'][2] < 60
        assert before['stats'][4] < 1e-12 and before['stats'][5] < 1e-12
        assert abs(before['stats'][8]) < 1e-10
    summary = json.loads((root/'results/计算摘要.json').read_text())
    with np.load(root/'runs'/f'{summary["main_case"]}.npz') as f:
        a = dict(f)
    mask = np.arange(20)[None, :]*.001 <= a['radii'][:, None]+1e-10
    assert np.array_equal(np.isfinite(a['C'][:, :20]), mask)
    assert np.isfinite(a['C'][:, -1]).all()
    wb = openpyxl.load_workbook(root/'results/result4.xlsx', read_only=True, data_only=True)
    rows = list(wb.active.values); wb.close()
    output = np.asarray(rows[1:], dtype=float)
    assert list(rows[0][1:-1]) == [i/10 for i in range(20)]
    assert rows[0][-1] == '药材表面'
    assert np.array_equal(output[:, 0], a['times'])
    assert np.array_equal(output[:, 1:], np.round(a['C'], 4), equal_nan=True)
    wb = openpyxl.load_workbook(root/'results/表6_水分浓度.xlsx', read_only=True, data_only=True)
    table = np.asarray(list(wb.active.values)[1:], dtype=float); wb.close()
    times = np.asarray(summary['table6_hours'][:-1])*3600
    idx = np.searchsorted(a['times'], times)
    expected = np.vstack((a['C'][idx][:, [0, 5, 10, 20]], a['event_C'][[0, 5, 10, 20]]))
    assert np.array_equal(table[:, 1:], np.round(expected, 4))
    assert np.allclose(table[:, 0], summary['table6_hours'], rtol=0, atol=1e-12)
    assert summary['event_radius_cm'] == 1.2
    assert not summary['radius_plateau_extension_used']
    print(json.dumps({'status': 'PASS', 'mode': 'fresh PDE recomputation' if args.recompute else 'frozen-archive reproduction with fresh short tests',
                      'files_hashed': len(manifest['files_sha256']), 'cases': len(manifest['cases']),
                      'main_drying_h': summary['reported_drying_h'],
                      'fixed_drying_h': summary['fixed_drying_h'], 'result4_rows': len(a['times']),
                      'outside_domain_blanks': int(np.isnan(a['C']).sum()),
                      'table6_rows': len(table)}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
