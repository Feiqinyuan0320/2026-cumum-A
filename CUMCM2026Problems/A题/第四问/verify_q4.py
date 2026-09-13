"""Short, independent physical-volume and material-conservation checks."""
import json
import numpy as np
import solve_q4 as q


def checks():
    data, radii = q.load_inputs()
    n, radius, dt = 40, .02, 17.0
    xi = (np.arange(n)+.5)/n
    w = (np.arange(n)+.5)/n**2
    old = 2.0-.8*xi**2
    coef = 1e-9*(1+.3*xi)
    cap = np.ones(n)
    # Independently assemble the dimensional cylinder annuli and dense BE system.
    faces = np.linspace(0, radius, n+1)
    volume = np.pi*np.diff(faces**2)
    conductance = 2*np.pi*faces[1:-1]*2/(1/coef[:-1]+1/coef[1:])/(radius/n)
    gb = 2*np.pi*radius/(radius/(2*n*coef[-1])+1/q.HM)
    matrix = np.diag(volume/dt)
    rhs = volume/dt*old
    for j, g in enumerate(conductance):
        matrix[j, j] += g
        matrix[j+1, j+1] += g
        matrix[j, j+1] -= g
        matrix[j+1, j] -= g
    matrix[-1, -1] += gb
    rhs[-1] += gb*.05
    expected = np.linalg.solve(matrix, rhs)
    observed = q.linear_step(old, coef, coef[-1], cap, .05, q.HM, dt, radius, w)[0]
    a_error = float(np.max(np.abs(expected-observed)))
    assert a_error < 2e-14
    # A closed shrinking specimen must retain both a constant C and total dry-basis water.
    uniform = np.full(n, 1.7)
    varying = old.copy()
    initial_mass = np.sum(w*varying)
    uniform_error = 0.0
    for t in np.arange(1800, 259201, 1800):
        r = q.radius_at(float(t), radii, 0)
        uniform = q.linear_step(uniform, coef, coef[-1], cap, 0., 0., 1800., r, w)[0]
        varying = q.linear_step(varying, coef, coef[-1], cap, 0., 0., 1800., r, w)[0]
        uniform_error = max(uniform_error, float(np.max(np.abs(uniform-1.7))))
    mass_error = float(abs(np.sum(w*varying)-initial_mass))
    assert uniform_error == 0. and mass_error < 2e-14
    # Also exercise nonlinear coupling, not only the frozen-coefficient kernel.
    coupled = q.step(np.full(n, 45.), np.full(n, 1.7), 45., 1.7,
                     0., 0., 60., .012, w, ht=0., hm=0.)
    assert np.array_equal(coupled[0], np.full(n, 45.))
    assert np.array_equal(coupled[1], np.full(n, 1.7))
    hrs = np.array([0, 6, 12, 18, 24, 30, 36, 72])
    cm = np.array([2, 1.374, 1.248, 1.214, 1.204, 1.201, 1.200, 1.198])
    radius_error = float(max(abs(q.radius_at(float(t*3600), radii, 0)*100-r) for t, r in zip(hrs, cm)))
    assert radius_error < 5e-15
    assert q.radius_at(400000., radii, 0) == radii[-1, 1]
    assert q.radius_at(400000., radii, 1) == .02
    surf = .06
    at6 = q.sample_physical(old, surf, .01374)
    at36 = q.sample_physical(old, surf, .012)
    at60 = q.sample_physical(old, surf, .01199)
    assert np.isfinite(at6[:14]).all() and np.isnan(at6[14:20]).all()
    assert at36[12] == at36[-1] == surf and np.isnan(at36[13:20]).all()
    assert np.isnan(at60[12:20]).all() and at60[-1] == surf
    # Surface interpolation must remain bounded in the last half-cell.
    assert surf < q.sample_xi(old, surf, 1-.25/n) < old[-1]
    assert q.max_state(np.full(n, .1), .2, radius) == (.2, radius)
    inner = np.full(n, .1); inner[20] = .3
    assert q.max_state(inner, .05, radius)[0] == .3
    return {'status': 'PASS', 'solver_sha256': q.digest(q.__file__),
            'A_constant_radius_dense_dimensional_max_error': a_error,
            'B_closed_uniform_field_max_error': uniform_error,
            'C_closed_nonuniform_weighted_mass_error': mass_error,
            'D_radius_nodes_max_error_cm': radius_error,
            'E_outside_blank_surface_equality_and_halfcell': 'PASS',
            'global_maximum_cells_axis_surface': 'PASS',
            'nonlinear_closed_uniform_T_C': 'PASS'}


if __name__ == '__main__':
    result = checks()
    (q.ROOT/'检查记录/基础测试.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False, indent=2))
