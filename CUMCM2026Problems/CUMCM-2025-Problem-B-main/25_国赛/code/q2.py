# -*- coding: utf-8 -*-
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import minimize, differential_evolution
import zhplot
from copy import deepcopy
from repro_utils import attachment_path

# ========== 常量与入射条件 ==========
eps_inf = 6.56
theta1 = 15 / 180 * np.pi  # 入射角（弧度）
n0 = 1.0  # 入射介质（空气）

# ========== 赝等离激元-晶格 (Lorentz + Drude) 介电函数 ==========
# 所有频率量纲均为 cm^-1；sigma 也是 cm^-1
omega_L = 970.0
omega_T = 798.0


def get_epsilon(sigma, gamma_L, gamma_T, omega_p, gamma_p):
    """
    sigma: cm^-1 (可为标量或 ndarray)
    其余参数: cm^-1
    返回: 复介电常数 ε(σ)
    """
    sigma = np.asarray(sigma, dtype=np.complex128)
    lattice = eps_inf * (
        (omega_L**2 - sigma**2 - 1j * gamma_L * sigma)
        / (omega_T**2 - sigma**2 - 1j * gamma_T * sigma)
    )
    drude = (omega_p**2) / (sigma**2 + 1j * gamma_p * sigma)
    return lattice - drude


def fresnel_rt_and_theta2(n_i, n_j, theta_i):
    """
    允许 n_j 为复数/数组；返回 (r_s, r_p, t_s, t_p, theta_j)
    """
    n_i = np.asarray(n_i, dtype=np.complex128)
    n_j = np.asarray(n_j, dtype=np.complex128)
    theta_i = np.asarray(theta_i, dtype=np.complex128)

    sin_theta_j = (n_i / n_j) * np.sin(theta_i)
    theta_j = np.arcsin(sin_theta_j)

    cos_i = np.cos(theta_i)
    cos_j = np.cos(theta_j)

    r_s = (n_i * cos_i - n_j * cos_j) / (n_i * cos_i + n_j * cos_j)
    t_s = (2 * n_i * cos_i) / (n_i * cos_i + n_j * cos_j)

    r_p = (n_j * cos_i - n_i * cos_j) / (n_j * cos_i + n_i * cos_j)
    t_p = (2 * n_i * cos_i) / (n_j * cos_i + n_i * cos_j)

    return r_s, r_p, t_s, t_p, theta_j


def get_I(sigma, d_um, gamma_L, gamma_T, omega_p1, gamma_p1, omega_p2, gamma_p2):
    """
    双光束近似：首反射 + 一次往返
    返回 非偏振反射率 R(σ) (0-1)
    """
    sigma = np.asarray(sigma, dtype=np.complex128)
    n1 = np.sqrt(get_epsilon(sigma, gamma_L, gamma_T, omega_p1, gamma_p1))  # 薄膜
    n2 = np.sqrt(get_epsilon(sigma, gamma_L, gamma_T, omega_p2, gamma_p2))  # 衬底

    r01s, r01p, t01s, t01p, theta2 = fresnel_rt_and_theta2(n0, n1, theta1)
    r12s, r12p, t12s, t12p, _ = fresnel_rt_and_theta2(n1, n2, theta2)
    r10s, r10p, t10s, t10p, _ = fresnel_rt_and_theta2(n1, n0, theta2)

    d_cm = d_um * 1e-4
    delta = 4 * np.pi * sigma * d_cm * n1 * np.cos(theta2)

    A_s = r01s + t01s * r12s * t10s * np.exp(1j * delta)
    A_p = r01p + t01p * r12p * t10p * np.exp(1j * delta)

    R = (np.abs(A_s) ** 2 + np.abs(A_p) ** 2) / 2.0
    return np.real_if_close(R)


# ========== 数据读取 ==========
def load_data(excel_path):
    """
    读取单个xlsx文件并返回处理后的数据
    返回: (sigma_data, y_data)
    """
    # 读取（含表头），两列：[sigma(cm^-1), 目标值(百分数)]
    df_raw = pd.read_excel(excel_path)

    # 尝试自动识别两列（容错：列名未知）
    # 将前两列转换为数值；非数值转为 NaN
    df = df_raw.iloc[:, :2].copy()
    df.columns = ["sigma", "y_percent"]
    df["sigma"] = pd.to_numeric(df["sigma"], errors="coerce")
    df["y_percent"] = pd.to_numeric(df["y_percent"], errors="coerce")

    # 丢弃无效行
    df = df.dropna(subset=["sigma", "y_percent"]).reset_index(drop=True)

    # 从"第二个数据点开始读取" → 跳过第一行有效数据
    if len(df) >= 2:
        df = df.iloc[1:].reset_index(drop=True)

    sigma_data = df["sigma"].to_numpy()
    y_data = df["y_percent"].to_numpy()  # 百分数形式（例如 30 表示 30%）

    return sigma_data, y_data


# 读取两个Excel文件。优先兼容原始的 ./attach/N.xlsx 布局；
# 若不存在，则读取仓库随附的 题目以及原始数据/附件/附件N.xlsx。
excel_path1 = attachment_path(1)
excel_path2 = attachment_path(2)

sigma_data1, y_data1 = load_data(excel_path1)
sigma_data2, y_data2 = load_data(excel_path2)

print(
    f"数据集1: {len(sigma_data1)} 个数据点, 波数范围: {sigma_data1.min():.1f} - {sigma_data1.max():.1f} cm⁻¹"
)
print(
    f"数据集2: {len(sigma_data2)} 个数据点, 波数范围: {sigma_data2.min():.1f} - {sigma_data2.max():.1f} cm⁻¹"
)


# ========== 目标函数（最小化残差平方和） ==========
def model_percent(sigma, params):
    d_um, gamma_L, gamma_T, omega_p1, gamma_p1, omega_p2, gamma_p2 = params
    R = get_I(sigma, d_um, gamma_L, gamma_T, omega_p1, gamma_p1, omega_p2, gamma_p2)
    return 100.0 * R  # 拟合目标是 R*100（百分数）


def loss_single(sigma_data, y_data, params):
    """计算单个数据集的loss"""
    y_hat = model_percent(sigma_data, params)
    # 对 NaN/Inf 做保护
    if not np.all(np.isfinite(y_hat)):
        return 1e12  # 返回一个非常大的值作为惩罚
    resid = y_hat - y_data
    return float(np.mean(resid**2))


def loss(params):
    """计算双数据集的总loss（等权重）"""
    loss1 = loss_single(sigma_data1, y_data1, params)
    loss2 = loss_single(sigma_data2, y_data2, params)

    # 如果任何一个数据集返回惩罚值，则返回惩罚值
    if loss1 >= 1e12 or loss2 >= 1e12:
        return 1e12

    # 等权重平均
    return (loss1 + loss2) / 2.0


# =========================================================================
# 关键修改：为 differential_evolution 创建一个可被 pickle 的函数
# 这个函数在顶层定义，并直接调用现有的 `loss` 函数
def de_loss_wrapper(params):
    return loss(params)


# =========================================================================

# ========== 初值与边界 ==========
# 你提供的近似初值：
x0 = np.array([6.4, 6.0, 6.0, 65.0, 55.0, 480.0, 420.0], dtype=float)

if __name__ == "__main__":
    # 边界（可根据你的样品实际情况再收紧/放宽）
    bounds = [
        (0.01, 100.0),  # d_um
        (0.1, 2000.0),  # gamma_L
        (0.1, 2000.0),  # gamma_T
        (1.0, 5000.0),  # omega_p1
        (0.1, 2000.0),  # gamma_p1
        (1.0, 5000.0),  # omega_p2
        (0.1, 2000.0),  # gamma_p2
    ]

    # ========== 全局 + 局部 拟合 ==========
    # 1) 全局搜索
    result_de = differential_evolution(
        func=de_loss_wrapper,  # <--- 这里修改了，使用 de_loss_wrapper
        bounds=bounds,
        strategy="best2bin",
        maxiter=300,
        popsize=40,
        tol=1e-2,
        polish=False,
        updating="deferred",
        workers=-1,  # 建议先从 workers=1 开始测试，确保一切正常
        # 如果需要加速，再改为 -1。
        # 此时，由于 de_loss_wrapper 是 def 定义的，应该不会有 pickle 错误。
        seed=42,
        disp=True,
    )

    # 2) 以全局结果为起点做局部细化
    result_local = minimize(
        fun=loss,  # minimize 函数没有多进程问题，可以直接用 loss 函数
        x0=result_de.x,
        method="L-BFGS-B",
        bounds=bounds,
        options=dict(maxiter=500, ftol=1e-12, gtol=1e-12),
    )
    best_params = result_local.x
    best_mse = result_local.fun

    param_names = [
        "d_um",
        "gamma_L",
        "gamma_T",
        "omega_p1",
        "gamma_p1",
        "omega_p2",
        "gamma_p2",
    ]
    print("===== 拟合完成 =====")
    for n, v in zip(param_names, best_params):
        print(f"{n:>9s} = {v:.6g}")
    print(f"总MSE (percent^2) = {best_mse:.6g}")

    # 计算各数据集的单独指标
    loss1 = loss_single(sigma_data1, y_data1, best_params)
    loss2 = loss_single(sigma_data2, y_data2, best_params)
    print(f"数据集1 MSE = {loss1:.6g}")
    print(f"数据集2 MSE = {loss2:.6g}")

    # 计算R²值
    def calculate_r2(y_true, y_pred):
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        return 1 - (ss_res / ss_tot)

    y_fit1 = model_percent(sigma_data1, best_params)
    y_fit2 = model_percent(sigma_data2, best_params)
    r2_1 = calculate_r2(y_data1, y_fit1)
    r2_2 = calculate_r2(y_data2, y_fit2)
    print(f"数据集1 R² = {r2_1:.6f}")
    print(f"数据集2 R² = {r2_2:.6f}")

    # ========== 可视化 ==========
    # 计算残差
    resid1 = y_fit1 - y_data1
    resid2 = y_fit2 - y_data2

    # 数据集1的拟合图
    plt.figure(figsize=(10, 6))
    plt.plot(
        sigma_data1, y_data1, "o", color="#a30543", ms=5, label="实验数据", alpha=0.7
    )
    plt.plot(sigma_data1, y_fit1, color="#297270", lw=3, label="拟合曲线")
    plt.gca().invert_xaxis()  # 红外谱常用：高到低
    plt.xlabel("波数 σ (cm$^{-1}$)", fontsize=16)
    plt.ylabel("反射率 (％)", fontsize=16)
    plt.title(f"附件1拟合结果 (R² = {r2_1:.4f})", fontsize=18)
    plt.legend(fontsize=14)
    plt.grid(True, alpha=0.3)
    plt.tick_params(labelsize=14)
    plt.tight_layout()
    plt.savefig("数据集1_拟合结果.png", dpi=300, bbox_inches="tight")
    plt.show()

    # 数据集2的拟合图
    plt.figure(figsize=(10, 6))
    plt.plot(
        sigma_data2, y_data2, "o", color="#a30543", ms=5, label="实验数据", alpha=0.7
    )
    plt.plot(sigma_data2, y_fit2, "#297270", lw=3, label="拟合曲线")
    plt.gca().invert_xaxis()  # 红外谱常用：高到低
    plt.xlabel("波数 σ (cm$^{-1}$)", fontsize=16)
    plt.ylabel("反射率 (％)", fontsize=16)
    plt.title(f"附件2拟合结果 (R² = {r2_2:.4f})", fontsize=18)
    plt.legend(fontsize=14)
    plt.grid(True, alpha=0.3)
    plt.tick_params(labelsize=14)
    plt.tight_layout()
    plt.savefig("数据集2_拟合结果.png", dpi=300, bbox_inches="tight")
    plt.show()

    # 数据集1的残差图
    plt.figure(figsize=(10, 4))
    plt.plot(sigma_data1, resid1, "o", color="#a30543", ms=4, alpha=0.7)
    plt.axhline(0, lw=2, color="#297270", linestyle="--")
    plt.gca().invert_xaxis()
    plt.xlabel("波数 σ (cm$^{-1}$)", fontsize=16)
    plt.ylabel("残差 (％)", fontsize=16)
    plt.title("附件1残差分析", fontsize=18)
    plt.grid(True, alpha=0.3)
    plt.tick_params(labelsize=14)
    plt.tight_layout()
    plt.savefig("数据集1_残差分析.png", dpi=300, bbox_inches="tight")
    plt.show()

    # 数据集2的残差图
    plt.figure(figsize=(10, 4))
    plt.plot(sigma_data2, resid2, "o", color="#a30543", ms=4, alpha=0.7)
    plt.axhline(0, lw=2, color="#297270", linestyle="--")
    plt.gca().invert_xaxis()
    plt.xlabel("波数 σ (cm$^{-1}$)", fontsize=16)
    plt.ylabel("残差 (％)", fontsize=16)
    plt.title("附件2残差分析", fontsize=18)
    plt.grid(True, alpha=0.3)
    plt.tick_params(labelsize=14)
    plt.tight_layout()
    plt.savefig("数据集2_残差分析.png", dpi=300, bbox_inches="tight")
    plt.show()

    # ========== 复介电常数图 ==========
    # 创建波数范围用于绘制复介电常数
    sigma_range = np.linspace(500, 3900, 3400)
    
    # 使用拟合得到的参数计算复介电常数
    epsilon_film = get_epsilon(sigma_range, best_params[1], best_params[2], best_params[3], best_params[4])
    epsilon_substrate = get_epsilon(sigma_range, best_params[1], best_params[2], best_params[5], best_params[6])
    
    # 计算复折射率 n = sqrt(epsilon)，然后取实部
    n_film = np.sqrt(epsilon_film).real
    n_substrate = np.sqrt(epsilon_substrate).real
    
    # 绘制折射率实部随波数的变化
    plt.figure(figsize=(10, 6))
    plt.plot(sigma_range, n_film, color="#297270", lw=3, label="外延层 n")
    plt.plot(sigma_range, n_substrate, color="#a30543", lw=3, label="衬底层 n")
    plt.gca().invert_xaxis()
    plt.xlabel("波数 σ (cm$^{-1}$)", fontsize=16)
    plt.ylabel("折射率 n", fontsize=16)
    plt.title("折射率随波数变化", fontsize=18)
    plt.legend(fontsize=14)
    plt.grid(True, alpha=0.3)
    plt.tick_params(labelsize=14)
    plt.tight_layout()
    plt.savefig("折射率_波数依赖性.png", dpi=300, bbox_inches="tight")
    plt.show()

    # ========== 灵敏度分析 ==========
    # 保存基准厚度
    baseline_thickness = best_params[0]
    
    # 1. 参数灵敏度分析 (eps_inf, omega_L, omega_T)
    print("\n--- 正在进行参数灵敏度分析 ---")
    
    # 参数扰动幅度
    variation = 0.02  # ±2%
    
    # 创建修改参数的函数
    def get_epsilon_modified(sigma, gamma_L, gamma_T, omega_p, gamma_p, eps_inf_mod=eps_inf, omega_L_mod=omega_L, omega_T_mod=omega_T):
        sigma = np.asarray(sigma, dtype=np.complex128)
        lattice = eps_inf_mod * (
            (omega_L_mod**2 - sigma**2 - 1j * gamma_L * sigma)
            / (omega_T_mod**2 - sigma**2 - 1j * gamma_T * sigma)
        )
        drude = (omega_p**2) / (sigma**2 + 1j * gamma_p * sigma)
        return lattice - drude
    
    def get_I_modified(sigma, d_um, gamma_L, gamma_T, omega_p1, gamma_p1, omega_p2, gamma_p2, eps_inf_mod=eps_inf, omega_L_mod=omega_L, omega_T_mod=omega_T):
        sigma = np.asarray(sigma, dtype=np.complex128)
        n1 = np.sqrt(get_epsilon_modified(sigma, gamma_L, gamma_T, omega_p1, gamma_p1, eps_inf_mod, omega_L_mod, omega_T_mod))
        n2 = np.sqrt(get_epsilon_modified(sigma, gamma_L, gamma_T, omega_p2, gamma_p2, eps_inf_mod, omega_L_mod, omega_T_mod))

        r01s, r01p, t01s, t01p, theta2 = fresnel_rt_and_theta2(n0, n1, theta1)
        r12s, r12p, t12s, t12p, _ = fresnel_rt_and_theta2(n1, n2, theta2)
        r10s, r10p, t10s, t10p, _ = fresnel_rt_and_theta2(n1, n0, theta2)

        d_cm = d_um * 1e-4
        delta = 4 * np.pi * sigma * d_cm * n1 * np.cos(theta2)

        A_s = r01s + t01s * r12s * t10s * np.exp(1j * delta)
        A_p = r01p + t01p * r12p * t10p * np.exp(1j * delta)

        R = (np.abs(A_s) ** 2 + np.abs(A_p) ** 2) / 2.0
        return np.real_if_close(R)
    
    def model_percent_modified(sigma, params, eps_inf_mod=eps_inf, omega_L_mod=omega_L, omega_T_mod=omega_T):
        d_um, gamma_L, gamma_T, omega_p1, gamma_p1, omega_p2, gamma_p2 = params
        R = get_I_modified(sigma, d_um, gamma_L, gamma_T, omega_p1, gamma_p1, omega_p2, gamma_p2, eps_inf_mod, omega_L_mod, omega_T_mod)
        return 100.0 * R
    
    def loss_modified(params, eps_inf_mod=eps_inf, omega_L_mod=omega_L, omega_T_mod=omega_T):
        loss1 = loss_single_modified(sigma_data1, y_data1, params, eps_inf_mod, omega_L_mod, omega_T_mod)
        loss2 = loss_single_modified(sigma_data2, y_data2, params, eps_inf_mod, omega_L_mod, omega_T_mod)
        if loss1 >= 1e12 or loss2 >= 1e12:
            return 1e12
        return (loss1 + loss2) / 2.0
    
    def loss_single_modified(sigma_data, y_data, params, eps_inf_mod=eps_inf, omega_L_mod=omega_L, omega_T_mod=omega_T):
        y_hat = model_percent_modified(sigma_data, params, eps_inf_mod, omega_L_mod, omega_T_mod)
        if not np.all(np.isfinite(y_hat)):
            return 1e12
        resid = y_hat - y_data
        return float(np.mean(resid**2))
    
    # 进行参数扰动分析
    param_variations = {
        'eps_inf_minus': eps_inf * (1 - variation),
        'eps_inf_plus': eps_inf * (1 + variation),
        'omega_L_minus': omega_L * (1 - variation),
        'omega_L_plus': omega_L * (1 + variation),
        'omega_T_minus': omega_T * (1 - variation),
        'omega_T_plus': omega_T * (1 + variation)
    }
    
    thickness_variations = []
    labels = []
    
    for name, value in param_variations.items():
        if 'eps_inf' in name:
            result = minimize(lambda x: loss_modified(x, eps_inf_mod=value), 
                            x0=best_params, method="L-BFGS-B", bounds=bounds)
        elif 'omega_L' in name:
            result = minimize(lambda x: loss_modified(x, omega_L_mod=value), 
                            x0=best_params, method="L-BFGS-B", bounds=bounds)
        elif 'omega_T' in name:
            result = minimize(lambda x: loss_modified(x, omega_T_mod=value), 
                            x0=best_params, method="L-BFGS-B", bounds=bounds)
        
        thickness_change = (result.x[0] - baseline_thickness) / baseline_thickness * 100
        thickness_variations.append(thickness_change)
        labels.append(name.replace('_', ' '))
    
    # 绘制参数灵敏度分析图
    plt.figure(figsize=(10, 6))
    colors = ['#e66d50', '#297270', '#e66d50', '#297270', '#e66d50', '#297270']
    bars = plt.bar(labels, thickness_variations, color=colors, alpha=0.7)
    plt.axhline(0, color='black', linestyle='--', alpha=0.5)
    plt.ylabel('薄膜厚度变化 (%)', fontsize=16)
    plt.title(f'参数灵敏度分析 (扰动幅度: ±{variation*100}%)', fontsize=18)
    plt.xticks(rotation=45, fontsize=12)
    plt.tick_params(labelsize=14)
    for bar, val in zip(bars, thickness_variations):
        plt.text(bar.get_x() + bar.get_width()/2.0, val + (0.01 if val >= 0 else -0.03), 
                f'{val:.3f}%', ha='center', va='bottom' if val >= 0 else 'top', fontsize=12)
    plt.tight_layout()
    plt.savefig("参数灵敏度分析.png", dpi=300, bbox_inches="tight")
    plt.show()

    # 2. 数据噪声稳健性分析 (蒙特卡洛)
    print("\n--- 正在进行噪声稳健性分析 ---")
    
    num_simulations = 100
    noise_level = 0.5  # 反射率噪声的标准差为0.5%
    noisy_thicknesses = []
    
    for i in range(num_simulations):
        # 为两个数据集添加噪声
        noisy_y_data1 = y_data1 + np.random.normal(0, noise_level, len(y_data1))
        noisy_y_data2 = y_data2 + np.random.normal(0, noise_level, len(y_data2))
        
        # 定义噪声情况下的loss函数
        def loss_noisy(params):
            loss1 = loss_single_noisy(sigma_data1, noisy_y_data1, params)
            loss2 = loss_single_noisy(sigma_data2, noisy_y_data2, params)
            if loss1 >= 1e12 or loss2 >= 1e12:
                return 1e12
            return (loss1 + loss2) / 2.0
        
        def loss_single_noisy(sigma_data, y_data_noisy, params):
            y_hat = model_percent(sigma_data, params)
            if not np.all(np.isfinite(y_hat)):
                return 1e12
            resid = y_hat - y_data_noisy
            return float(np.mean(resid**2))
        
        # 进行拟合
        result = minimize(loss_noisy, x0=best_params, method="L-BFGS-B", bounds=bounds)
        noisy_thicknesses.append(result.x[0])
        print(f"\r模拟 {i+1}/{num_simulations}", end="")
    
    print("\n模拟完成。")
    
    # 计算统计量
    thickness_changes = [(t - baseline_thickness) / baseline_thickness * 100 for t in noisy_thicknesses]
    mean_change = np.mean(thickness_changes)
    std_change = np.std(thickness_changes)
    
    # 绘制噪声稳健性分析图
    plt.figure(figsize=(10, 6))
    plt.hist(thickness_changes, bins=20, color="#e9f4a3", edgecolor='black', alpha=0.7)
    plt.axvline(0, color='#e66d50', linestyle='--', label=f'基准厚度: {baseline_thickness:.4f} μm')
    plt.axvline(mean_change, color='#297270', linestyle=':', label=f'噪声下均值变化: {mean_change:.3f}%')
    plt.xlabel('薄膜厚度变化 (%)', fontsize=16)
    plt.ylabel('频数', fontsize=16)
    plt.title(f'噪声稳健性分析 (N={num_simulations}, 噪声 σ={noise_level}%)', fontsize=18)
    plt.legend(fontsize=14)
    plt.tick_params(labelsize=14)
    plt.text(0.02, 0.95, f'标准差: {std_change:.3f}%', transform=plt.gca().transAxes, 
             bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8), fontsize=12)
    plt.tight_layout()
    plt.savefig("噪声稳健性分析.png", dpi=300, bbox_inches="tight")
    plt.show()

    print("=" * 50)
    print("灵敏度分析完成")
    print(f"基准薄膜厚度: {baseline_thickness:.4f} μm")
    print(f"噪声影响 - 均值变化: {mean_change:.3f}%, 标准差: {std_change:.3f}%")
    print("=" * 50)

    print("=" * 50)
    print("图片已保存：")
    print("- 数据集1_拟合结果.png")
    print("- 数据集2_拟合结果.png")
    print("- 数据集1_残差分析.png")
    print("- 数据集2_残差分析.png")
    print("- 折射率_波数依赖性.png")
    print("- 参数灵敏度分析.png")
    print("- 噪声稳健性分析.png")
    print("=" * 50)
