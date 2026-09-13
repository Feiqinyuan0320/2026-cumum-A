import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import zhplot  
from repro_utils import attachment_path
COLOR_PALETTE = {
    "dark_teal": "#274753",  # 深青色
    "medium_teal": "#297270",  # 中青色
    "teal": "#299d8f",  # 青色
    "sage_green": "#8ab07c",  # 鼠尾草绿
    "gold": "#e7c66b",  # 金色
    "orange": "#f3a361",  # 橙色
    "coral": "#e66d50",  # 珊瑚色
}
def sellmeier_silicon(wavenumber_cm):
    wavelength_um = 1 / (wavenumber_cm * 1e-4)

    B1, B2, B3 = 10.6684293, 0.0030434748, 1.54133408
    C1, C2, C3 = 0.09091219, 1.28766018, 1218816

    lambda_sq = wavelength_um**2

    n_sq = (
        1
        + (B1 * lambda_sq) / (lambda_sq - C1)
        + (B2 * lambda_sq) / (lambda_sq - C2)
        + (B3 * lambda_sq) / (lambda_sq - C3)
    )

    return np.sqrt(n_sq)


def quadratic_peak_interpolation(y_values, x_values):
    if len(y_values) != 3 or len(x_values) != 3:
        raise ValueError("需要且仅需要三个点来进行二次插值。")

    A = np.vstack([x_values**2, x_values, np.ones(3)]).T
    a, b, c = np.linalg.solve(A, y_values)

    return -b / (2 * a), (a, b, c)


def perform_fft_analysis(filename, angle_deg, num_points=8192):

    df = pd.read_excel(filename, header=None)
    wavenumber_raw = pd.to_numeric(df.iloc[:, 0], errors="coerce").values
    reflectance_raw = pd.to_numeric(df.iloc[:, 1], errors="coerce").values
    valid_mask = ~np.isnan(wavenumber_raw) & ~np.isnan(reflectance_raw)
    wavenumber_raw, reflectance_raw = (
        wavenumber_raw[valid_mask],
        reflectance_raw[valid_mask],
    )

    n_values = sellmeier_silicon(wavenumber_raw)
    sin_theta_i_sq = np.sin(np.deg2rad(angle_deg)) ** 2
    x_domain_nonuniform = 2 * wavenumber_raw * np.sqrt(n_values**2 - sin_theta_i_sq)

    x_domain_uniform = np.linspace(
        x_domain_nonuniform.min(), x_domain_nonuniform.max(), num_points
    )
    reflectance_uniform_in_x = np.interp(
        x_domain_uniform, x_domain_nonuniform, reflectance_raw
    )

    window = np.hanning(num_points)
    windowed_signal = (
        reflectance_uniform_in_x - np.mean(reflectance_uniform_in_x)
    ) * window

    fft_result = np.fft.fft(windowed_signal)
    fft_amplitude = np.abs(fft_result)
    delta_x = x_domain_uniform[1] - x_domain_uniform[0]
    fft_freq_d_cm = np.fft.fftfreq(num_points, d=delta_x)

    min_d_um = 2.0
    positive_mask = (fft_freq_d_cm * 1e4) > min_d_um
    peak_idx_rough = np.argmax(fft_amplitude[positive_mask])
    peak_idx_global = np.where(positive_mask)[0][peak_idx_rough]
    indices_to_fit = np.array(
        [peak_idx_global - 1, peak_idx_global, peak_idx_global + 1]
    )
    d_values_to_fit = fft_freq_d_cm[indices_to_fit]
    amp_values_to_fit = fft_amplitude[indices_to_fit]
    d_cm_precise, parabola_coeffs = quadratic_peak_interpolation(
        amp_values_to_fit, d_values_to_fit
    )
    d_um = d_cm_precise * 1e4


    return {
        "filename": filename,
        "d_um": d_um,
        "x_domain_uniform": x_domain_uniform,
        "reflectance_uniform_in_x": reflectance_uniform_in_x,
        "fft_freq_d_um": fft_freq_d_cm * 1e4,  
        "fft_amplitude": fft_amplitude,
        "positive_mask": positive_mask,
        "d_values_to_fit_um": d_values_to_fit * 1e4,  
        "amp_values_to_fit": amp_values_to_fit,
        "parabola_coeffs": parabola_coeffs,
    }


def plot_fft_details(ax, data, title):
    ax.plot(
        data["fft_freq_d_um"][data["positive_mask"]],
        data["fft_amplitude"][data["positive_mask"]],
        "o--",
        color="#4965b0",
        markersize=6,
        linewidth=2,
        label="FFT 频谱 (离散点)",
    )
    
    ax.fill_between(
        data["fft_freq_d_um"][data["positive_mask"]],
        data["fft_amplitude"][data["positive_mask"]],
        alpha=0.3,
        color="#cfeaf1",
        label="FFT 频谱区域"
    )

    ax.plot(
        data["d_values_to_fit_um"],
        data["amp_values_to_fit"],
        "o",
        color="#a30543",
        markersize=10,
        label="用于二次插值的三个关键点",
    )

    a, b, c = data["parabola_coeffs"]
    a_um = a / 1e8
    b_um = b / 1e4
    d_fine_grid_um = np.linspace(
        data["d_values_to_fit_um"].min(), data["d_values_to_fit_um"].max(), 100
    )
    parabola_y = a_um * d_fine_grid_um**2 + b_um * d_fine_grid_um + c
    ax.plot(
        d_fine_grid_um,
        parabola_y,
        "-",
        color="#f36f43",
        linewidth=3,
        label=f"二次插值拟合抛物线",
    )

    ax.axvline(data["d_um"], color="crimson", ls="-.", lw=3)

    ax.set_title(title, fontsize=16)
    ax.set_xlabel("厚度 d (μm)", fontsize=12)
    ax.set_ylabel("FFT 振幅", fontsize=12)

    zoom_range = 1.5
    ax.set_xlim(data["d_um"] - zoom_range, data["d_um"] + zoom_range)

    ax.grid(True, linestyle="--", alpha=0.6)
    ax.legend(fontsize=10)


if __name__ == "__main__":
    data_f3 = perform_fft_analysis(filename=attachment_path(3), angle_deg=10)
    data_f4 = perform_fft_analysis(filename=attachment_path(4), angle_deg=15)
    avg_d = (data_f3["d_um"] + data_f4["d_um"]) / 2

    print("===== 色散校正 FFT 厚度结果 =====")
    print(f"附件3 (10°) d3 = {data_f3['d_um']:.4f} μm")
    print(f"附件4 (15°) d4 = {data_f4['d_um']:.4f} μm")
    print(f"平均厚度 d = {avg_d:.4f} μm")

    plt.rcParams["font.sans-serif"] = ["SimHei"]  # 设置中文字体
    plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示问题

    fig1, ax1 = plt.subplots(1, 1, figsize=(10, 6))
    
    ax1.plot(
        data_f3["x_domain_uniform"],
        data_f3["reflectance_uniform_in_x"],
        label="在新坐标域(x)重采样后的信号",
        color="teal",
        linewidth=2.5
    )
    ax1.set_title("经坐标变换后的完美周期信号 (以附件3为例)", fontsize=20, fontweight='bold')
    ax1.set_xlabel("新坐标 x = 2σ sqrt(n²-sin²θ) (cm^-1)", fontsize=16)
    ax1.set_ylabel("反射率 (%)", fontsize=16)
    ax1.grid(True, linestyle="--", alpha=0.6)
    ax1.legend(fontsize=14)
    ax1.tick_params(axis='both', which='major', labelsize=14)

    plt.tight_layout()
    plt.savefig("坐标变换后的周期信号.png", dpi=300, bbox_inches='tight')
    plt.close()

    fig2, axes = plt.subplots(2, 1, figsize=(10, 10))

    plot_fft_details(axes[0], data_f3, title="附件3 (10° 入射角) FFT频谱分析")
    
    plot_fft_details(axes[1], data_f4, title="附件4 (15° 入射角) FFT频谱分析")

    fig2.tight_layout(pad=3.0)
    plt.savefig("FFT频谱分析结果.png", dpi=300, bbox_inches='tight')
    plt.close()
