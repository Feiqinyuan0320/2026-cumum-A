"""Q4 material-coordinate FV solver; model contract: 题目分析报告.md.

C is moisture per dry mass. Fixed xi weights preserve dry-mass-weighted C.
rho(C)*cp(C) remains the agreed effective thermal capacity, not a full enthalpy law.
"""
from pathlib import Path
import argparse
import hashlib
import json
import time

import numpy as np
import openpyxl
from numba import njit

ROOT = Path(__file__).resolve().parent
ENV = ROOT.parent/'附件/烘干初期各时间点烘房温度和水分浓度.xlsx'
RAD = ROOT.parent/'附件/烘干过程中各时间点药材的半径.xlsx'
HT, HM, R0, TOL = 25.0, 8e-7, 0.02, 1e-10
GEOMETRY = {'shrink': 0, 'fixed': 1}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_inputs():
    arrays = []
    for path in (ENV, RAD):
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        arrays.append(np.asarray(list(wb.active.values)[1:], dtype=float))
        wb.close()
    data, radii = arrays
    assert data.shape == (241, 3) and radii.shape == (145, 2)
    assert np.isfinite(data).all() and np.isfinite(radii).all()
    assert np.array_equal(data[:, 0], np.arange(241)*60)
    assert np.array_equal(radii[:, 0], np.arange(145)*1800)
    radii[:, 1] *= 0.01
    assert np.all(np.diff(radii[:, 1]) <= 0) and np.min(radii[:, 1]) > 0
    return data, radii


@njit(cache=True)
def radius_at(t, radii, geometry):
    if geometry == 1:
        return R0
    if t >= radii[-1, 0]:
        return radii[-1, 1]
    j = min(int(t/1800.0), len(radii)-2)
    f = (t-radii[j, 0])/1800.0
    return radii[j, 1]+f*(radii[j+1, 1]-radii[j, 1])


@njit(cache=True)
def ambient_at(t, data, tail):
    if t > data[-1, 0]:
        return tail[0], tail[1]
    j = min(int(t/60.0), len(data)-2)
    f = (t-data[j, 0])/60.0
    return data[j, 1]+f*(data[j+1, 1]-data[j, 1]), data[j, 2]+f*(data[j+1, 2]-data[j, 2])


@njit(cache=True)
def diffusivity(c, temp):
    return 4.2e-4*np.exp(-0.30/c)*np.exp(-3850.0/(temp+273.15))


@njit(cache=True)
def conductivity(c):
    return 0.12+0.20*c/(1.0+c)


@njit(cache=True)
def capacity(c):
    return (760.0+90.0*c)*(1850.0+2150.0*c/(1.0+c))


@njit(cache=True)
def tri_solve(lower, diag, upper, rhs):
    n = len(diag)
    a, b = np.empty(n), np.empty(n)
    a[0], b[0] = upper[0]/diag[0], rhs[0]/diag[0]
    for i in range(1, n):
        pivot = diag[i]-lower[i]*a[i-1]
        a[i], b[i] = upper[i]/pivot, (rhs[i]-lower[i]*b[i-1])/pivot
    x = np.empty(n)
    x[-1] = b[-1]
    for i in range(n-2, -1, -1):
        x[i] = b[i]-a[i]*x[i+1]
    return x


@njit(cache=True)
def linear_step(old, coef, surface_coef, masscap, ambient, h, dt, radius, weights):
    """Normalized FV. g_int=xi*coef/(R^2*dxi); g_surface=1/(R*resistance)."""
    n = len(old)
    g = np.zeros(n+1)
    for i in range(1, n):
        g[i] = i*2.0*coef[i-1]*coef[i]/(coef[i-1]+coef[i])/radius**2
    if h > 0:
        g[n] = 1.0/(radius*(radius/(2*n*surface_coef)+1.0/h))
    lower, diag, upper, rhs = np.zeros(n), np.empty(n), np.zeros(n), np.zeros(n)
    for i in range(n-1):
        flow = g[i+1]*(old[i+1]-old[i])
        rhs[i] += flow
        rhs[i+1] -= flow
    rhs[-1] += g[n]*(ambient-old[-1])
    for i in range(n):
        lower[i] = -g[i]
        if i < n-1:
            upper[i] = -g[i+1]
        diag[i] = masscap[i]*weights[i]/dt+g[i]+g[i+1]
    new = old+tri_solve(lower, diag, upper, rhs)
    surface = new[-1] if h == 0 else ambient+g[n]*radius*(new[-1]-ambient)/h
    # State-level residual, including finite precision in old + increment.
    balance = np.sum(masscap*weights*(new-old))/dt+g[n]*(new[-1]-ambient)
    return new, surface, balance


@njit(cache=True)
def step(temp, water, ts, cs, ambient_t, ambient_c, dt, radius, weights, ht=HT, hm=HM):
    n = len(temp)
    t, c, st, sc = temp.copy(), water.copy(), ts, cs
    ones = np.ones(n)
    for iteration in range(1, 81):
        nt, nts, bt = linear_step(temp, conductivity(c), conductivity(sc), capacity(c),
                                 ambient_t, ht, dt, radius, weights)
        nc, ncs, bc = linear_step(water, diffusivity(c, nt), diffusivity(sc, nts), ones,
                                 ambient_c, hm, dt, radius, weights)
        error = max(np.max(np.abs(nt-t)), np.max(np.abs(nc-c)), abs(nts-st), abs(ncs-sc))
        t, c, st, sc = nt, nc, nts, ncs
        if np.min(c) <= 0 or sc <= 0 or not np.isfinite(c).all() or not np.isfinite(t).all():
            raise ValueError('non-positive/non-finite material state')
        if error < TOL:
            return t, c, st, sc, iteration, error, bt, bc
    raise ValueError('coupled Picard failed to converge within 80 iterations')


@njit(cache=True)
def sample_xi(u, surface, xi):
    n = len(u)
    axis = (9*u[0]-u[1])/8.0
    if xi <= 0:
        return axis
    if xi >= 1:
        return surface
    z = xi*n-0.5
    if z <= 0:
        return axis+(u[0]-axis)*(2*n*xi)**2
    if z >= n-1:
        f = (xi-(n-0.5)/n)/(0.5/n)
        return u[-1]*(1-f)+surface*f
    i = int(np.floor(z))
    f = z-i
    return u[i]*(1-f)+u[i+1]*f


@njit(cache=True)
def sample_physical(u, surface, radius):
    # 0,...,1.9 cm plus the actual moving surface; NaN marks outside material.
    out = np.full(21, np.nan)
    for j in range(20):
        r = j*0.001
        if abs(r-radius) <= 1e-10:
            out[j] = surface
        elif r < radius:
            out[j] = sample_xi(u, surface, r/radius)
    out[-1] = surface
    return out


@njit(cache=True)
def sample_relative(u, surface):
    out = np.empty(5)
    for j in range(5):
        out[j] = sample_xi(u, surface, j/4.0)
    return out


@njit(cache=True)
def max_state(c, cs, radius):
    idx = int(np.argmax(c))
    maximum, position = c[idx], (idx+0.5)/len(c)*radius
    axis = (9*c[0]-c[1])/8.0
    if axis >= maximum:
        maximum, position = axis, 0.0
    if cs > maximum:
        maximum, position = cs, radius
    return maximum, position


@njit(cache=True)
def event_refine(t0, temp, water, ts, cs, dt, data, tail, radii, geometry, weights):
    lo, hi = 0.0, dt
    for _ in range(40):
        if hi-lo <= 0.001:
            break
        mid = (lo+hi)/2
        at, ac = ambient_at(t0+mid, data, tail)
        radius = radius_at(t0+mid, radii, geometry)
        rr = step(temp, water, ts, cs, at, ac, mid, radius, weights)
        if max_state(rr[1], rr[3], radius)[0] < 0.15:
            hi = mid
        else:
            lo = mid
    reported = np.ceil((t0+hi)/3600.0*10000.0)/10000.0*3600.0
    at, ac = ambient_at(reported, data, tail)
    radius = radius_at(reported, radii, geometry)
    rr = step(temp, water, ts, cs, at, ac, reported-t0, radius, weights)
    return t0+lo, t0+hi, reported, radius, rr[0], rr[1], rr[2], rr[3]


@njit(cache=True)
def advance(temp, water, ts, cs, start, end, dt, data, tail, radii, geometry, seek_dry):
    n = len(temp)
    weights = (np.arange(n, dtype=np.float64)+0.5)/n**2
    size = int(np.ceil((end-start)/60))+2
    times, radii_out = np.empty(size), np.empty(size)
    out_t, out_c = np.empty((size, 21)), np.empty((size, 21))
    rel_t, rel_c = np.empty((size, 5)), np.empty((size, 5))
    maxima, average = np.empty((size, 2)), np.empty(size)
    k, now, final_end = 0, start, end
    next_output = (np.floor(start/60)+1.0)*60
    stats = np.zeros(9)
    stats[7] = min(np.min(water), cs)
    event, event_c = np.full(5, np.nan), np.full(21, np.nan)
    event_t, event_rel_c, event_radius = np.full(21, np.nan), np.full(5, np.nan), np.nan
    while now < final_end-1e-8:
        d = min(dt, final_end-now, next_output-now)
        at, ac = ambient_at(now+d, data, tail)
        radius = radius_at(now+d, radii, geometry)
        rr = step(temp, water, ts, cs, at, ac, d, radius, weights)
        nt, nc, nts, ncs = rr[0], rr[1], rr[2], rr[3]
        stats[0] = max(stats[0], rr[4])
        stats[1] = max(stats[1], rr[5])
        stats[2] = max(stats[2], abs(rr[6]))
        stats[3] = max(stats[3], abs(rr[7]))
        stats[4] = max(stats[4], np.max(nc-water), ncs-cs)
        stats[5] = max(stats[5], np.max(nc[1:]-nc[:-1]), ncs-nc[-1])
        stats[6] += 1
        stats[7] = min(stats[7], np.min(nc), ncs)
        stats[8] += d*rr[7]
        if seek_dry and np.isnan(event[0]) and max_state(nc, ncs, radius)[0] < 0.15:
            er = event_refine(now, temp, water, ts, cs, d, data, tail, radii, geometry, weights)
            event[:3] = np.array([er[0], er[1], er[2]])
            event_radius = er[3]
            event[3], event[4] = max_state(er[5], er[7], er[3])
            event_t, event_c = sample_physical(er[4], er[6], er[3]), sample_physical(er[5], er[7], er[3])
            event_rel_c = sample_relative(er[5], er[7])
            if event[3] >= 0.15:
                raise ValueError('reported time not on strict dry side')
            final_end = min(end, np.ceil(er[2]/60)*60)
        temp, water, ts, cs = nt, nc, nts, ncs
        now += d
        if abs(now-next_output) < 1e-7:
            times[k], radii_out[k] = now, radius
            out_t[k], out_c[k] = sample_physical(temp, ts, radius), sample_physical(water, cs, radius)
            rel_t[k], rel_c[k] = sample_relative(temp, ts), sample_relative(water, cs)
            maxima[k, 0], maxima[k, 1] = max_state(water, cs, radius)
            average[k] = 2*np.sum(weights*water)
            k += 1
            next_output += 60
    return (times[:k], radii_out[:k], out_t[:k], out_c[:k], rel_t[:k], rel_c[:k],
            maxima[:k], average[:k], temp, water, ts, cs, stats, event,
            event_radius, event_t, event_c, event_rel_c)


def unpack(res):
    names = ['times', 'radii', 'T', 'C', 'relative_T', 'relative_C', 'maxima', 'average_C',
             'temp', 'water', 'ts', 'cs', 'stats', 'event', 'event_radius',
             'event_T', 'event_C', 'event_relative_C']
    return {name: np.asarray(value) for name, value in zip(names, res)}


def stamp(n, early_dt, geometry, extension):
    return {'solver_sha256': digest(__file__), 'environment_sha256': digest(ENV),
            'radius_input_sha256': digest(RAD), 'n': n, 'early_dt': early_dt,
            'geometry': geometry, 'extension': extension}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=['smoke', 'case'], default='smoke')
    p.add_argument('--n', type=int, default=400)
    p.add_argument('--dt', type=float, default=1.0)
    p.add_argument('--early-dt', type=float, default=0.0625)
    p.add_argument('--end', type=float, default=1800.0, help='smoke end time, seconds')
    p.add_argument('--max-days', type=float, default=14.0)
    p.add_argument('--geometry', choices=list(GEOMETRY), default='shrink')
    p.add_argument('--extension', choices=['mean', 'last'], default='mean')
    p.add_argument('--label', default='smoke')
    p.add_argument('--no-cache', action='store_true')
    args = p.parse_args()
    assert args.n >= 40 and args.dt > 0 and args.early_dt > 0
    data, radii = load_inputs()
    tail = data[data[:, 0] >= 10800, 1:].mean(axis=0) if args.extension == 'mean' else data[-1, 1:]
    geo = GEOMETRY[args.geometry]
    runs = ROOT/'runs'; runs.mkdir(exist_ok=True)
    started = time.perf_counter()
    signature = stamp(args.n, args.early_dt, args.geometry, args.extension)
    print(json.dumps({'start': args.label, **vars(args)}, ensure_ascii=False), flush=True)
    def initial(end):
        return unpack(advance(np.full(args.n, 28.0), np.full(args.n, 2.55), 28.0, 2.55,
                              0.0, end, args.early_dt, data, tail, radii, geo, False))
    if args.mode == 'smoke':
        out = initial(args.end)
    else:
        cache = runs/f'prefix_{args.geometry}_{args.extension}_n{args.n}_dt{args.early_dt:g}'
        cj, cn = cache.with_suffix('.json'), cache.with_suffix('.npz')
        # Use appended suffixes because a decimal dt appears in the prefix name.
        cj, cn = Path(str(cache)+'.json'), Path(str(cache)+'.npz')
        if not args.no_cache and cj.exists() and cn.exists() and json.loads(cj.read_text()) == signature:
            with np.load(cn) as saved:
                first = dict(saved)
        else:
            first = initial(10800.0)
            np.savez_compressed(cn, **first)
            cj.write_text(json.dumps(signature, ensure_ascii=False))
        chunks, prev, now = [first], first, 10800.0
        total_stats = first['stats'].copy()
        while now < args.max_days*86400:
            end = min(now+6*3600, args.max_days*86400)
            prev = unpack(advance(prev['temp'], prev['water'], float(prev['ts']), float(prev['cs']),
                                  now, end, args.dt, data, tail, radii, geo, True))
            chunks.append(prev)
            total_stats[:6] = np.maximum(total_stats[:6], prev['stats'][:6])
            total_stats[6] += prev['stats'][6]
            total_stats[7] = min(total_stats[7], prev['stats'][7])
            total_stats[8] += prev['stats'][8]
            now = float(prev['times'][-1])
            print(json.dumps({'case': args.label, 'time_h': now/3600, 'radius_cm': float(prev['radii'][-1]*100),
                              'max_C': float(prev['maxima'][-1, 0])}), flush=True)
            if np.isfinite(prev['event']).all():
                break
        if not np.isfinite(prev['event']).all():
            raise RuntimeError('drying criterion not reached within guard horizon')
        out = dict(prev)
        for key in ['times', 'radii', 'T', 'C', 'relative_T', 'relative_C', 'maxima', 'average_C']:
            out[key] = np.concatenate([chunk[key] for chunk in chunks], axis=0)
        out['stats'] = total_stats
    assert np.all(np.diff(out['times']) == 60) and np.isfinite(out['relative_C']).all()
    expected_inside = np.arange(20)[None, :]*0.001 <= out['radii'][:, None]+1e-10
    assert np.array_equal(np.isfinite(out['C'][:, :20]), expected_inside)
    assert np.isfinite(out['C'][:, -1]).all()
    output = runs/args.label
    np.savez_compressed(str(output)+'.npz', **out, input=data, radius_data=radii, tail=tail)
    meta = {'settings': vars(args), **signature, 'runtime_s': time.perf_counter()-started,
            'tail_T_C': tail.tolist(), 'stats': out['stats'].tolist(),
            'stats_definition': ['max_Picard_iterations', 'max_final_Picard_difference',
              'max_abs_normalized_heat_equation_balance', 'max_abs_dry_mass_weighted_water_balance_per_s',
              'max_material_C_time_increase', 'max_outward_C_increase', 'step_count', 'minimum_C',
              'accumulated_dry_mass_weighted_water_balance_defect'],
            'event': out['event'].tolist() if args.mode == 'case' else None,
            'event_definition': ['last_non_dry_s', 'first_dry_s', 'reported_dry_s',
                                 'max_C_at_reported_time', 'radius_of_maximum_m'],
            'event_radius_m': float(out['event_radius']) if args.mode == 'case' else None,
            'radius_plateau_extension_used': bool(out['times'][-1] > radii[-1, 0] and geo == 0),
            'output_rows': len(out['times']), 'last_output_s': float(out['times'][-1])}
    Path(str(output)+'.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    print(json.dumps(meta, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
