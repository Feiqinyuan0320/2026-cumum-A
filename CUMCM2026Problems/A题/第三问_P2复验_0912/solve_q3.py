"""Q3: inherit the handed-off Q2 model, with explicit long-time boundary scenarios.

Cell-centred radial FV, backward Euler, harmonic internal faces, planar
half-cell surface resistance with surface properties, coupled Picard iteration.
Run using /opt/anaconda3/bin/python. Original workbooks are read-only.
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
ENV = ROOT.parent / '附件/烘干初期各时间点烘房温度和水分浓度.xlsx'
Q2 = ROOT.parent / '第二问/result2.xlsx'
R, HT, HM = 0.02, 25.0, 8e-7
TOL = 1e-10


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_environment():
    wb = openpyxl.load_workbook(ENV, read_only=True, data_only=True)
    rows = list(wb.active.values)
    wb.close()
    a = np.asarray(rows[1:], dtype=float)
    assert a.shape == (241, 3) and np.isfinite(a).all()
    assert a[0, 0] == 0 and a[-1, 0] == 14400 and np.all(np.diff(a[:, 0]) == 60)
    return a


@njit(cache=True)
def diffusivity(c, temp):
    return 2.4e-3 * np.exp(-0.45/c) * np.exp(-3850.0/(temp+273.15))


@njit(cache=True)
def conductivity(c):
    return 0.21 + 0.38*c/(1.0+c)


@njit(cache=True)
def capacity(c):
    return (650.0+128.0*c) * (1450.0+2736.0*c/(1.0+c))


@njit(cache=True)
def tri_solve(lower, diag, upper, rhs):
    n = len(diag)
    a, b = np.empty(n), np.empty(n)
    a[0], b[0] = upper[0]/diag[0], rhs[0]/diag[0]
    for i in range(1, n):
        pivot = diag[i]-lower[i]*a[i-1]
        a[i] = upper[i]/pivot
        b[i] = (rhs[i]-lower[i]*b[i-1])/pivot
    x = np.empty(n)
    x[-1] = b[-1]
    for i in range(n-2, -1, -1):
        x[i] = b[i]-a[i]*x[i+1]
    return x


@njit(cache=True)
def linear_step(old, coef, surface_coef, masscap, ambient, h, dt, dr, volume):
    """Solve for increments to reduce cancellation for nearly constant T."""
    n = len(old)
    g = np.empty(n+1)
    g[0] = 0.0
    for i in range(1, n):
        g[i] = i * 2.0*coef[i-1]*coef[i]/(coef[i-1]+coef[i])
    g[n] = R/(0.5*dr/surface_coef + 1.0/h)
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
        diag[i] = masscap[i]*volume[i]/dt + g[i]+g[i+1]
    increment = tri_solve(lower, diag, upper, rhs)
    new = old+increment
    surf = ambient+g[-1]*(new[-1]-ambient)/(R*h)
    # Exact discrete balance for the coefficients used by this linear solve.
    balance = abs(np.sum(masscap*volume*increment/dt)+g[-1]*(new[-1]-ambient))
    return new, surf, balance


@njit(cache=True)
def step(temp, water, ts, cs, ambient_t, ambient_c, dt, dr, volume):
    n = len(temp)
    t, c = temp.copy(), water.copy()
    s_t, s_c = ts, cs
    ones = np.ones(n)
    err = 1.0
    for iteration in range(1, 81):
        new_t, new_ts, bt = linear_step(temp, conductivity(c), conductivity(s_c),
                                      capacity(c), ambient_t, HT, dt, dr, volume)
        new_c, new_cs, bc = linear_step(water, diffusivity(c, new_t),
                                       diffusivity(s_c, new_ts), ones,
                                       ambient_c, HM, dt, dr, volume)
        err = max(np.max(np.abs(new_t-t)), np.max(np.abs(new_c-c)),
                  abs(new_ts-s_t), abs(new_cs-s_c))
        t, c, s_t, s_c = new_t, new_c, new_ts, new_cs
        if np.min(c) <= 0 or s_c <= 0 or not np.isfinite(c).all() or not np.isfinite(t).all():
            raise ValueError('non-positive or non-finite state')
        if err < TOL:
            return t, c, s_t, s_c, iteration, err, bt, bc
    raise ValueError('coupled Picard failed to converge')


@njit(cache=True)
def ambient_at(t, data, tail):
    if t > data[-1, 0]:
        return tail[0], tail[1]
    j = min(int(t/60.0), len(data)-2)
    fraction = (t-data[j, 0])/60.0
    return (data[j, 1]+fraction*(data[j+1, 1]-data[j, 1]),
            data[j, 2]+fraction*(data[j+1, 2]-data[j, 2]))


@njit(cache=True)
def sample(u, surf, dr):
    out = np.empty(21)
    out[0] = (9*u[0]-u[1])/8.0
    out[-1] = surf
    for j in range(1, 20):
        z = j*0.001/dr-0.5
        i = int(np.floor(z))
        f = z-i
        out[j] = u[i]*(1-f)+u[i+1]*f
    return out


@njit(cache=True)
def max_state(c, cs, dr):
    # Check all cells, the symmetric-axis reconstruction and physical surface.
    # Together these also bound the piecewise spatial reconstruction used here.
    idx = int(np.argmax(c))
    maximum, radius = c[idx], (idx+0.5)*dr
    axis = (9*c[0]-c[1])/8.0
    if axis >= maximum:
        maximum, radius = axis, 0.0
    if cs > maximum:
        maximum, radius = cs, R
    return maximum, radius


@njit(cache=True)
def event_refine(t0, temp, water, ts, cs, dt, data, tail, dr, volume, threshold):
    """Bracket the crossing using BE substeps from the last non-dry state."""
    lo, hi = 0.0, dt
    for _ in range(40):
        if hi-lo <= 0.001:
            break
        mid = (lo+hi)/2
        at, ac = ambient_at(t0+mid, data, tail)
        rr = step(temp, water, ts, cs, at, ac, mid, dr, volume)
        if max_state(rr[1], rr[3], dr)[0] < threshold:
            hi = mid
        else:
            lo = mid
    # Round hours upward, so the reported finite time lies on the dry side.
    reported = np.ceil((t0+hi)/3600.0*10000.0)/10000.0*3600.0
    at, ac = ambient_at(reported, data, tail)
    rr = step(temp, water, ts, cs, at, ac, reported-t0, dr, volume)
    return t0+lo, t0+hi, reported, rr[0], rr[1], rr[2], rr[3]


@njit(cache=True)
def advance(temp, water, ts, cs, start, end, dt, output_every, data, tail, seek_dry):
    n = len(temp)
    dr = R/n
    volume = (np.arange(n, dtype=np.float64)+0.5)*dr**2  # divided by 2*pi*L
    capacity_out = int(np.ceil((end-start)/output_every))+2
    ot = np.empty(capacity_out)
    out_t, out_c = np.empty((capacity_out, 21)), np.empty((capacity_out, 21))
    maxima = np.empty((capacity_out, 2))
    k = 0
    now, final_end = start, end
    next_output = (np.floor(start/output_every)+1.0)*output_every
    stats = np.zeros(8)
    # iterations, final increment, abs heat/water balance, C time increase,
    # C outward increase, steps, minimum C
    stats[7] = min(np.min(water), cs)
    event = np.full(5, np.nan)  # lower, upper, reported seconds, max C, radius m
    event_t, event_c = np.empty(21), np.empty(21)
    while now < final_end-1e-8:
        d = min(dt, final_end-now, next_output-now)
        at, ac = ambient_at(now+d, data, tail)
        rr = step(temp, water, ts, cs, at, ac, d, dr, volume)
        new_t, new_c, new_ts, new_cs = rr[0], rr[1], rr[2], rr[3]
        stats[0] = max(stats[0], rr[4])
        stats[1] = max(stats[1], rr[5])
        stats[2] = max(stats[2], rr[6]*2*np.pi*0.25)
        stats[3] = max(stats[3], rr[7]*2*np.pi*0.25)
        stats[4] = max(stats[4], np.max(new_c-water), new_cs-cs)
        stats[5] = max(stats[5], np.max(new_c[1:]-new_c[:-1]), new_cs-new_c[-1])
        stats[6] += 1
        stats[7] = min(stats[7], np.min(new_c), new_cs)
        cm, loc = max_state(new_c, new_cs, dr)
        if seek_dry and np.isnan(event[0]) and cm < 0.15:
            refined = event_refine(now, temp, water, ts, cs, d, data, tail, dr, volume, 0.15)
            event[:3] = np.array([refined[0], refined[1], refined[2]])
            event[3], event[4] = max_state(refined[4], refined[6], dr)
            event_t = sample(refined[3], refined[5], dr)
            event_c = sample(refined[4], refined[6], dr)
            if event[3] >= 0.15:
                raise ValueError('reported drying time is not on the strict dry side')
            final_end = min(end, np.ceil(refined[2]/output_every)*output_every)
        temp, water, ts, cs = new_t, new_c, new_ts, new_cs
        now += d
        if abs(now-next_output) <= 1e-7:
            ot[k] = now
            out_t[k] = sample(temp, ts, dr)
            out_c[k] = sample(water, cs, dr)
            maxima[k, 0], maxima[k, 1] = max_state(water, cs, dr)
            k += 1
            next_output += output_every
    return (ot[:k], out_t[:k], out_c[:k], maxima[:k], temp, water, ts, cs,
            stats, event, event_t, event_c)


def unpack(res):
    return dict(times=res[0], T=res[1], C=res[2], maxima=res[3], temp=res[4],
                water=res[5], ts=np.array(res[6]), cs=np.array(res[7]),
                stats=res[8], event=res[9], event_T=res[10], event_C=res[11])


def run_initial(n, end, dt, data):
    return unpack(advance(np.full(n, 28.0), np.full(n, 2.55), 28.0, 2.55,
                          0.0, float(end), dt, 1.0, data, data[-1, 1:], False))


def regression(out):
    wb = openpyxl.load_workbook(Q2, read_only=True, data_only=True)
    report = {}
    for field, name in [('T', '温度'), ('C', '水分浓度')]:
        rows = list(wb[name].values)
        target = np.asarray(rows[1:], dtype=float)
        assert target.shape == (10800, 22) and np.all(target[:, 0] == np.arange(1, 10801))
        assert np.isfinite(target).all()
        count = len(out['times'])
        actual = out[field]
        diff = actual-target[:count, 1:]
        paper_idx = np.arange(1799, count, 1800)
        report[field] = {
            'max_abs_vs_rounded_workbook': float(np.max(np.abs(diff))),
            'rounded_mismatches': int(np.count_nonzero(np.round(actual, 4) != target[:count, 1:])),
            'paper_mismatches': int(np.count_nonzero(np.round(actual[paper_idx][:, ::5], 4) != target[paper_idx, 1:][:, ::5])),
            'paper_values': np.round(actual[paper_idx][:, ::5], 4).tolist(),
        }
    wb.close()
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=['smoke', 'regression', 'case'], default='smoke')
    p.add_argument('--n', type=int, default=400)
    p.add_argument('--dt', type=float, default=1.0)
    p.add_argument('--early-dt', type=float, default=0.0625)
    p.add_argument('--end', type=float, default=1800)
    p.add_argument('--extension', choices=['mean', 'last'], default='mean')
    p.add_argument('--label', default='smoke')
    args = p.parse_args()
    assert args.n >= 40 and args.dt > 0 and args.early_dt > 0
    data = load_environment()
    tail = np.mean(data[data[:, 0] >= 10800, 1:], axis=0) if args.extension == 'mean' else data[-1, 1:]
    stamp = {'input_sha256': digest(ENV), 'solver_sha256': digest(__file__),
             'n': args.n, 'early_dt': args.early_dt}
    runs = ROOT/'runs'
    runs.mkdir(exist_ok=True)
    started = time.perf_counter()
    initial = None
    if args.mode in ('smoke', 'regression'):
        end = 10800.0 if args.mode == 'regression' else args.end
        out = run_initial(args.n, end, args.early_dt, data)
        checks = regression(out)
        if args.mode == 'regression':
            cache = runs/f'prefix_n{args.n}_dt{args.early_dt:g}'
            np.savez_compressed(str(cache)+'.npz', **out)
            Path(str(cache)+'.json').write_text(json.dumps(stamp))
    else:
        cache = runs/f'prefix_n{args.n}_dt{args.early_dt:g}'
        if Path(str(cache)+'.json').exists() and json.loads(Path(str(cache)+'.json').read_text()) == stamp:
            with np.load(str(cache)+'.npz') as a:
                initial = dict(a)
        else:
            initial = run_initial(args.n, 10800.0, args.early_dt, data)
            np.savez_compressed(str(cache)+'.npz', **initial)
            Path(str(cache)+'.json').write_text(json.dumps(stamp))
        out = unpack(advance(initial['temp'], initial['water'], float(initial['ts']), float(initial['cs']),
                             10800.0, 14*86400.0, args.dt, 60.0, data, tail, True))
        if not np.isfinite(out['event']).all():
            raise RuntimeError('drying criterion not reached within 14 days')
        # Prefix output is per second; result3 will contain only 60-second samples.
        pick = (initial['times'] % 60 == 0)
        for key in ('times', 'T', 'C', 'maxima'):
            out[key] = np.concatenate((initial[key][pick], out[key]), axis=0)
        checks = {}
    output = runs/args.label
    np.savez_compressed(str(output)+'.npz', **out, input=data, tail=tail)
    meta = {'settings': vars(args), **stamp, 'q2_sha256': digest(Q2),
            'runtime_s': time.perf_counter()-started, 'tail_T_C': tail.tolist(),
            'tail_rule': 'arithmetic mean of 61 nodes from 10800 through 14400 s inclusive' if args.extension == 'mean' else 'last observed value at 14400 s',
            'regression': checks, 'stats': out['stats'].tolist(),
            'stats_definition': ['max_iterations', 'max_final_Picard_difference', 'max_absolute_heat_discrete_balance_W',
                                 'max_absolute_reduced_water_discrete_balance_m3_per_s', 'max_C_time_increase',
                                 'max_C_outward_increase', 'step_count', 'minimum_C'],
            'event': out['event'].tolist() if args.mode == 'case' else None,
            'event_definition': ['last_non_dry_time_s', 'first_dry_time_s', 'reported_time_s_rounded_hours_upward',
                                 'maximum_reconstructed_C_at_reported_time', 'radius_of_maximum_m'],
            'output_rows': len(out['times']), 'last_output_s': float(out['times'][-1])}
    Path(str(output)+'.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    print(json.dumps(meta, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
