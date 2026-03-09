
import numpy as np
from copy import deepcopy
import os
import sys

def _get_systems():
    """Lazily import SYSTEMS so path resolution works in any calling context."""
    _root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from config_test_Pilot import SYSTEMS as _S
    return _S

# ---------------------------------------------------------------------
# Two-node thermal model for cold-room simulation
# ---------------------------------------------------------------------
# The room is modelled as two coupled thermal nodes:
#
#   Node 1 – AIR (+ surfaces):  small thermal mass  C_air  [J/K]
#   Node 2 – PRODUCT (goods):   large thermal mass  C_prod [J/K]
#
#   C_air  = air_fraction * C_eff       (default air_fraction = 0.02)
#   C_prod = (1 - air_fraction) * C_eff
#
# Heat flows:
#   Q_trans  = UA * (T_out - T_air)        envelope losses
#   Q_inf    = q_inf * V                   infiltration (const)
#   Q_int    = internal gains (const)
#   Q_ap     = h_ap * (T_air - T_prod)     air ↔ product coupling
#
# The compressor controls T_air to follow the setpoint.
# T_prod evolves passively:  C_prod * dT_prod/dt = h_ap * (T_air - T_prod)
#
# Cooling demand at each step:
#   Q_cool = Q_trans + Q_inf + Q_int + C_air * (T_air_prev - T_set)/dt + Q_ap
#          = (what must be removed to bring air to T_set) + product coupling
#
# This means:
#   - Pre-cooling (lowering T_set) costs only C_air * dT (cheap)
#   - Warming (raising T_set) → compressor off, Q_cool = 0
#   - Product mass slowly exchanges heat with air (free thermal buffer)
# ---------------------------------------------------------------------

def power_from_setpoint_two_node(
    t_s,                # 1D array of seconds (strictly increasing)
    T_set_C,            # 1D array [°C] air-temperature setpoint schedule
    T_out_C,            # 1D array [°C] ambient (or scalar; will broadcast)
    UA_W_per_K=45.5,    # W/K  envelope heat transfer
    V_m3=368.18,        # m³   room volume
    q_inf_W_per_m3=6.0, # W/m³ infiltration heat gain per unit volume
    C_eff_J_per_K=30e6, # J/K  TOTAL thermal capacity (air + product)
    COP=1.4,            # cooling COP (electrical → thermal)
    Q_int_W=0.0,        # W    constant internal heat gain
    air_fraction=0.02,  # fraction of C_eff assigned to air node
    h_ap_W_per_K=None,  # W/K  air-product coupling (None → auto-size)
    # PCM parameters (set m_pcm_kg=0 to disable)
    m_pcm_kg=0.0,
    latent_J_per_kg=250_000.0,
    T_melt_C=-21.5,
    hysteresis_K=0.3,
    P_pcm_charge_max_W=2_000.0,
    P_pcm_discharge_max_W=2_000.0,
    initial_pcm_soc=1.0,
    # Optional refrigeration capacity limit
    Q_cool_max_kW=None,
    # Optional explicit PCM schedule (overrides T_set-based logic)
    # Array of same length as t_s:  +1 = charge, -1 = discharge, 0 = idle
    # When None (default), uses original T_set vs T_melt logic.
    pcm_schedule=None,
):
    """
    Two-node thermal model: air (fast) + product (slow).

    The compressor forces the air node to the setpoint; the product
    node drifts passively via convective coupling.  This correctly
    captures the low cost of pre-cooling air and the large free
    thermal buffer of product mass.

    Returns dict with P_el_kW, Q_cool_kW, component breakdowns,
    PCM SOC, T_product trajectory, and feasibility flags.
    """
    t_s     = np.asarray(t_s, dtype=float)
    T_set_C = np.asarray(T_set_C, dtype=float)
    if np.isscalar(T_out_C):
        T_out_C = np.full_like(T_set_C, float(T_out_C))
    else:
        T_out_C = np.asarray(T_out_C, dtype=float)

    n = len(t_s)
    if not (len(T_set_C) == n and len(T_out_C) == n and n >= 2):
        raise ValueError("t_s, T_set_C, T_out_C must have same length >= 2")
    dt = np.diff(t_s)
    if np.any(dt <= 0):
        raise ValueError("t_s must be strictly increasing (seconds)")

    # ── Split thermal capacity ──────────────────────────────────
    C_air  = air_fraction * C_eff_J_per_K
    C_prod = (1.0 - air_fraction) * C_eff_J_per_K

    # Auto-size air-product coupling so product time constant ≈ 4 hours
    if h_ap_W_per_K is None:
        tau_prod_s = 4.0 * 3600.0   # 4 hours
        h_ap_W_per_K = C_prod / tau_prod_s

    # ── State initialisation ────────────────────────────────────
    T_air  = np.zeros(n)           # air temperature (= setpoint)
    T_prod = np.zeros(n)           # product temperature
    T_air[0]  = T_set_C[0]
    T_prod[0] = T_set_C[0]        # assume equilibrium at start

    # Steady-state loads (vectorised for output)
    Q_trans_W = UA_W_per_K * (T_out_C - T_set_C)   # >0 when T_out > T_set (heat in)
    Q_inf_W   = q_inf_W_per_m3 * V_m3 * np.ones(n)
    Q_int_Wv  = Q_int_W * np.ones(n)

    # PCM state
    E_pcm_max_J = m_pcm_kg * latent_J_per_kg
    E_pcm_J     = np.clip(initial_pcm_soc, 0.0, 1.0) * E_pcm_max_J

    # Output arrays
    Q_ap_W        = np.zeros(n)    # air → product heat flow
    Q_dyn_air_W   = np.zeros(n)    # energy to change air temperature
    Q_need_W      = np.zeros(n)    # total thermal demand on compressor
    Q_cool_W      = np.zeros(n)    # actual cooling delivered
    Q_pcm_chg_W   = np.zeros(n)
    Q_pcm_dis_W   = np.zeros(n)
    P_el_kW       = np.zeros(n)
    SOC           = np.zeros(n)
    Q_shortfall_W = np.zeros(n)

    SOC[0] = 0.0 if E_pcm_max_J == 0 else E_pcm_J / E_pcm_max_J

    # Parse explicit PCM schedule if provided
    _pcm_sched = None
    if pcm_schedule is not None:
        _pcm_sched = np.asarray(pcm_schedule, dtype=float)
        if len(_pcm_sched) != n:
            raise ValueError(f"pcm_schedule length ({len(_pcm_sched)}) != t_s length ({n})")

    for i in range(1, n):
        dti = dt[i - 1]   # seconds for this step

        # Air node must reach T_set_C[i] from T_air[i-1]
        T_air[i] = T_set_C[i]

        # Heat flow from product to air (>0 when product warmer than air)
        Q_ap_W[i] = h_ap_W_per_K * (T_prod[i - 1] - T_air[i])

        # Energy to change air temperature
        Q_dyn_air_W[i] = C_air * (T_air[i - 1] - T_air[i]) / dti  # >0 when cooling

        # Steady-state loads at this step
        Q_ss = Q_trans_W[i] + Q_inf_W[i] + Q_int_Wv[i]

        # Total thermal demand: steady-state + air dynamic + product coupling
        # Q_ap > 0 means product is warmer → dumps heat into air → more cooling
        # Q_dyn_air > 0 means air is being cooled → compressor must work
        Q_need_W[i] = Q_ss + Q_dyn_air_W[i] + Q_ap_W[i]

        # ── PCM logic ──────────────────────────────────────────
        Qdis = 0.0
        Qchg = 0.0

        if (m_pcm_kg > 0) and (E_pcm_max_J > 0):
            if _pcm_sched is not None:
                # Explicit schedule: +1 charge, -1 discharge, 0 idle
                cmd = _pcm_sched[i]
                if cmd > 0:
                    # Charge: extra cooling to freeze PCM
                    cap_W = min((E_pcm_max_J - E_pcm_J) / dti, P_pcm_charge_max_W)
                    Qchg = max(0.0, cap_W)
                    E_pcm_J += Qchg * dti
                elif cmd < 0:
                    # Discharge: PCM offsets cooling demand
                    avail_W = min(E_pcm_J / dti, P_pcm_discharge_max_W)
                    Qdis = max(0.0, min(avail_W, max(0.0, Q_need_W[i])))
                    E_pcm_J -= Qdis * dti
                # cmd == 0 → idle, no charge or discharge
            else:
                # Original T_set-based logic
                if T_set_C[i] >= T_melt_C:
                    # Discharge: PCM offsets cooling demand
                    avail_W = min(E_pcm_J / dti, P_pcm_discharge_max_W)
                    Qdis = max(0.0, min(avail_W, max(0.0, Q_need_W[i])))
                    E_pcm_J -= Qdis * dti
                elif T_set_C[i] <= (T_melt_C - hysteresis_K):
                    # Charge: extra cooling to freeze PCM
                    cap_W = min((E_pcm_max_J - E_pcm_J) / dti, P_pcm_charge_max_W)
                    Qchg = max(0.0, cap_W)
                    E_pcm_J += Qchg * dti
            E_pcm_J = float(np.clip(E_pcm_J, 0.0, E_pcm_max_J))

        SOC[i] = 0.0 if E_pcm_max_J == 0 else E_pcm_J / E_pcm_max_J

        # Compressor cooling (thermal side)
        Q_cool_W[i] = max(0.0, Q_need_W[i] - Qdis + Qchg)

        # Apply capacity limit
        if Q_cool_max_kW is not None:
            Q_max_W = 1000.0 * float(Q_cool_max_kW)
            if Q_cool_W[i] > Q_max_W:
                Q_shortfall_W[i] = Q_cool_W[i] - Q_max_W
                Q_cool_W[i] = Q_max_W

        Q_pcm_chg_W[i] = Qchg
        Q_pcm_dis_W[i] = Qdis
        P_el_kW[i]      = Q_cool_W[i] / (COP * 1000.0)

        # ── Evolve product temperature passively ───────────────
        # dT_prod = h_ap * (T_air - T_prod) * dt / C_prod
        dT_prod = h_ap_W_per_K * (T_air[i] - T_prod[i - 1]) * dti / C_prod
        T_prod[i] = T_prod[i - 1] + dT_prod

    return {
        "P_el_kW":        P_el_kW,
        "Q_cool_kW":      Q_cool_W / 1000.0,
        "Q_need_kW":      Q_need_W / 1000.0,
        "Q_trans_kW":     Q_trans_W / 1000.0,
        "Q_inf_kW":       Q_inf_W / 1000.0,
        "Q_dyn_kW":       Q_dyn_air_W / 1000.0,
        "Q_ap_kW":        Q_ap_W / 1000.0,
        "Q_pcm_chg_kW":   Q_pcm_chg_W / 1000.0,
        "Q_pcm_dis_kW":   Q_pcm_dis_W / 1000.0,
        "SOC":            SOC,
        "Q_shortfall_kW": Q_shortfall_W / 1000.0,
        "T_air_C":        T_air,
        "T_product_C":    T_prod,
    }


# Keep legacy single-node model available under original name
def power_from_setpoint_with_pcm(
    t_s, T_set_C, T_out_C,
    UA_W_per_K=45.5, V_m3=368.18, q_inf_W_per_m3=6.0,
    C_eff_J_per_K=30e6, COP=1.4, Q_int_W=0.0,
    m_pcm_kg=100.0, latent_J_per_kg=250_000.0,
    T_melt_C=-21.5, hysteresis_K=0.3,
    P_pcm_charge_max_W=2_000.0, P_pcm_discharge_max_W=2_000.0,
    initial_pcm_soc=1.0, Q_cool_max_kW=None,
    pcm_schedule=None,
):
    """Legacy single-node wrapper — delegates to two-node model."""
    return power_from_setpoint_two_node(
        t_s=t_s, T_set_C=T_set_C, T_out_C=T_out_C,
        UA_W_per_K=UA_W_per_K, V_m3=V_m3,
        q_inf_W_per_m3=q_inf_W_per_m3,
        C_eff_J_per_K=C_eff_J_per_K, COP=COP, Q_int_W=Q_int_W,
        m_pcm_kg=m_pcm_kg, latent_J_per_kg=latent_J_per_kg,
        T_melt_C=T_melt_C, hysteresis_K=hysteresis_K,
        P_pcm_charge_max_W=P_pcm_charge_max_W,
        P_pcm_discharge_max_W=P_pcm_discharge_max_W,
        initial_pcm_soc=initial_pcm_soc,
        Q_cool_max_kW=Q_cool_max_kW,
        pcm_schedule=pcm_schedule,
    )


 #---------------------------------------------------------------------
# 3) Helper to run any system by name (PCM on/off + optional overrides)
# ---------------------------------------------------------------------
def simulate_system(
    system_name: str,
    t_s,
    T_set_C,
    T_out_C,
    use_pcm: bool = False,
    overrides: dict | None = None,
    pcm_schedule=None,
):
    """
    Simulate one of the four systems by pulling defaults from SYSTEMS
    and optionally overriding selected parameters.

    Parameters
    ----------
    system_name : str
        One of: "Pluskühlung 1", "Pluskühlung 2", "Tiefkühlung 1", "Tiefkühlung 2".
    t_s, T_set_C, T_out_C :
        Time base, setpoint trajectory, and ambient (scalar or array).
    use_pcm : bool
        If False (default), PCM is disabled (m_pcm_kg=0). If True, uses dict defaults unless overridden.
    overrides : dict | None
        Flat dict of parameters to override (e.g., {"COP":2.6, "pcm":{"m_pcm_kg":600}}).
        Nested keys under "pcm" merge into PCM defaults.

    Returns
    -------
    dict : Model output from power_from_setpoint_with_pcm(...)
    """
    SYSTEMS = _get_systems()
    if system_name not in SYSTEMS:
        raise KeyError(f"Unknown system '{system_name}'. Valid: {list(SYSTEMS.keys())}")

    # Deep copy base parameters
    base = deepcopy(SYSTEMS[system_name])

    # Merge overrides
    if overrides:
        for k, v in overrides.items():
            if k == "pcm" and isinstance(v, dict):
                base["pcm"].update(v)
            else:
                base[k] = v

    # Respect PCM toggle
    pcm = base["pcm"]
    if not use_pcm:
        pcm = deepcopy(pcm)
        pcm["m_pcm_kg"] = 0.0

    # Call the model
    result = power_from_setpoint_with_pcm(
        t_s=t_s,
        T_set_C=T_set_C,
        T_out_C=T_out_C,
        UA_W_per_K=base["UA_W_per_K"],
        V_m3=base["V_m3"],
        q_inf_W_per_m3=base["q_inf_W_per_m3"],
        C_eff_J_per_K=base["C_eff_J_per_K"],
        COP=base["COP"],
        Q_int_W=base["Q_int_W"],
        m_pcm_kg=pcm["m_pcm_kg"],
        latent_J_per_kg=pcm["latent_J_per_kg"],
        T_melt_C=pcm["T_melt_C"],
        hysteresis_K=pcm["hysteresis_K"],
        P_pcm_charge_max_W=pcm["P_pcm_charge_max_W"],
        P_pcm_discharge_max_W=pcm["P_pcm_discharge_max_W"],
        initial_pcm_soc=pcm["initial_pcm_soc"],
        Q_cool_max_kW=base["Q_cool_max_kW"],
        pcm_schedule=pcm_schedule,
    )
    return result

# ---------------------------------------------------------------------
# 4) Tiny helpers (optional)
# ---------------------------------------------------------------------
def get_system_params(system_name: str) -> dict:
    """Return a deep copy of the parameter dict for inspection/logging."""
    SYSTEMS = _get_systems()
    if system_name not in SYSTEMS:
        raise KeyError(f"Unknown system '{system_name}'")
    return deepcopy(SYSTEMS[system_name])

def validate_Tset_bounds(system_name: str, T_set_C: np.ndarray) -> None:
    """Optional: assert that T_set_C stays within the room's allowed band."""
    SYSTEMS = _get_systems()
    lo, hi = SYSTEMS[system_name]["T_set_bounds_C"]
    if np.any(T_set_C < lo) or np.any(T_set_C > hi):
        raise ValueError(f"{system_name} setpoint out of bounds [{lo},{hi}] °C")

# ---------------------------------------------------------------------
# 5) Example usage
# ---------------------------------------------------------------------
if __name__ == "__main__":
    # 24h demo with 10‑min steps
    hours = np.arange(0, 24, 1/6)
    t_s = (hours * 3600.0).astype(float)

    # Ambient (scalar or array)
    T_out = 4.0 + 3.0 * np.sin(2*np.pi*(hours-6)/24)  # simple winter curve

    # Example schedules
    Tset_plus = np.clip(2.5 + 0.8*np.sin(2*np.pi*(hours-5)/24), 0.0, 4.0)       # chilled
    Tset_tfk  = np.clip(-20 + 1.0*np.sin(2*np.pi*(hours-8)/24), -25.0, -16.0)   # deep‑freeze

    # Validate optional bounds
    validate_Tset_bounds("Pluskühlung 2", Tset_plus)
    validate_Tset_bounds("Tiefkühlung 2", Tset_tfk)

    # Run baseline (no PCM), then with PCM
    res_p2_no_pcm = simulate_system("Pluskühlung 2", t_s, Tset_plus, T_out, use_pcm=False)
    res_p2_pcm    = simulate_system("Pluskühlung 2", t_s, Tset_plus, T_out, use_pcm=True,
                                    overrides={"pcm": {"m_pcm_kg": 800}})

    res_tf2_no_pcm = simulate_system("Tiefkühlung 2", t_s, Tset_tfk, T_out, use_pcm=False)
    res_tf2_pcm    = simulate_system("Tiefkühlung 2", t_s, Tset_tfk, T_out, use_pcm=True,
                                     overrides={"pcm": {"m_pcm_kg": 600}})
    # Aggregate energy example (kWh)
    dt_h = np.diff(t_s)/3600.0
    def energy_kwh(P_el_kW):
        # trapezoid not needed; model uses stepwise power → rectangle with last value ignored
        return float(np.sum(P_el_kW[:-1] * dt_h))

    print("Pluskühlung 2 baseline (kWh):", energy_kwh(res_p2_no_pcm["P_el_kW"]))
    print("Pluskühlung 2 with PCM (kWh):", energy_kwh(res_p2_pcm["P_el_kW"]))
    print("Tiefkühlung 2 baseline (kWh):", energy_kwh(res_tf2_no_pcm["P_el_kW"]))
    print("Tiefkühlung 2 with PCM (kWh):", energy_kwh(res_tf2_pcm["P_el_kW"]))
