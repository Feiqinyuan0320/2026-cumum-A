import numpy as np
import matplotlib.pyplot as plt
import zhplot


class SiThicknessEstimator:
    def __init__(self):
        print("初始化基于干涉极值点法的厚度估算器...")

    def calculate_n_si(self, nu_cm):
        nu = np.asarray(nu_cm, dtype=float)
        B1, C1 = 10.6684293, 0.0909121907
        B2, C2 = 0.0030434748, 1.287660172
        B3, C3 = 1.54133408, 1.218816e6
        
        n2 = (
            1.0
            + (B1 * 1e8) / (1e8 - C1 * nu**2)
            + (B2 * 1e8) / (1e8 - C2 * nu**2)
            + (B3 * 1e8) / (1e8 - C3 * nu**2)
        )
        return np.sqrt(n2)

    def estimate_thickness(self, extrema_points, angle_deg, m_range=range(1, 40)):
        print(f"\n{'='*25} 开始估算厚度 (入射角: {angle_deg}°) {'='*25}")
        
        best_m_start = -1
        min_std_dev = float('inf')
        best_results = {}
        
        all_std_devs = []

        for m_start in m_range:
            d_values = []
            for i, point in enumerate(extrema_points):
                wavenumber = point['wavenumber']
                if extrema_points[0]['type'] == 'peak':
                    order = m_start + i / 2.0
                else: 
                    order = m_start + (i+1) / 2.0

                
                n1 = self.calculate_n_si(wavenumber)
                theta0_rad = np.radians(angle_deg)
                
                theta1_rad = np.arcsin(np.sin(theta0_rad) / n1)
                
                d = order / (2 * n1 * np.cos(theta1_rad) * wavenumber * 1e-4)
                d_values.append(d)

            std_dev = np.std(d_values)
            all_std_devs.append(std_dev)
            
            if std_dev < min_std_dev:
                min_std_dev = std_dev
                best_m_start = m_start
                best_results = {
                    'best_m_start': best_m_start,
                    'avg_thickness_um': np.mean(d_values),
                    'min_std_dev': min_std_dev,
                    'thickness_values': d_values,
                }
        
        self.plot_std_dev_vs_m(m_range, all_std_devs, best_results, angle_deg)
        
        return best_results

    def plot_std_dev_vs_m(self, m_range, std_devs, best_results, angle_deg):
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(m_range, std_devs, 'o-', markersize=4, label='厚度计算值的标准差')
        ax.axvline(best_results['best_m_start'], color='r', linestyle='--', 
                   label=f'最优解 m0 = {best_results["best_m_start"]}')
        ax.set_xlabel('假定的初始干涉级数 (m)', fontsize=16)
        ax.set_ylabel('计算厚度 d 的标准差 (μm)', fontsize=16)
        ax.set_title(f'厚度一致性分析 (入射角 {angle_deg}°)', fontsize=18, fontweight='bold')
        ax.grid(True)
        ax.legend(fontsize=14)
        ax.tick_params(axis='both', which='major', labelsize=14)
        plt.tight_layout()
        plt.savefig(f"厚度一致性分析_{angle_deg}度.png", dpi=300)
        print(f"✅ 厚度一致性分析图已保存。")
        if "agg" not in plt.get_backend().lower():
            plt.show()
        plt.close(fig)

if __name__ == '__main__':
    extrema_points_3 = [
        {'wavenumber': 750.1736, 'reflectance': 70.957828}, {'wavenumber': 940.6096, 'reflectance': 0.134385},
        {'wavenumber': 1105.494, 'reflectance': 55.786779}, {'wavenumber': 1312.804, 'reflectance': 11.654351},
        {'wavenumber': 1508.061, 'reflectance': 39.33095}, {'wavenumber': 1722.603, 'reflectance': 20.771007},
        {'wavenumber': 1927.02, 'reflectance': 33.108994}, {'wavenumber': 2144.937, 'reflectance': 24.514375},
        {'wavenumber': 2378.764, 'reflectance': 30.360874}, {'wavenumber': 2564.861, 'reflectance': 26.210183},
        {'wavenumber': 2779.885, 'reflectance': 29.43295}, {'wavenumber': 2993.462, 'reflectance': 27.052822},
        {'wavenumber': 3203.665, 'reflectance': 28.874511}, {'wavenumber': 3465.455, 'reflectance': 27.624775},
        {'wavenumber': 3650.587, 'reflectance': 28.630007}, {'wavenumber': 3913.341, 'reflectance': 27.896136},
    ]
    for i, point in enumerate(extrema_points_3): point['type'] = 'peak' if i % 2 == 0 else 'trough'

    extrema_points_4 = [
        {'wavenumber': 574.201, 'reflectance': 3.8458416}, {'wavenumber': 749.2094, 'reflectance': 78.781032},
        {'wavenumber': 946.395, 'reflectance': 0.3493311}, {'wavenumber': 1108.386, 'reflectance': 60.657749},
        {'wavenumber': 1324.375, 'reflectance': 13.301342}, {'wavenumber': 1519.15, 'reflectance': 43.048557},
        {'wavenumber': 1736.102, 'reflectance': 22.879293}, {'wavenumber': 1941.966, 'reflectance': 36.174206},
        {'wavenumber': 2160.847, 'reflectance': 26.795459}, {'wavenumber': 2387.442, 'reflectance': 33.288474},
        {'wavenumber': 2587.038, 'reflectance': 28.637388}, {'wavenumber': 2802.544, 'reflectance': 32.164834},
        {'wavenumber': 3035.889, 'reflectance': 29.60452}, {'wavenumber': 3245.127, 'reflectance': 31.675433},
        {'wavenumber': 3450.027, 'reflectance': 30.238529}, {'wavenumber': 3676.14, 'reflectance': 31.571544}
    ]
    for i, point in enumerate(extrema_points_4): point['type'] = 'trough' if i % 2 == 0 else 'peak'

    estimator = SiThicknessEstimator()
    
    results_3 = estimator.estimate_thickness(extrema_points_3, angle_deg=10, m_range=range(1, 15))
    
    results_4 = estimator.estimate_thickness(extrema_points_4, angle_deg=15, m_range=range(1, 15))

    d3 = results_3['avg_thickness_um']
    d4 = results_4['avg_thickness_um']
    
    avg_d = (d3 + d4) / 2
    diff_percent = abs(d3 - d4) / avg_d * 100 if avg_d > 0 else 0

    print("\n===== 干涉极值点法厚度结果 =====")
    print(f"附件3 (10°) d3 = {d3:.4f} μm")
    print(f"附件4 (15°) d4 = {d4:.4f} μm")
    print(f"平均厚度 d = {avg_d:.4f} μm")
    print(f"两角度差异 = {diff_percent:.2f}%")
