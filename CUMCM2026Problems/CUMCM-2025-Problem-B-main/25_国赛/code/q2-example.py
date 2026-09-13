# -*- coding: utf-8 -*-
"""Fast Problem 2 reproduction using the fitted parameters reported in paper.

`q2.py` performs the full differential-evolution plus L-BFGS-B optimization.
That run is intentionally heavier.  This script reuses the same model and data
loader, evaluates the published fitted parameters, and reports the fit metrics
needed for a quick reproducibility check.
"""

import numpy as np

from q2 import load_data, loss_single, model_percent
from repro_utils import attachment_path


PAPER_PARAMS = np.array(
    [
        7.413,    # d_um
        0.100,    # gamma_L
        1.096,    # gamma_T
        457.42,   # omega_p1
        1294.51,  # gamma_p1
        1120.07,  # omega_p2
        648.05,   # gamma_p2
    ],
    dtype=float,
)


def calculate_r2(y_true, y_pred):
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    return 1 - (ss_res / ss_tot)


def summarize_dataset(index, params):
    sigma_data, y_data = load_data(attachment_path(index))
    y_fit = model_percent(sigma_data, params)
    mse = loss_single(sigma_data, y_data, params)
    r2 = calculate_r2(y_data, y_fit)
    return mse, r2


if __name__ == "__main__":
    print("===== 问题二快速复现：论文报告参数 =====")
    print(f"d_um = {PAPER_PARAMS[0]:.4f} μm")
    for index in (1, 2):
        mse, r2 = summarize_dataset(index, PAPER_PARAMS)
        print(f"附件{index}: MSE = {mse:.6g}, R² = {r2:.6f}")
