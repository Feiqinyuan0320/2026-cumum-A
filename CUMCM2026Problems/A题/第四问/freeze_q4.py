"""Record the exact numerical inputs, archives and generated artifacts for review."""
import json
import platform
from pathlib import Path
import numpy as np
import numba
import openpyxl
import matplotlib
import solve_q4 as q


def main():
    root = q.ROOT
    summary = json.loads((root/'results/计算摘要.json').read_text())
    files = [root/n for n in ['solve_q4.py', 'verify_q4.py', 'deliver_q4.py', 'reproduce_q4.py',
                              'freeze_q4.py', 'utils/plot_style.py', '题目分析报告.md', '术语表格.md']]
    files += [q.ENV, q.RAD, root.parent/'附件/结果文件夹/result4.xlsx']
    for c in summary['cases']:
        files += [root/'runs'/f'{c["label"]}.{ext}' for ext in ['json', 'npz']]
    files += [f for f in (root/'results').iterdir() if f.is_file() and f.name != '复现清单.json']
    files += [f for f in (root/'figures').iterdir() if f.suffix in ['.pdf', '.svg', '.png']]
    import os
    hashes = {os.path.relpath(f, root): q.digest(f) for f in sorted(set(files))}
    manifest = {'scope': 'q4', 'randomness': 'none; deterministic finite-volume solution',
        'command': '/opt/anaconda3/bin/python reproduce_q4.py',
        'fresh_PDE_command': '/opt/anaconda3/bin/python reproduce_q4.py --recompute',
        'default_mode': 'Hash-verified archived trajectories; fresh short tests and workbook/table reconstruction checks. No long PDE rerun.',
        'working_directory': str(root), 'cases': summary['cases'],
        'runtime': {'python': platform.python_version(), 'numpy': np.__version__, 'numba': numba.__version__,
                    'openpyxl': openpyxl.__version__, 'matplotlib': matplotlib.__version__},
        'figure_scope': '3 core figures requested in agreed preparation; one each raw/process/result, English labels.',
        'main_case': summary['main_case'], 'fixed_case': summary['fixed_case'], 'files_sha256': hashes}
    (root/'results/复现清单.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(json.dumps({'frozen_files': len(hashes), 'cases': len(summary['cases'])}))


if __name__ == '__main__':
    main()
