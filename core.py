#!/usr/bin/env python3
"""
Gas MOC Smart Optimizer — Core Module
======================================

This module contains the core simulation engine and optimization logic,
separated from the GUI for better maintainability and to support both
tkinter and Streamlit interfaces.

Author: Bharat Flow Analytics
Version: 5.0
Date: 2026-09
"""

import math
import numpy as np
from scipy.optimize import differential_evolution, minimize, brentq


# =============================================================================
#  CORE GAS MOC SIMULATION ENGINE
# =============================================================================

def colebrook_white(Re, D_pipe, roughness):
    """Darcy friction factor — Colebrook-White iteration."""
    if Re < 1.0:
        return 0.02
    if Re < 2300.0:
        return 64.0 / Re
    f = 0.02
    for _ in range(60):
        rhs = -2.0 * math.log10(roughness / (3.7 * D_pipe) +
                                 2.51 / (Re * math.sqrt(f)))
        f_new = 1.0 / rhs ** 2
        if abs(f_new - f) < 1.0e-10:
            break
        f = f_new
    return f_new


def haaland(Re, D_pipe, roughness):
    """Darcy friction factor — Haaland explicit approximation.
    
    Valid range: Re >= 2300, 1e-6 <= epsilon/D <= 0.05
    Max error vs Colebrook-White: ~2%
    No iteration required — single closed-form evaluation.
    
    Haaland (1983): 1/sqrt(f) = -1.8 * log10[(epsilon/D / 3.7)^1.11 + 6.9/Re]
    """
    if Re < 1.0:
        return 0.02
    if Re < 2300.0:
        return 64.0 / Re  # Laminar — Hagen-Poiseuille, exact
    
    rel_rough = roughness / D_pipe
    inner = (rel_rough / 3.7) ** 1.11 + 6.9 / Re
    inv_sqrt_f = -1.8 * math.log10(inner)
    return 1.0 / inv_sqrt_f ** 2


def run_gas_moc(
    # Geometry
    L=7800.0, dx=50.0,
    D=None,
    eps=45.0e-6,
    elevation_profile=None,
    # Gas properties
    Z_factor=0.996, gamma=1.26, R_gas=424.0, T_K=298.15, mu_dyn=1.1e-5,
    # Pressures (Pa absolute)
    P_upstream=36.5e5, P_atm=1.0e5,
    # Valve geometry / location
    valve_position=7800.0,
    xT=0.9, Fp=1.0, Cv_max=132.0,
    t_valve_open_start=30.0,
    t_valve_opening=5.0,
    t_valve_hold_open=60.0,
    t_valve_closing=5.0,
    K_multiplier=5.0, T_total=200.0,
    beta=0.9,
    B_factor=1.0,
    x_pt_m=7750.0,
    upstream_bc='CLOSED_END', V_tank=10.0,
    verbose=False,
    g=9.81,
):
    """
    Run Gas-MOC simulation with optional elevation profile.
    
    elevation_profile: numpy array of shape (M, 2) with columns
                       [distance_m, elevation_m], or None for flat.
    
    Returns dict with keys:
        time, P_up, P_down_pt, P_valve_upstream, P_valve_downstream,
        P_flare, Q_valve, tau, x_grid, x_segments, D_arr, elevation_arr
    """
    N = int(round(L / dx))
    if verbose:
        print(f"Running Gas MOC with {N} segments (dx={dx} m)")
    
    x_grid = np.linspace(0.0, L, N + 1)

    # Build per-node diameter array
    if D is None or np.isscalar(D):
        D_val = float(D) if D is not None else 0.2032
        D_arr = np.full(N + 1, D_val)
    else:
        D_np = np.asarray(D, dtype=float)
        if len(D_np) == N:
            D_arr = np.append(D_np, D_np[-1])
        elif len(D_np) == N + 1:
            D_arr = D_np.copy()
        else:
            D_arr = np.interp(np.arange(N + 1),
                              np.linspace(0, N, len(D_np)), D_np)

    A_arr = np.pi * D_arr ** 2 / 4.0

    # Build per-node elevation array
    if elevation_profile is not None:
        elev_np = np.asarray(elevation_profile, dtype=float)
        elev_dist = elev_np[:, 0]
        elev_vals = elev_np[:, 1]
        elevation_arr = np.interp(x_grid, elev_dist, elev_vals)
    else:
        elevation_arr = np.zeros(N + 1)

    # Wave speed
    B_iso = math.sqrt(Z_factor * R_gas * T_K)
    B = B_iso * B_factor
    if verbose:
        print(f"Wave speed B = {B_iso:.2f} m/s  (B_factor={B_factor:.4f}  ->  B_eff={B:.2f} m/s)")

    # Courant-number based time step
    beta = float(np.clip(beta, 0.01, 1.0))
    dt = beta * dx / B
    if verbose:
        print(f"Courant beta = {beta:.3f}  ->  dt = {dt:.5f} s  (dx={dx} m)")
    Nt = int(T_total / dt)

    rho_ref = P_upstream / (Z_factor * R_gas * T_K)

    # PT recording node
    i_pt = int(round(x_pt_m / dx))
    i_pt = min(i_pt, N - 1)
    i_pt = max(i_pt, 0)

    # ISA N6 constant
    N6 = 2.73

    # Friction helper
    def local_friction(M_flow, p_node, i_node):
        D_i = D_arr[i_node]
        A_i = A_arr[i_node]
        if abs(M_flow) < 1.0e-12 or p_node < 1.0 or A_i < 1e-10 or D_i < 1e-6:
            return 0.02
        rho_loc = p_node / (Z_factor * R_gas * T_K)
        u_loc = abs(M_flow) / (rho_loc * A_i)
        if not np.isfinite(u_loc) or u_loc > 1e6:
            return 0.02
        Re = rho_loc * u_loc * D_i / mu_dyn
        if not np.isfinite(Re) or Re < 1.0:
            return 0.02
        return haaland(Re, D_i, eps)

    def friction_force(f, M_flow, p_node, D_i, A_i):
        denom = 2.0 * D_i * A_i**2 * max(p_node, 1.0)
        if denom < 1e-30:
            return 0.0
        val = (f * B**2 * M_flow * abs(M_flow)) / denom
        if not np.isfinite(val):
            return 0.0
        return float(np.clip(val, -1e12, 1e12))

    # Elevation slope helper
    def gravity_term(i_node, pres):
        if i_node == 0:
            dz = elevation_arr[1] - elevation_arr[0]
        elif i_node == N:
            dz = elevation_arr[N] - elevation_arr[N - 1]
        else:
            dz = (elevation_arr[i_node + 1] - elevation_arr[i_node - 1]) / 2.0
        sin_theta = dz / dx
        rho_loc = pres / (Z_factor * R_gas * T_K)
        return (rho_loc * g * sin_theta)

    # Valve opening fraction - 4-phase linear cycle
    _t0 = float(t_valve_open_start)
    _t1_end = _t0 + float(t_valve_opening)
    _t2_end = _t1_end + float(t_valve_hold_open)
    _t3_end = _t2_end + float(t_valve_closing)

    def valve_tau(t):
        if t < _t0:
            return 0.0
        elif t < _t1_end:
            return (t - _t0) / (_t1_end - _t0)
        elif t < _t2_end:
            return 1.0
        elif t < _t3_end:
            return 1.0 - (t - _t2_end) / (_t3_end - _t2_end)
        else:
            return 0.0

    # ISA/IEC N6 mass-flow model
    def valve_mass_flow(Pu, Pd, tau_v):
        if tau_v <= 0.0 or Pu <= Pd:
            return 0.0
        Fgamma = gamma / 1.40
        x_choked = Fgamma * xT
        x_actual = (Pu - Pd) / Pu
        if x_actual >= x_choked:
            x_sizing = x_choked
            Y = 2.0 / 3.0
        else:
            x_sizing = x_actual
            Y = 1.0 - x_sizing / (3.0 * Fgamma * xT)
        Cv_eff = (Cv_max / K_multiplier) * tau_v
        rho_u = Pu / (Z_factor * R_gas * T_K)
        Pu_kPa = Pu / 1000.0
        mdot_kgh = N6 * Fp * Cv_eff * Y * math.sqrt(x_sizing * Pu_kPa * rho_u)
        return mdot_kgh / 3600.0

    # Initial conditions
    p = np.full(N + 1, P_upstream)
    M_flow = np.zeros(N + 1)
    p_L_valve = P_upstream
    P_tank = float(P_upstream)

    # Time-history storage
    t_hist, P_up_h, P_down_pt_h = [], [], []
    P_Lv_h, P_Rv_h, P_flare_h, Q_v_h, tau_h = [], [], [], [], []

    frac = 1.0 - beta

    def _foot_plus(i):
        w0, w1 = beta, frac
        return (p[i-1]*w0 + p[i]*w1, M_flow[i-1]*w0 + M_flow[i]*w1, i - 1)

    def _foot_minus(i):
        w0, w1 = frac, beta
        return (p[i]*w0 + p[i+1]*w1, M_flow[i]*w0 + M_flow[i+1]*w1, i + 1)

    # Main time loop
    for n in range(Nt):
        t_now = n * dt
        tau_v = valve_tau(t_now)

        p_new = p.copy()
        M_new = M_flow.copy()

        # Interior nodes 1 .. N-1
        for i in range(1, N):
            A_i = A_arr[i]
            pA, MA, iA = _foot_plus(i)
            D_A = D_arr[iA]; A_A = A_arr[iA]
            fA = local_friction(MA, pA, iA)
            FA = friction_force(fA, MA, pA, D_A, A_A)
            GA = gravity_term(iA, pA)
            Cp = MA / A_i + pA / B - dt * (FA + GA)

            pB, MB, iB = _foot_minus(i)
            D_B = D_arr[iB]; A_B = A_arr[iB]
            fB = local_friction(MB, pB, iB)
            FB = friction_force(fB, MB, pB, D_B, A_B)
            GB = gravity_term(iB, pB)
            Cm = MB / A_i - pB / B - dt * (FB + GB)

            Mp = A_i * (Cp + Cm) / 2.0
            pp = B * (Cp - Cm) / 2.0

            M_new[i] = float(Mp) if np.isfinite(Mp) else 0.0
            p_new[i] = float(pp) if np.isfinite(pp) else P_upstream

        # Upstream boundary
        A0 = A_arr[0]
        pB0 = p[0] * frac + p[1] * beta
        MB0 = M_flow[0] * frac + M_flow[1] * beta
        iB0 = 1
        D_B0 = D_arr[iB0]; A_B0 = A_arr[iB0]
        fB0 = local_friction(MB0, pB0, iB0)
        FB0 = friction_force(fB0, MB0, pB0, D_B0, A_B0)
        GB0 = gravity_term(iB0, pB0)
        Cm0 = MB0 / A0 - pB0 / B - dt * (FB0 + GB0)

        if upstream_bc == 'CONSTANT_P':
            p_new[0] = P_upstream
            M_new[0] = A0 * (Cm0 + P_upstream / B)
        elif upstream_bc == 'CLOSED_END':
            M_new[0] = 0.0
            p_wall = -B * Cm0
            p_new[0] = float(np.clip(p_wall, 0.3 * P_atm, 2.0 * P_upstream))
        else:  # FINITE_TANK
            M_new[0] = A0 * (Cm0 + P_tank / B)
            M_new[0] = max(0.0, M_new[0])
            P_tank -= dt * (Z_factor * R_gas * T_K / V_tank) * M_new[0]
            P_tank = max(P_tank, 0.3 * P_atm)
            p_new[0] = P_tank

        # Downstream boundary - valve
        AN = A_arr[N]
        pAN = p[N-1] * beta + p[N] * frac
        MAN = M_flow[N-1] * beta + M_flow[N] * frac
        iAN = N - 1
        D_AN = D_arr[iAN]; A_AN = A_arr[iAN]
        fAN = local_friction(MAN, pAN, iAN)
        FAN = friction_force(fAN, MAN, pAN, D_AN, A_AN)
        GAN = gravity_term(iAN, pAN)
        Cp_N = MAN / AN + pAN / B - dt * (FAN + GAN)

        if tau_v > 0.0:
            M_upper = min(rho_ref * B * AN, abs(Cp_N) * AN * 0.999)

            def valve_residual(M_v):
                p_u = B * (Cp_N - M_v / AN)
                if p_u <= P_atm * 0.05:
                    return M_v
                return M_v - valve_mass_flow(p_u, P_atm, tau_v)

            try:
                r_lo = valve_residual(0.0)
                r_hi = valve_residual(M_upper)
                if r_lo * r_hi < 0.0:
                    M_v_sol = brentq(valve_residual, 0.0, M_upper, xtol=1.0e-8, maxiter=200)
                else:
                    M_v_sol = 0.0 if abs(r_lo) <= abs(r_hi) else M_upper
            except Exception:
                M_v_sol = 0.0

            p_u_sol = B * (Cp_N - M_v_sol / AN)
            p_u_sol = max(p_u_sol, P_atm)
            p_L_valve = p_u_sol
            p_new[N] = p_u_sol
            M_new[N] = M_v_sol
        else:
            p_wall = B * Cp_N
            p_L_valve = float(np.clip(p_wall, P_atm, 2.0 * P_upstream))
            p_new[N] = p_L_valve
            M_new[N] = 0.0

        p_new = np.clip(p_new, 0.3 * P_atm, 2.0 * P_upstream)
        p[:] = p_new
        M_flow[:] = M_new

        t_hist.append(t_now)
        P_up_h.append(p[0] / 1.0e5)
        P_down_pt_h.append(p[i_pt] / 1.0e5)
        P_Lv_h.append(p_L_valve / 1.0e5)
        P_Rv_h.append(P_atm / 1.0e5)
        P_flare_h.append(p[N] / 1.0e5)
        rho_v = p[N] / (Z_factor * R_gas * T_K)
        Q_v_h.append(M_flow[N] / rho_v if rho_v > 1e-3 else 0.0)
        tau_h.append(tau_v)

    x_seg = 0.5 * (x_grid[:-1] + x_grid[1:])
    return {
        'time': np.array(t_hist),
        'P_up': np.array(P_up_h),
        'P_down_pt': np.array(P_down_pt_h),
        'P_valve_upstream': np.array(P_Lv_h),
        'P_valve_downstream': np.array(P_Rv_h),
        'P_flare': np.array(P_flare_h),
        'Q_valve': np.array(Q_v_h),
        'tau': np.array(tau_h),
        'x_grid': x_grid,
        'x_segments': x_seg,
        'D_arr': D_arr,
        'elevation_arr': elevation_arr,
    }


# =============================================================================
#  PICKLABLE WORKER FOR MULTIPROCESSING
# =============================================================================

class _MOCWorkerParams:
    """Immutable container of all run_gas_moc keyword arguments."""
    __slots__ = ('kwargs', 'D_nom', 'w', 't_pt', 'p_pt',
                 'lambda_smooth', 'lambda_tv', 'D_initial')

    def __init__(self, base_params, D_nom, t_pt, p_pt, w,
                 D_initial, lambda_smooth, lambda_tv):
        self.kwargs = base_params
        self.D_nom = float(D_nom)
        self.t_pt = np.asarray(t_pt, dtype=float)
        self.p_pt = np.asarray(p_pt, dtype=float)
        self.w = np.asarray(w, dtype=float)
        self.D_initial = np.asarray(D_initial, dtype=float)
        self.lambda_smooth = float(lambda_smooth)
        self.lambda_tv = float(lambda_tv)


_WORKER_PARAMS = None


def _worker_initializer(wp):
    """Pool initializer: runs once in each child process on spawn."""
    global _WORKER_PARAMS
    _WORKER_PARAMS = wp


def _moc_worker_cost(D_multipliers):
    """
    Module-level cost function — picklable by multiprocessing.
    Called once per candidate solution by each worker process.
    """
    global _WORKER_PARAMS
    wp = _WORKER_PARAMS
    if wp is None:
        return 1e10

    D_array = np.asarray(D_multipliers, dtype=float) * wp.D_nom
    if np.any(D_array < 0.01) or np.any(D_array > 2.0 * wp.D_nom):
        return 1e10

    params = dict(wp.kwargs)
    params['D'] = D_array
    params['verbose'] = False

    try:
        res = run_gas_moc(**params)
        if np.any(~np.isfinite(res['P_down_pt'])):
            return 1e10

        p_model = np.interp(wp.t_pt, res['time'], res['P_down_pt'])
        residuals = p_model - wp.p_pt
        misfit = float(np.sqrt(np.mean(wp.w * residuals ** 2)))

        smooth = float(np.mean(np.diff(D_array) ** 2))
        tot_var = float(np.mean((D_array - wp.D_initial) ** 2))

        lam_s = min(wp.lambda_smooth * max(misfit, 1e-9) / max(smooth, 1e-15),
                    1e-3 * misfit)
        lam_t = min(wp.lambda_tv * max(misfit, 1e-9) / max(tot_var, 1e-15),
                    1e-3 * misfit)

        return misfit + lam_s * smooth + lam_t * tot_var

    except Exception:
        return 1e10


# =============================================================================
#  DIAMETER OPTIMIZER ENGINE
# =============================================================================

class GasMOCOptimizer:
    """
    Optimizer — fits per-segment pipe diameters to downstream PT data.
    
    Key features:
    - Cost function uses pure RMSE (bar) with adaptive transient weighting
    - Regularisation scaled relative to misfit magnitude (not absolute)
    - Bounds defined as absolute D multiplier range, symmetrically from initial
    - DE with best1bin + polish (L-BFGS-B) for global+local refinement
    - Parallel workers auto-detected
    - Warm-start: initial profile seeded into DE population
    - Full history including all evaluations, not just improvements
    
    Note: In Streamlit, multiprocessing with workers > 1 may have limitations
    depending on the operating system and deployment environment.
    """

    def __init__(self, t_pt, p_pt, base_params, D_nom, n_segments,
                 D_initial_profile=None):
        self.t_pt = np.asarray(t_pt, dtype=float)
        self.p_pt = np.asarray(p_pt, dtype=float)
        self.base_params = base_params
        self.D_nom = float(D_nom)
        self.n_segments = n_segments

        if D_initial_profile is not None and len(D_initial_profile) == n_segments:
            self.D_initial = np.asarray(D_initial_profile, dtype=float)
        else:
            self.D_initial = np.full(n_segments, D_nom)

        # Regularisation weights
        self.lambda_smooth = 1e-6
        self.lambda_tv = 1e-7

        self.eval_count = 0
        self.best_cost = np.inf
        self.best_D_array = self.D_initial.copy()
        self.history = []
        self.running = False
        self.stop_requested = False
        self.progress_callback = None

        self._build_weight_mask()

    def _build_weight_mask(self):
        """Weight the transient window (valve open → 2× close time) 10× higher."""
        t = self.t_pt
        bp = self.base_params
        t0 = bp.get('t_valve_open_start', 0.0)
        dop = bp.get('t_valve_opening', 5.0)
        dhld = bp.get('t_valve_hold_open', 60.0)
        dcl = bp.get('t_valve_closing', 5.0)
        t_end_transient = t0 + dop + dhld + 2.0 * dcl

        self.w = np.ones(len(t), dtype=float)
        mask = (t >= t0) & (t <= t_end_transient)
        if mask.sum() > 0:
            self.w[mask] = 20.0
        t_peak = t0 + dop + 0.1 * dhld
        peak_mask = (t >= t0) & (t <= t_peak)
        if peak_mask.sum() > 0:
            self.w[peak_mask] = 25.0

    def cost_function(self, D_multipliers):
        """Evaluate cost function for a given set of diameter multipliers."""
        if self.stop_requested:
            raise StopIteration

        self.eval_count += 1
        D_array = np.asarray(D_multipliers, dtype=float) * self.D_nom

        # Hard physical bounds
        if np.any(D_array < 0.01) or np.any(D_array > 2.0 * self.D_nom):
            return 1e10

        params = self.base_params.copy()
        params['D'] = D_array
        params['verbose'] = False

        try:
            res = run_gas_moc(**params)

            if np.any(~np.isfinite(res['P_down_pt'])):
                return 1e10

            # Interpolate model onto PT time base
            p_interp = np.interp(self.t_pt, res['time'], res['P_down_pt'])
            residuals = p_interp - self.p_pt

            # Weighted RMSE
            w_res2 = self.w * residuals ** 2
            misfit = float(np.sqrt(np.mean(w_res2)))
            rmse_uw = float(np.sqrt(np.mean(residuals ** 2))) * 1000.0

            # Regularisation terms
            smoothness = float(np.mean(np.diff(D_array) ** 2))
            total_var = float(np.mean((D_array - self.D_initial) ** 2))

            # Cost with regularisation
            cost_total = (misfit
                          + self.lambda_smooth * smoothness
                          + self.lambda_tv * total_var)

            improved = False
            if misfit < self.best_cost:
                self.best_cost = misfit
                self.best_D_array = D_array.copy()
                improved = True

            rec = {
                'eval': self.eval_count,
                'D_mean': float(D_array.mean()),
                'D_std': float(D_array.std()),
                'D_min': float(D_array.min()),
                'D_max': float(D_array.max()),
                'cost': misfit,
                'cost_total': cost_total,
                'smoothness': smoothness,
                'total_var': total_var,
                'rmse_mbar': rmse_uw,
                'improved': improved,
            }
            self.history.append(rec)

            # Notify progress callback if registered
            if self.progress_callback:
                self.progress_callback({
                    'eval': self.eval_count,
                    'D_mean': D_array.mean(),
                    'D_std': D_array.std(),
                    'rmse': rmse_uw,
                    'improved': improved,
                    'cost': misfit,
                })

            return cost_total

        except StopIteration:
            raise
        except Exception:
            if self.stop_requested:
                raise StopIteration
            return 1e10

    def optimize(self, method='differential_evolution',
                 D_range=(0.80, 1.05), max_iter=100, workers=1, **kwargs):
        """
        Run optimization with the specified method.
        
        Parameters:
        -----------
        method : str
            Optimization method: 'differential_evolution', 'lbfgsb', or 'de_then_lbfgsb'
        D_range : tuple
            Min and max diameter multipliers (e.g., (0.70, 1.05))
        max_iter : int
            Maximum number of iterations
        workers : int
            Number of parallel workers. Note: In Streamlit, workers > 1 may cause issues.
        **kwargs : dict
            Additional arguments passed to the optimizer
            
        Returns:
        --------
        result : object or None
            Optimization result object, or None if stopped
        """
        global _WORKER_PARAMS

        self.running = True
        self.stop_requested = False
        self.eval_count = 0
        self.history = []
        self.best_cost = np.inf
        self.best_D_array = self.D_initial.copy()

        kwargs['workers'] = int(workers)

        lo = float(np.clip(D_range[0], 0.05, 0.999))
        hi = float(np.clip(D_range[1], lo + 0.01, 1.0))

        try:
            if method == 'differential_evolution':
                return self._optimize_de(D_range, max_iter, **kwargs)
            elif method == 'lbfgsb':
                return self._optimize_lbfgsb(D_range, max_iter)
            elif method == 'de_then_lbfgsb':
                self._optimize_de(D_range, max_iter, **kwargs)
                return self._optimize_lbfgsb(D_range, max(5, max_iter // 5))
            else:
                raise ValueError(f"Unknown method: {method}")
        except StopIteration:
            return None
        finally:
            self.running = False
            _WORKER_PARAMS = None

    def _optimize_de(self, D_range, max_iter, **kwargs):
        """Differential Evolution optimization."""
        global _WORKER_PARAMS

        lo = float(np.clip(D_range[0], 0.05, 0.999))
        hi = float(np.clip(D_range[1], lo + 0.01, 1.0))

        x0 = self.D_initial / self.D_nom
        bounds = [(lo, hi)] * self.n_segments
        popsize = max(kwargs.get('popsize', 15), 5)
        n_workers = int(kwargs.get('workers', 1))

        # Build seeded initial population (warm-start)
        rng = np.random.default_rng(42)
        n_pop = popsize * self.n_segments
        lhs = rng.uniform(lo, hi, size=(max(n_pop - 1, 1), self.n_segments))
        x0_clipped = np.clip(x0, lo, hi)
        init_pop = np.vstack([x0_clipped[np.newaxis, :], lhs])

        # Progress callback
        def _de_callback(xk, convergence=None):
            if self.stop_requested:
                return True
            D_arr = np.asarray(xk, dtype=float) * self.D_nom
            cost = self.cost_function(xk)
            return False

        if n_workers > 1:
            # Parallel path
            wp = _MOCWorkerParams(
                base_params=self.base_params,
                D_nom=self.D_nom,
                t_pt=self.t_pt,
                p_pt=self.p_pt,
                w=self.w,
                D_initial=self.D_initial,
                lambda_smooth=self.lambda_smooth,
                lambda_tv=self.lambda_tv,
            )
            _WORKER_PARAMS = wp

            try:
                import multiprocessing as _mp
                _pool = _mp.Pool(
                    processes=n_workers,
                    initializer=_worker_initializer,
                    initargs=(wp,),
                )
                cost_fn = _moc_worker_cost
                workers_arg = _pool.map
            except Exception as e:
                # Fall back to serial if multiprocessing fails
                _WORKER_PARAMS = None
                n_workers = 1
                workers_arg = 1
                cost_fn = self.cost_function
                _pool = None
        else:
            _WORKER_PARAMS = None
            cost_fn = self.cost_function
            workers_arg = 1
            _pool = None

        try:
            result = differential_evolution(
                cost_fn,
                bounds=bounds,
                strategy=kwargs.get('strategy', 'best1bin'),
                maxiter=max_iter,
                popsize=popsize,
                tol=kwargs.get('tol', 1e-3),
                mutation=kwargs.get('mutation', (0.4, 1.2)),
                recombination=kwargs.get('recombination', 0.85),
                workers=workers_arg,
                updating='deferred',
                disp=False,
                polish=False,
                init=init_pop,
                atol=0,
                seed=42,
                callback=_de_callback if n_workers > 1 else None,
            )
        finally:
            if _pool is not None:
                try:
                    _pool.close()
                    _pool.join()
                except:
                    pass

        if n_workers > 1 and result is not None:
            try:
                self.cost_function(result.x)
            except:
                pass

        return result

    def _optimize_lbfgsb(self, D_range, max_iter):
        """L-BFGS-B optimization (gradient-based local optimization)."""
        lo = float(np.clip(D_range[0], 0.05, 0.999))
        hi = float(np.clip(D_range[1], lo + 0.01, 2.0))

        x0 = self.best_D_array / self.D_nom
        x0 = np.clip(x0, lo, hi)
        bounds = [(lo, hi)] * self.n_segments

        return minimize(
            self.cost_function, x0=x0,
            method='L-BFGS-B',
            bounds=bounds,
            options={
                'maxiter': max_iter,
                'ftol': 1e-3,
                'gtol': 1e-3,
                'eps': 1e-4,
                'disp': False,
            },
        )

    def stop(self):
        """Stop the running optimization."""
        self.stop_requested = True


# =============================================================================
#  UTILITY FUNCTIONS
# =============================================================================

def build_initial_profile(D_nom, n_segments, profile_type='uniform', **kwargs):
    """
    Build initial diameter profile.
    
    Parameters:
    -----------
    D_nom : float
        Nominal diameter (m)
    n_segments : int
        Number of segments
    profile_type : str
        'uniform' or 'probable'
    **kwargs : dict
        Additional parameters for probable profile:
        - D_init: baseline diameter multiplier (default: 0.95)
        - D_mult: reduced diameter multiplier (default: 0.75)
        - L_ds: location from downstream (m) (default: 200.0)
        - seg_len: reduced segment length (m) (default: 1000.0)
        - L: pipe length (m) (default: 8000.0)
        - dx: grid spacing (m) (default: 200.0)
        
    Returns:
    --------
    D_prof : numpy.ndarray
        Diameter profile array (m)
    """
    if profile_type == "uniform" or n_segments == 0:
        return np.full(n_segments, D_nom)
    
    L = kwargs.get('L', 8000.0)
    dx = kwargs.get('dx', 200.0)
    D_init = kwargs.get('D_init', 0.95)
    D_mult = kwargs.get('D_mult', 0.75)
    L_ds = kwargs.get('L_ds', 200.0)
    seg_len = kwargs.get('seg_len', 1000.0)
    
    D_prof = np.full(n_segments, D_nom)
    pos_start = L - L_ds - seg_len
    pos_end = L - L_ds
    
    for i in range(n_segments):
        x_mid = (i + 0.5) * dx
        if pos_start <= x_mid <= pos_end:
            D_prof[i] = D_nom * D_mult
        else:
            D_prof[i] = D_nom * D_init
    
    return D_prof


def get_base_params(config):
    """
    Extract base simulation parameters from configuration dict.
    
    Parameters:
    -----------
    config : dict
        Configuration dictionary with all parameter values
        
    Returns:
    --------
    params : dict
        Dictionary of parameters for run_gas_moc
    """
    T_K = float(config.get('T_celsius', 25.0)) + 273.15
    
    return {
        'L': float(config.get('L', 8000.0)),
        'dx': float(config.get('dx', 200.0)),
        'eps': float(config.get('eps_mm', 0.045)) / 1000.0,
        'Z_factor': float(config.get('Z_factor', 0.996)),
        'gamma': float(config.get('gamma', 1.26)),
        'R_gas': float(config.get('R_gas', 424.0)),
        'T_K': T_K,
        'mu_dyn': float(config.get('mu_dyn', 1.1e-5)),
        'P_upstream': float(config.get('P_upstream_bar', 8.098)) * 1e5,
        'P_atm': float(config.get('P_atm_bar', 1.0)) * 1e5,
        'valve_position': float(config.get('valve_pos_m', 8000.0)),
        'x_pt_m': float(config.get('x_pt_m', 7600.0)),
        'xT': float(config.get('xT', 0.9)),
        'Fp': float(config.get('Fp', 1.0)),
        'Cv_max': float(config.get('Cv_max', 500.0)),
        't_valve_open_start': float(config.get('t_valve_open_start', 30.0)),
        't_valve_opening': float(config.get('t_valve_opening', 5.0)),
        't_valve_hold_open': float(config.get('t_valve_hold_open', 60.0)),
        't_valve_closing': float(config.get('t_valve_closing', 5.0)),
        'K_multiplier': float(config.get('K_multiplier', 5.0)),
        'T_total': float(config.get('T_total', 200.0)),
        'beta': float(config.get('beta', 0.9)),
        'B_factor': float(config.get('B_factor', 1.0)),
        'upstream_bc': config.get('upstream_bc', 'CLOSED_END'),
        'V_tank': float(config.get('V_tank', 10.0)),
        'elevation_profile': config.get('elevation_profile', None),
        'g': float(config.get('g', 9.81)),
    }


def get_default_config():
    """Return default configuration dictionary."""
    return {
        # Geometry
        'L': 8000.0,
        'dx': 200.0,
        'D_nom': 0.1937,
        'eps_mm': 0.045,
        'x_pt_m': 7600.0,
        'valve_pos_m': 8000.0,
        'g': 9.81,
        
        # Gas properties
        'T_celsius': 25.0,
        'mu_dyn': 1.1e-5,
        'R_gas': 424.0,
        'Z_factor': 0.996,
        'gamma': 1.26,
        
        # Pressures
        'P_upstream_bar': 8.098,
        'P_atm_bar': 1.0,
        'upstream_bc': 'CLOSED_END',
        'V_tank': 10.0,
        
        # Valve parameters
        'xT': 0.9,
        'Fp': 1.0,
        'Cv_max': 500.0,
        'K_multiplier': 5.0,
        't_valve_open_start': 30.0,
        't_valve_opening': 5.0,
        't_valve_hold_open': 60.0,
        't_valve_closing': 5.0,
        'T_total': 200.0,
        
        # MOC numerical
        'beta': 0.9,
        'B_factor': 1.0,
        
        # Optimization
        'profile_type': 'uniform',
        'prob_D_init': 0.95,
        'prob_D_mult': 0.75,
        'prob_L_ds': 200.0,
        'prob_seg_len': 1000.0,
        'D_range_min': 0.70,
        'D_range_max': 1.05,
        'max_iter': 150,
        'popsize': 15,
        'lambda_smooth': 1e-6,
        'lambda_tv': 1e-7,
        'workers': 1,
        'method': 'differential_evolution',
    }
