# -*- coding: utf-8 -*-
"""Run the repository's reproducibility scripts from the project root."""

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CODE_DIR = ROOT / "25_国赛" / "code"
OUTPUT_DIR = CODE_DIR / "outputs"


def run_script(script_name, env):
    script = CODE_DIR / script_name
    print(f"\n===== Running {script_name} =====", flush=True)
    subprocess.run([sys.executable, str(script)], cwd=OUTPUT_DIR, env=env, check=True)


def build_env():
    env = os.environ.copy()
    env.setdefault("MPLBACKEND", "Agg")
    env.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".mplconfig"))
    env["PYTHONPATH"] = str(CODE_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    return env


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Reproduce the reported numerical checks and figures. By default "
            "this runs the lightweight checks; pass --full-q2 to rerun the "
            "heavier global-local optimization in q2.py."
        )
    )
    parser.add_argument(
        "--full-q2",
        action="store_true",
        help="run q2.py full optimization instead of the fast q2-example.py check",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / ".mplconfig").mkdir(parents=True, exist_ok=True)
    env = build_env()

    run_script("q2.py" if args.full_q2 else "q2-example.py", env)
    run_script("q3-interfere.py", env)
    run_script("q3-fft.py", env)

    print(f"\nDone. Generated figures are under: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
