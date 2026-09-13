# -*- coding: utf-8 -*-
"""Small helpers for running the solver scripts from any working directory."""

from pathlib import Path


CODE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = CODE_DIR.parent
REPO_ROOT = PROJECT_DIR.parent


def attachment_path(index):
    """Return the path to contest attachment `index`.

    The original scripts expected files named `1.xlsx` ... `4.xlsx` under
    `25_国赛/code/attach/`.  The repository also keeps the released files under
    `题目以及原始数据/附件/附件N.xlsx`, so this resolver supports both layouts.
    """
    candidates = [
        CODE_DIR / "attach" / f"{index}.xlsx",
        REPO_ROOT / "attach" / f"{index}.xlsx",
        REPO_ROOT / "题目以及原始数据" / "附件" / f"附件{index}.xlsx",
    ]
    for path in candidates:
        if path.exists():
            return path

    searched = "\n".join(f"  - {path}" for path in candidates)
    raise FileNotFoundError(
        f"Cannot find attachment {index}.xlsx. Searched:\n{searched}"
    )
