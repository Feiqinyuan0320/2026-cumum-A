---
project: "2026 CUMCM A题：药材的烘干问题"
handoff_target: "Astra"
task_scope: "仅完成第三问，并与已完成的第一、二问保持模型与数值口径一致"
status: "Q1/Q2 已完成；Q3 待运行"
preferred_language: "中文"
model_style: "物理机制 → 文献依据 → 本题适用性 → 模型 → 算法 → 结果 → 数值验证/合理性 → 局限"
---

# A题第三问 AI 交接包

## 0. 执行目标

请在**不改动第一、二问既定建模口径**的前提下，完成问题三：

1. 继续使用问题二的变物性一维径向热质耦合模型；
2. 求出药材内部所有位置均满足
   \[
   C(r,t)<0.15\ \mathrm{kg/kg}
   \]
   时的最早烘干时间 \(t_{\rm dry}\)；
3. 在论文中给出每隔 6 h、半径位置
   \[
   r=0,\ 0.5,\ 1.0,\ 1.5,\ 2.0\ \mathrm{cm}
   \]
   的水分浓度，并增加“烘干结束时间”一行；
4. 生成 `result3.xlsx`：
   - 时间输出：每 60 s；
   - 空间输出：每 0.1 cm；
   - 只保存水分浓度；
   - 保留四位小数；
5. 做必要的数值收敛检验，重点检验**烘干结束时间本身的稳定性**；
6. 给出适合论文正文使用的结果分析、图和局限说明。

---

# 1. 第三问题目要求

完成判据：

\[
C(r,t)<0.15\ \mathrm{kg/kg},\qquad \forall r\in[0,R].
\]

结束时间定义为：

\[
\boxed{
t_{\rm dry}
=
\inf\left\{
t:
\max_{0\le r\le R} C(r,t)<0.15
\right\}
}
\]

**不要直接假设圆柱中心一定是最后达标位置。**

程序中必须实际计算：

\[
C_{\max}(t)=\max_i C_i(t)
\]

再判断是否结束。

---

# 2. 已确定的几何与初值

\[
L=0.25\ \mathrm m,\qquad R=0.02\ \mathrm m
\]

\[
T(r,0)=28^\circ\mathrm C,\qquad C(r,0)=2.55
\]

其中 \(C\) 为干基含水率：

\[
C=\frac{m_w}{m_d}
\]

问题三继续按**固定几何**计算。问题四才处理半径收缩。

---

# 3. 问题二模型：第三问直接继承

\[
\boxed{
M_2:
\text{固定几何、变物性热质耦合模型}
}
\]

第三问不要另换 Page、Weibull 或纯经验动力学模型替代 PDE。若使用经验模型，只能作为辅助比较。

---

# 4. 附录3物性关系

\[
\rho(C)=650+128C
\]

\[
c_p(C)=1450+2736\frac{C}{C+1}
\]

\[
k(C)=0.21+0.38\frac{C}{C+1}
\]

\[
D(C,T_K)
=
2.4\times10^{-3}
\exp\left(-\frac{0.45}{C}\right)
\exp\left(-\frac{3850}{T_K}\right)
\]

其中：

\[
\boxed{T_K=T_{^\circ C}+273.15}
\]

强制注意：

- \(D\) 必须使用**药材局部绝对温度**；
- 不能直接代入摄氏温度；
- 不能用烘房温度代替药材局部温度。

---

# 5. 控制方程

温度场：

\[
\boxed{
\rho(C)c_p(C)
\frac{\partial T}{\partial t}
=
\frac1r
\frac{\partial}{\partial r}
\left[
rk(C)\frac{\partial T}{\partial r}
\right]
}
\]

水分场：

\[
\boxed{
\frac{\partial C}{\partial t}
=
\frac1r
\frac{\partial}{\partial r}
\left[
rD(C,T)\frac{\partial C}{\partial r}
\right]
}
\]

耦合结构：

\[
C\rightarrow(\rho,c_p,k)\rightarrow T
\]

\[
(T,C)\rightarrow D\rightarrow C
\]

---

# 6. 初始与边界条件

轴线：

\[
\left.T_r\right|_{r=0}=0,\qquad
\left.C_r\right|_{r=0}=0
\]

表面换热：

\[
-k(C_s)\left.T_r\right|_{r=R}
=
h_T(T_s-T_\infty)
\]

表面传质：

\[
-D(C_s,T_s)\left.C_r\right|_{r=R}
=
h_m(C_s-C_\infty)
\]

沿用：

\[
h_T=25\ \mathrm{W/(m^2K)},\qquad
h_m=8\times10^{-7}\ \mathrm{m/s}
\]

---

# 7. 外界水分浓度解释

附件1中的烘房“水分浓度”与药材干基含水率并非严格相同的热力学浓度定义。

统一口径：

> 将附件1中的烘房水分浓度视为题目规定浓度尺度下的**等效外界传质驱动力**，与给定 \(h_m\) 共同构成 Robin 边界。

不要在第三问将其改解释为真实空气绝对湿度、相对湿度或水活度。

---

# 8. 数值方法

核心参考：

**Da Silva W P, e Silva C M D P S, Gama F J A, 2014.**
*Estimation of thermo-physical properties of products with cylindrical shape during drying: The coupling between mass and heat.*

正确表述：

> Da Silva 等针对圆柱物料干燥建立表观液态扩散热质传递模型，并采用全隐式有限体积法离散一维圆柱扩散方程；本文借鉴其数值框架。

不要写成“Da Silva 提出了有限体积法”。

---

# 9. 有限体积离散

\[
V_i=
\pi L
\left(
r_{i+1/2}^2-r_{i-1/2}^2
\right)
\]

\[
A_{i\pm1/2}
=
2\pi Lr_{i\pm1/2}
\]

界面系数采用调和平均：

\[
k_{i+1/2}
=
\frac{2k_i k_{i+1}}{k_i+k_{i+1}}
\]

\[
D_{i+1/2}
=
\frac{2D_iD_{i+1}}{D_i+D_{i+1}}
\]

---

# 10. 表面 Robin 边界离散

不能把最后一个 cell center 当作真实表面。

热边界：

\[
q_R=
\frac{T_P-T_\infty}
{\Delta r/(2k_s)+1/h_T}
\]

\[
T_s=T_\infty+\frac{q_R}{h_T}
\]

水分边界：

\[
f_R=
\frac{C_P-C_\infty}
{\Delta r/(2D_s)+1/h_m}
\]

\[
C_s=C_\infty+\frac{f_R}{h_m}
\]

---

# 11. 时间推进与 Picard

时间离散：

\[
\text{Backward Euler}
\]

每个时间层：

\[
C^{(m)}
\rightarrow(\rho,c_p,k)
\rightarrow T^{(m+1)}
\]

\[
(T^{(m+1)},C^{(m)})
\rightarrow D
\rightarrow C^{(m+1)}
\]

线性三对角系统：Thomas 法。

第二问 Picard 容差：

\[
10^{-10}
\]

最大实际迭代次数：4。

---

# 12. 输出位置处理

轴心：

\[
u(0)\approx\frac{9u_1-u_2}{8}
\]

内部指定半径：

- 线性插值。

表面：

- 必须由 Robin 边界反算；
- 不要直接用最外层 cell center。

---

# 13. 第二问最终数值设置

\[
N=400
\]

\[
\Delta r=5\times10^{-5}\ \mathrm m
=
0.005\ \mathrm{cm}
\]

\[
\Delta t=0.0625\ \mathrm s
\]

\[
\varepsilon_{\rm Picard}=10^{-10}
\]

最大 Picard 次数：4。

---

# 14. 第二问收敛结果

空间网格：

\[
N=400\rightarrow800
\]

\[
E_T=6.6567\times10^{-6}\ ^\circ\mathrm C
\]

\[
E_C=5.0049\times10^{-6}
\]

时间步：

\[
0.125\rightarrow0.0625\ \mathrm s
\]

\[
E_T=9.2260\times10^{-5}\ ^\circ\mathrm C
\]

\[
E_C=5.7111\times10^{-6}
\]

---

# 15. 第二问回归测试值

位置顺序：

\[
r=[0,\ 0.5,\ 1.0,\ 1.5,\ 2.0]\ \mathrm{cm}
\]

0.5 h：

\[
T=[32.1893,32.3822,32.9660,33.9609,35.4131]
\]

\[
C=[2.5499,2.5489,2.5256,2.3257,1.6486]
\]

1 h：

\[
T=[40.3816,40.5536,41.0605,41.8782,42.9976]
\]

\[
C=[2.5257,2.4948,2.3578,2.0230,1.4711]
\]

1.5 h：

\[
T=[45.8467,45.9348,46.1929,46.6050,47.1400]
\]

\[
C=[2.3861,2.3256,2.1344,1.8020,1.3476]
\]

2 h：

\[
T=[48.4502,48.4880,48.5984,48.7735,49.0033]
\]

\[
C=[2.1709,2.1084,1.9236,1.6259,1.2311]
\]

2.5 h：

\[
T=[49.4670,49.4792,49.5136,49.5653,49.6609]
\]

\[
C=[1.9566,1.9006,1.7360,1.4720,1.1166]
\]

3 h：

\[
T=[49.8495,49.8553,49.8746,49.9101,49.9664]
\]

\[
C=[1.7662,1.7165,1.5702,1.3333,1.0081]
\]

新程序必须先复现这些结果，再跑长期第三问。

---

# 16. 已有文件

已有：

- `result2.xlsx`
  - 1–10800 s；
  - 每 1 s；
  - \(r=0,0.1,\ldots,2.0\) cm；
  - 两个工作表：
    - 温度
    - 水分浓度
  - 四位小数。

推荐先把新程序 0–3 h 结果与 `result2.xlsx` 自动做回归比较。

---

# 17. 第三问最关键的新问题：4 h 后边界延拓

附件1只到：

\[
14400\ \mathrm s=4\ \mathrm h
\]

但第三问可能持续 2–3 天。

附件1尾段大致稳定在：

\[
T_\infty\approx50^\circ\mathrm C
\]

\[
C_\infty\approx0.05
\]

第三问必须明确给出 \(t>4h\) 的边界延拓。

至少比较：

## 方案 A：末值延拓

\[
T_\infty(t)=T_\infty(14400)
\]

\[
C_\infty(t)=C_\infty(14400)
\]

## 方案 B：稳定尾段均值

取附件1最后 0.5–1 h 等稳定尾段：

\[
T_\infty^\ast=\operatorname{mean}(T_\infty)
\]

\[
C_\infty^\ast=\operatorname{mean}(C_\infty)
\]

然后长期固定。

推荐主方案：

\[
\boxed{\text{稳定尾段均值延拓}}
\]

末值延拓作为敏感性比较。

必须报告两种延拓对 \(t_{\rm dry}\) 的影响。

---

# 18. 长期时间步策略

第二问 \(\Delta t=0.0625\rm\,s\) 对 2–3 天计算代价很高。

允许第三问适当放大时间步，但必须重新做收敛检验。

推荐测试：

\[
\Delta t=0.25,\ 0.5,\ 1,\ 2,\ 5\ \mathrm s
\]

可根据运行效果调整。

重点比较：

\[
E_t=
\left|
t_{\rm dry}^{(\Delta t_a)}
-
t_{\rm dry}^{(\Delta t_b)}
\right|
\]

不要因为结果每60 s输出，就直接使用60 s作为积分时间步。

---

# 19. 烘干结束事件检测

每一步计算：

\[
C_{\max}(t)=\max_i C_i(t)
\]

找到第一次：

\[
C_{\max}(t_n)\ge0.15
\]

且：

\[
C_{\max}(t_{n+1})<0.15
\]

然后局部精化结束时间。

可采用：

- 缩小时间步重跑阈值附近区间；
- 或合理时间插值。

最终输出：

\[
t_{\rm dry}\ [\mathrm h]
\]

并说明事件检测精度。

---

# 20. result3.xlsx 格式

只保存水分浓度。

建议工作表：

`水分浓度`

首行：

`时间/s, 0, 0.1, 0.2, ..., 1.9, 2`

时间：

\[
60,120,180,\ldots
\]

直到覆盖最终烘干时间。

空间：

\[
0,0.1,0.2,\ldots,2.0\ \mathrm{cm}
\]

四位小数。

如有官方模板，优先匹配模板格式。

---

# 21. 论文表5

时间：

\[
6,12,18,24,\ldots
\]

直到烘干结束。

空间：

\[
r=0,\ 0.5,\ 1.0,\ 1.5,\ 2.0\ \mathrm{cm}
\]

最后添加实际“烘干结束时间”行。

---

# 22. 推荐图

正文优先：

1. \(C(t;r)\) 代表半径曲线，并画 \(C=0.15\) 阈值；
2. \(C_{\max}(t)\) 与 0.15 阈值交点图；
3. 可选 \(C(r,t)\) 时空图。

---

# 23. 物理解释重点

问题二初始尺度：

\[
\tau_T\approx0.767\rm\,h
\]

\[
\tau_C\approx19.69\rm\,h
\]

所以：

\[
\tau_T\ll\tau_C
\]

长期后期应重点解释：

\[
\boxed{\text{内部水分扩散逐渐成为主要限制}}
\]

不要提前写“中心一定最后达标”，要由数值结果确认。

---

# 24. 不可擅自改变的模型口径

## 不提前加入收缩

问题四才处理。

## 不强行做微观密度闭合

\[
\rho(C)=650+128C
\]

继续按题目给出的宏观有效物性处理。

不要自行引入孔隙率、固体真密度、渗透率等未给参数。

## 不直接加入潜热

当前：

\[
h_m(C_s-C_\infty)
\]

并不是已闭合的真实水质量通量，因此不能直接乘汽化潜热加入能量边界。

## 不把数值收敛叫实验验证

只能说明数值求解稳定。

---

# 25. 文献

核心：

Da Silva W P, e Silva C M D P S, Gama F J A.  
**Estimation of thermo-physical properties of products with cylindrical shape during drying: The coupling between mass and heat.**  
Journal of Food Engineering, 2014, 141:65–73.

中文背景：

王乐意，李长河，刘明政，等.  
**中药材干燥技术与装备研究现状**.  
农业工程学报, 2024, 40(2):1–28.

补充：

Tzempelikos D A, Mitrakos D, Vouros A P, et al.  
**Numerical modeling of heat and mass transfer during convective drying of cylindrical quince slices.**  
Journal of Food Engineering, 2015, 156:10–21.

---

# 26. Astra 执行顺序

1. 读取题目、附件1、`result2.xlsx`、当前问题一/二论文稿；
2. 复现问题二 0–3 h；
3. 与第15节数值做回归验证；
4. 分析附件1尾段稳定平台；
5. 构造 4 h 后恒温阶段边界；
6. 比较末值延拓与尾段均值延拓；
7. 测试长期积分时间步；
8. 运行至 \(C_{\max}<0.15\)；
9. 精化结束时间；
10. 生成表5；
11. 生成 `result3.xlsx`；
12. 生成核心图；
13. 写第三问正文。

---

# 27. 验收清单

- [ ] 使用附录3公式
- [ ] \(D\) 使用 Kelvin
- [ ] 0–3 h 与问题二结果一致
- [ ] 4 h 后边界有明确延拓依据
- [ ] 做边界延拓敏感性比较
- [ ] 用全域 \(C_{\max}\) 判定，不只看中心
- [ ] 严格满足所有位置 \(C<0.15\)
- [ ] \(t_{\rm dry}\) 有时间步收敛检验
- [ ] `result3.xlsx` 每60 s
- [ ] `result3.xlsx` 每0.1 cm
- [ ] 四位小数
- [ ] 表5每6 h
- [ ] 最终烘干时间单独一行
- [ ] 未提前加入收缩
- [ ] 未未经闭合加入潜热
- [ ] 未把数值收敛写成实验验证
- [ ] 论文结论与数值输出一致

---

# 28. 当前最重要的第三问判断

第三问真正新增的核心不是重新建立 PDE，而是：

\[
\boxed{
\text{如何把第二问模型合理延拓到长期恒温干燥阶段}
}
\]

以及：

\[
\boxed{
\text{如何严格确定首次满足全域 }C<0.15\text{ 的时间}
}
\]

主要精力应放在：

1. 长期边界延拓；
2. 全域达标判据；
3. 烘干结束事件检测；
4. 结束时间数值收敛；
5. `result3.xlsx` 规范生成。
