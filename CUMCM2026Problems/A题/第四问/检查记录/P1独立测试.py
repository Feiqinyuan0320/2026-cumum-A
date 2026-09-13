"""Independent, bounded P1 tests. Does not edit or run full drying cases."""
from pathlib import Path
import sys, json, hashlib, subprocess
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import solve_q4 as q

record = {'gate': 'P1', 'scope': 'independent bounded numerical checks; no full drying run',
          'solver_sha256': q.digest(ROOT/'solve_q4.py'), 'checks': {}}
checks = record['checks']

# Independent dimensional FV matrix: physical volume and face area, not normalized g.
n, rad, length, dt = 7, 0.01321, 0.25, 37.0
faces = np.linspace(0, rad, n+1)
volume = np.pi*length*np.diff(faces**2)
area = 2*np.pi*length*faces
weights = (np.arange(n)+0.5)/n**2
old = np.array([.9, .83, .77, .71, .59, .5, .4])
coef = np.linspace(1e-9, 3e-10, n)
sc, ambient, h = 2.4e-10, .05, 8e-7
masscap = np.linspace(1, 1.4, n)
matrix = np.diag(masscap*volume/dt)
rhs = masscap*volume/dt*old
for j in range(1, n):
    conductance = area[j]/((rad/n/2)/coef[j-1]+(rad/n/2)/coef[j])
    matrix[j-1,j-1] += conductance
    matrix[j,j] += conductance
    matrix[j-1,j] -= conductance
    matrix[j,j-1] -= conductance
g_surface = area[-1]/((rad/n/2)/sc+1/h)
matrix[-1,-1] += g_surface
rhs[-1] += g_surface*ambient
expected = np.linalg.solve(matrix, rhs)
actual, surface, balance = q.linear_step(old, coef, sc, masscap, ambient, h, dt, rad, weights)
error = float(np.max(abs(actual-expected)))
assert error < 2e-14
surface_expected = (expected[-1]+(rad/n/2)*h/sc*ambient)/(1+(rad/n/2)*h/sc)
assert abs(surface-surface_expected) < 2e-14
flux_difference = float(abs(sc*(actual[-1]-surface)/(rad/n/2)-h*(surface-ambient)))
assert flux_difference < 1e-20
checks['dimensional_dense_matrix'] = {'max_state_difference': error,
    'surface_difference': float(abs(surface-surface_expected)), 'surface_flux_difference': flux_difference}

data, radii = q.load_inputs()
tail = data[data[:,0] >= 10800, 1:].mean(axis=0)
assert np.array_equal(np.array([q.radius_at(t, radii, 0) for t in radii[:,0]]), radii[:,1])
checks['radius_nodes'] = {'count': len(radii), 'max_difference': 0.0,
    'last_radius_m': float(radii[-1,1])}

# Closed system: nonuniform water must conserve fixed dry-mass weights during shrinkage.
n = 40
weights = (np.arange(n)+.5)/n**2
xi = (np.arange(n)+.5)/n
temp = np.full(n,50.)
water = .8+.2*np.cos(np.pi*xi)
ts, cs = 50., float(water[-1])
initial_total = float(weights@water)
for j in range(12):
    rr = q.step(temp, water, ts, cs, 50., .05, 10., .02-.0005*j, weights, 0., 0.)
    temp, water, ts, cs = rr[:4]
mass_error = abs(float(weights@water)-initial_total)
assert mass_error < 2e-14
constant = q.step(np.full(n,50.), np.full(n,.8), 50., .8, 50., .8, 10., .012, weights, 0., 0.)
assert np.max(abs(constant[1]-.8)) == 0
checks['closed_shrinkage'] = {'weighted_water_change': mass_error,
    'constant_water_error': float(np.max(abs(constant[1]-.8)))}

u = 1-.5*xi**2
surface = .5
out = q.sample_physical(u, surface, .01374)
assert np.isfinite(out[:14]).all() and np.isnan(out[14:20]).all() and out[20] == surface
equal = q.sample_physical(u, surface, .012)
assert equal[12] == surface and equal[20] == surface and np.isnan(equal[13:20]).all()
checks['physical_output'] = {'6h_inside_count': 14, 'equal_surface_value': float(equal[12]),
    'surface_column_value': float(equal[-1])}

# Cmax must inspect internal cells, the reconstructed axis and the surface.
peaks = {}
for label, c, cs, expect_r in [
    ('interior', np.array([.1,.1,.2,.1]), .1, .012*2.5/4),
    ('axis', np.array([.2,.1,.1,.1]), .1, 0.),
    ('surface', np.array([.1,.1,.1,.1]), .3, .012)]:
    maximum, position = q.max_state(c, cs, .012)
    assert abs(position-expect_r) < 1e-14
    peaks[label] = {'maximum':float(maximum), 'position_m':float(position)}
checks['maximum_search'] = peaks

# Synthetic short drying event using the actual dynamic geometry and nonlinear constitutive laws.
data_event = data.copy()
data_event[:,1] = 50.
data_event[:,2] = .05
tail_event = np.array([50., .05])
t0 = 10800.
c0 = .1500001-.06*xi**2
tinit = np.full(n,50.)
assert q.max_state(c0, .0900001, q.radius_at(t0,radii,0))[0] > .15
dt_event = 2.
test = q.step(tinit,c0,50.,.0900001,50.,.05,dt_event,q.radius_at(t0+dt_event,radii,0),weights)
assert q.max_state(test[1],test[3],q.radius_at(t0+dt_event,radii,0))[0] < .15
event = q.event_refine(t0,tinit,c0,50.,.0900001,dt_event,data_event,tail_event,radii,0,weights)
lo, hi, reported = event[:3]
bracket_maxima = []
for at_time in [lo,hi]:
    r = q.radius_at(at_time,radii,0)
    state = q.step(tinit,c0,50.,.0900001,50.,.05,at_time-t0,r,weights)
    bracket_maxima.append(float(q.max_state(state[1],state[3],r)[0]))
assert hi-lo <= .001 and bracket_maxima[0] >= .15 and bracket_maxima[1] < .15
report_max = float(q.max_state(event[5],event[7],event[3])[0])
assert report_max < .15 and reported >= hi
advanced = q.unpack(q.advance(tinit,c0,50.,.0900001,t0,t0+120,dt_event,
    data_event,tail_event,radii,0,True))
assert advanced['times'][-1] >= advanced['event'][2]
checks['event'] = {'lower_s':lo, 'upper_s':hi, 'width_s':hi-lo,
    'bracket_Cmax':bracket_maxima, 'reported_s':reported, 'reported_Cmax':report_max,
    'last_regular_output_s':float(advanced['times'][-1])}

# Execute a separate real-input 60 s CLI smoke run and compare its common row with author 1800 s run.
cmd = [sys.executable,str(ROOT/'solve_q4.py'),'--mode','smoke','--end','60','--label','reviewer_smoke60']
completed = subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
assert completed.returncode == 0, completed.stderr
with np.load(ROOT/'runs/reviewer_smoke60.npz') as mine, np.load(ROOT/'runs/smoke1800.npz') as author:
    common_error = float(np.nanmax(abs(mine['C'][0]-author['C'][0])))
    assert common_error == 0
    smoke_details = {'n':len(mine['water']), 'end_s':float(mine['times'][-1]),
        'radius_m':float(mine['radii'][-1]), 'Cmax':float(mine['maxima'][-1,0]),
        'Cs':float(mine['cs']), 'common_row_difference':common_error,
        'max_Picard_iterations':float(mine['stats'][0])}
checks['real_input_cli'] = {'command':cmd, 'exit_code':completed.returncode, **smoke_details}
record['status'] = 'PASS'
record['findings'] = {'P0':[], 'P1':[], 'P2':['Event bracketing tolerance is not full PDE error; full-run convergence remains required.']}
record['not_covered'] = ['long-time convergence', 'final result4 workbook', 'full report figures']
record['input_hashes'] = {'environment':q.digest(q.ENV), 'radius':q.digest(q.RAD)}
record['solver_unchanged_during_review'] = record['solver_sha256'] == q.digest(ROOT/'solve_q4.py')
assert record['solver_unchanged_during_review']
(Path(__file__).parent/'P1评审.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
print(json.dumps(record,ensure_ascii=False,indent=2))
