"""Independent Q1 finite-volume calculation; inputs are read-only.
Run with /opt/anaconda3/bin/python. Outputs use the same name as the run label.
"""
from pathlib import Path
import argparse, hashlib, json, time
import numpy as np
import openpyxl
from numba import njit

ROOT = Path(__file__).resolve().parent
INPUT = ROOT.parents[1] / '附件/烘干初期各时间点烘房温度和水分浓度.xlsx'
R = .02
RHOCP = 820.0 * 2600.0
K = .36
HT = 25.0
HM = 8e-7

@njit(cache=True)
def diffusivity(c):
    return 7e-9 * np.exp(-.89 / c)

@njit(cache=True)
def solve_tri(lower, diag, upper, rhs):
    n = len(diag)
    c = np.empty(n)
    d = np.empty(n)
    c[0] = upper[0] / diag[0]
    d[0] = rhs[0] / diag[0]
    for i in range(1, n):
        pivot = diag[i] - lower[i] * c[i-1]
        c[i] = upper[i] / pivot
        d[i] = (rhs[i] - lower[i] * d[i-1]) / pivot
    x = np.empty(n)
    x[-1] = d[-1]
    for i in range(n-2, -1, -1):
        x[i] = d[i] - c[i] * x[i+1]
    return x

@njit(cache=True)
def conductance(u, surface, dr, is_heat, improved):
    n = len(u)
    g = np.empty(n + 1)
    g[0] = 0.0
    for i in range(1, n):
        if is_heat:
            d = K
        else:
            dl, de = diffusivity(u[i-1]), diffusivity(u[i])
            d = 2 * dl * de / (dl + de)
        g[i] = (i * dr) * d / dr
    if is_heat:
        d, h = K, HT
    else:
        h = HM
        if improved:
            # Simpson approximation to the secant of the Kirchhoff transform.
            d = (diffusivity(u[-1]) + 4*diffusivity((u[-1]+surface)/2)
                 + diffusivity(surface)) / 6
        else:
            d = diffusivity(surface)
    distance = R*np.log(R/(R-dr/2)) if improved else dr/2
    g[n] = R / (distance/d + 1/h)
    return g

@njit(cache=True)
def rhs_diff(u, ambient, g):
    n = len(u)
    f = np.zeros(n)
    for i in range(n-1):
        flow = g[i+1]*(u[i+1]-u[i])
        f[i] += flow
        f[i+1] -= flow
    f[-1] += g[n]*(ambient-u[-1])
    return f

@njit(cache=True)
def step(old, prev, surf, ambient, volume, dr, dt, a0, is_heat,
         improved, tolerance):
    n = len(old)
    capacity = RHOCP if is_heat else 1.0
    h = HT if is_heat else HM
    current = old.copy()
    previous_surface = surf
    lower, upper, diag = np.zeros(n), np.zeros(n), np.zeros(n)
    rhs = np.zeros(n)
    increment = np.zeros(n)
    for iteration in range(1, 101):
        g = conductance(current, previous_surface, dr, is_heat, improved)
        f_old = rhs_diff(old, ambient, g)
        for i in range(n):
            mass = capacity*volume[i]/dt
            lower[i] = -g[i]
            upper[i] = -g[i+1] if i < n-1 else 0.0
            diag[i] = a0*mass + g[i] + g[i+1]
            rhs[i] = f_old[i] + (a0-1.0)*mass*(old[i]-prev[i])
        increment = solve_tri(lower, diag, upper, rhs)
        new = old + increment
        new_surface = ambient + g[n]*(new[-1]-ambient)/(R*h)
        difference = abs(new_surface-previous_surface)
        for i in range(n):
            difference = max(difference, abs(new[i]-current[i]))
        current = new
        previous_surface = new_surface
        if is_heat or difference < tolerance:
            break
    if iteration == 100:
        raise ValueError('nonlinear iteration failed')
    # Recompute all coefficients at the converged iterate, independently of
    # the coefficients used in the final linear solve.
    g_final = conductance(current, previous_surface, dr, is_heat, improved)
    f_final = rhs_diff(current, ambient, g_final)
    flux = g_final[n]*(current[-1]-ambient) / R
    storage_sum, storage_abs = 0.0, 0.0
    eq_error, eq_scale = 0.0, 0.0
    for i in range(n):
        storage = capacity*volume[i]*(a0*increment[i]-(a0-1)*(old[i]-prev[i]))/dt
        storage_sum += storage
        storage_abs += abs(storage)
        eq_error = max(eq_error, abs(storage-f_final[i]))
        eq_scale = max(eq_scale, abs(storage), abs(f_final[i]))
    # Geometry in calculations is divided by 2*pi*L. Restore physical units.
    geo = 2*np.pi*.25
    balance_abs = abs(storage_sum+R*flux)*geo
    scale = max(storage_abs, abs(R*flux), 1e-30)*geo
    balance_rel = balance_abs/scale
    surface_error = abs(h*(previous_surface-ambient)-flux)
    return (current, previous_surface, iteration,
            np.array([balance_abs, balance_rel, eq_error/max(eq_scale,1e-30), surface_error]))

@njit(cache=True)
def sample(u, surface, dr):
    out = np.empty(21)
    # The discrete unknown is interpreted as the cell-centre point value.
    out[0] = (9*u[0]-u[1])/8
    out[20] = surface
    for j in range(1,20):
        x = j*.001/dr-.5
        i = int(np.floor(x))
        fraction = x-i
        out[j] = u[i]*(1-fraction)+u[i+1]*fraction
    return out

@njit(cache=True)
def run(n, dt, end, data, bdf2, improved, tolerance, equilibrium):
    dr = R/n
    volume = np.empty(n)
    for i in range(n):
        volume[i] = ((i+1)**2-i**2)*dr**2/2
    temp = np.full(n,28.0)
    water = np.full(n,2.55)
    tp, cp = temp.copy(), water.copy()
    ts, cs = 28.0, 2.55
    outputs_t = np.empty((int(end)+1,21))
    outputs_c = np.empty_like(outputs_t)
    outputs_t[0,:] = 28
    outputs_c[0,:] = 2.55
    max_metrics = np.zeros((2,4))
    max_iterations = 0
    min_c, max_c = 2.55, 2.55
    min_t, max_t = 28.0, 28.0
    extrema_checks = np.zeros(6)
    sample_every = int(round(1/dt))
    for it in range(1,int(round(end/dt))+1):
        t = it*dt
        j = min(int(t/60),29)
        fraction = (t-data[j,0])/(data[j+1,0]-data[j,0])
        ambient_t = data[j,1]+fraction*(data[j+1,1]-data[j,1])
        ambient_c = data[j,2]+fraction*(data[j+1,2]-data[j,2])
        if equilibrium:
            ambient_t, ambient_c = 28.0, 2.55
        a0 = 1.5 if bdf2 and it > 1 else 1.0
        tr = step(temp,tp,ts,ambient_t,volume,dr,dt,a0,True,improved,tolerance)
        cr = step(water,cp,cs,ambient_c,volume,dr,dt,a0,False,improved,tolerance)
        for h in range(4):
            max_metrics[0,h] = max(max_metrics[0,h],tr[3][h])
            max_metrics[1,h] = max(max_metrics[1,h],cr[3][h])
        max_iterations = max(max_iterations,cr[2])
        # All time steps and all discrete cells, not merely 35 paper points.
        for i in range(n):
            extrema_checks[0]=max(extrema_checks[0],temp[i]-tr[0][i])
            extrema_checks[1]=max(extrema_checks[1],cr[0][i]-water[i])
            if i < n-1:
                extrema_checks[2]=max(extrema_checks[2],tr[0][i]-tr[0][i+1])
                extrema_checks[3]=max(extrema_checks[3],cr[0][i+1]-cr[0][i])
        extrema_checks[4]=max(extrema_checks[4],tr[1]-ambient_t)
        extrema_checks[5]=max(extrema_checks[5],cr[1]-cr[0][-1])
        tp, cp = temp, water
        temp,water,ts,cs = tr[0],cr[0],tr[1],cr[1]
        min_c,min_t=min(min_c,cs,np.min(water)),min(min_t,ts,np.min(temp))
        max_c,max_t=max(max_c,cs,np.max(water)),max(max_t,ts,np.max(temp))
        if it%sample_every==0:
            k=int(round(t))
            outputs_t[k,:]=sample(temp,ts,dr)
            outputs_c[k,:]=sample(water,cs,dr)
    return (outputs_t,outputs_c,max_metrics,max_iterations,
            np.array([min_t,max_t,min_c,max_c]),extrema_checks)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--n',type=int,default=1600)
    parser.add_argument('--dt',type=float,default=1/64)
    parser.add_argument('--end',type=int,default=1800)
    parser.add_argument('--scheme',choices=['be','bdf2'],default='be')
    parser.add_argument('--boundary',choices=['original','integrated'],default='original')
    parser.add_argument('--tol',type=float,default=1e-10)
    parser.add_argument('--label',default='original_1600_64')
    parser.add_argument('--equilibrium',action='store_true')
    args=parser.parse_args()
    assert args.n>=40 and 0<args.end<=1800
    assert abs(round(1/args.dt)*args.dt-1)<1e-12
    wb=openpyxl.load_workbook(INPUT,read_only=True,data_only=True)
    all_data=np.array(list(wb.active.values)[1:],dtype=float)
    data=all_data[all_data[:,0]<=1800]
    assert data.shape==(31,3) and np.all(np.diff(data[:,0])==60)
    assert np.isfinite(data).all()
    wb.close()
    started=time.time()
    output=run(args.n,args.dt,args.end,data,args.scheme=='bdf2',
               args.boundary=='integrated',args.tol,args.equilibrium)
    folder=ROOT/'runs';folder.mkdir(exist_ok=True)
    np.savez_compressed(folder/(args.label+'.npz'),T=output[0],C=output[1],input=data)
    meta={'settings':vars(args),'runtime_s':time.time()-started,
          'input':str(INPUT),'input_sha256':hashlib.sha256(INPUT.read_bytes()).hexdigest(),
          'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'metrics_columns':['max_absolute_global_balance','max_relative_global_balance',
                             'max_relative_equation_residual','max_absolute_surface_flux_residual'],
          'relative_balance_definition':'abs(sum(storage)+A*flux)/max(sum(abs(storage)),abs(A*flux),1e-30*2*pi*L)',
          'storage_definition':'capacity*V*(a0*(new-old)-(a0-1)*(old-previous))/dt; a0=1 BE, 1.5 BDF2',
          'heat_balance_unit':'W','water_balance_unit':'m^3/s times kg_water/kg_dry; multiply rho_d to obtain kg_water/s',
          'heat_metrics':output[2][0].tolist(),'water_metrics':output[2][1].tolist(),
          'max_picard_iterations':int(output[3]),'range_Tmin_Tmax_Cmin_Cmax':output[4].tolist(),
          'max_violations_T_time_drop_C_time_rise_T_radial_drop_C_radial_rise_Ts_above_ambient_Cs_above_last':output[5].tolist()}
    (folder/(args.label+'.json')).write_text(json.dumps(meta,ensure_ascii=False,indent=2))
    print(json.dumps(meta,ensure_ascii=False,indent=2))
    if args.end==1800:
        inds=[100,300,600,900,1200,1500,1800]
        print('T paper points:',np.round(output[0][inds][:,::5],4))
        print('C paper points:',np.round(output[1][inds][:,::5],4))

if __name__=='__main__':
    main()
