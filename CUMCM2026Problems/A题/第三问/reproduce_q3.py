"""Reproduce the Q3 analysis; completed runs are reused only when source/input hashes match.

Use --recompute to rerun all PDE cases. Default is deterministic cached rebuild.
"""
from pathlib import Path
import argparse
import json
import subprocess
import sys

from solve_q3 import digest, ENV, Q2

ROOT = Path(__file__).resolve().parent
CASES = [
    ('mean_n400_dt2', 400, 2, 'mean'),
    ('mean_n400_dt1', 400, 1, 'mean'),
    ('mean_n400_dt0p5', 400, 0.5, 'mean'),
    ('mean_n800_dt0p5', 800, 0.5, 'mean'),
    ('mean_n1600_dt0p5', 1600, 0.5, 'mean'),
    ('mean_n3200_dt0p5', 3200, 0.5, 'mean'),
    ('mean_n3200_dt1', 3200, 1, 'mean'),
    ('last_n3200_dt0p5', 3200, 0.5, 'last'),
]


def compatible(label):
    p = ROOT/'runs'/f'{label}.json'
    if not p.exists() or not p.with_suffix('.npz').exists():
        return False
    m = json.loads(p.read_text())
    return (m.get('solver_sha256') == digest(ROOT/'solve_q3.py')
            and m.get('input_sha256') == digest(ENV)
            and m.get('q2_sha256') == digest(Q2))


def call(args):
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--recompute', action='store_true')
    args = parser.parse_args()
    if args.recompute or not compatible('q2_regression'):
        call(['solve_q3.py', '--mode', 'regression', '--n', '400', '--label', 'q2_regression'])
    for label, n, dt, extension in CASES:
        if args.recompute or not compatible(label):
            call(['solve_q3.py', '--mode', 'case', '--n', str(n), '--dt', str(dt),
                  '--extension', extension, '--label', label])
    call(['deliver_q3.py'])


if __name__ == '__main__':
    main()
