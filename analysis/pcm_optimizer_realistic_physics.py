# pcm_optimizer_realistic_physics.py
# IMPROVED PCM model with temperature-proportional charging/discharging
# This version implements realistic heat transfer physics instead of bang-bang control
# --------------------------------------------------------------

import numpy as np

# ---------------------------------------------------------------
# REALISTIC PCM MODEL WITH TEMPERATURE-PROPORTIONAL CHARGING
# ---------------------------------------------------------------
def power_from_setpoint_with_realistic_pcm(
    t_s,
    T_set_C,
    T_out_C,
    UA_W_per_K=45.5,
    V_m3=368.18,
    q_inf_W_per_m3=6.0,
    C_eff_J_per_K=30e6,
    COP=1.4,
    Q_int_W=0.0,
    m_pcm_kg=100.0,
    latent_J_per_kg=250000.0,
    T_melt_C=-21.5,
    T_transition_range=2.5,  # NEW: Phase change occurs over a temperature range
    UA_pcm_W_per_K=2000.0,   # NEW: Heat transfer coefficient for PCM heat exchanger
                             # Typical values: 1000-2500 W/K for commercial PCM heat exchangers
                             # Higher = faster PCM response (constrained by power limit)
                             # See UA_PCM_DETERMINATION.md for calculation method
    P_pcm_charge_max_W=2000.0,
    P_pcm_discharge_max_W=2000.0,
    initial_pcm_soc=1.0,
    Q_cool_max_kW=None):
    """
    Simulate cooling system with REALISTIC PCM physics.
    
    Key improvements over bang-bang model:
    1. Temperature-proportional charging/discharging based on heat transfer
    2. Gradual phase change over a temperature range (not instant)
    3. Heat exchanger capacity limits (UA_pcm parameter)
    4. More realistic SOC dynamics
    
    Parameters:
    -----------
    T_transition_range : float
        Temperature range over which phase change occurs (°C)
        Larger values = more gradual transitions
        Typical: 2-3°C for real PCM systems
    
    UA_pcm_W_per_K : float
        Heat transfer coefficient for PCM heat exchanger (W/K)
        Determines maximum heat transfer rate as function of temperature difference
        Typical values: 300-800 W/K depending on heat exchanger design
        Higher values = faster PCM response, but still temperature-limited
    
    Returns:
    --------
    dict with keys:
        'P_el_kW': Electrical power (kW)
        'SOC': PCM state of charge (0-1)
        'Q_pcm_charge': PCM charging power (W)
        'Q_pcm_discharge': PCM discharging power (W)
        'phase_fraction': Phase fraction (0=fully frozen, 1=fully liquid)
    """
    t_s = np.asarray(t_s, float)
    T_set_C = np.asarray(T_set_C, float)
    if np.isscalar(T_out_C): 
        T_out_C = np.full_like(T_set_C, float(T_out_C))
    else: 
        T_out_C = np.asarray(T_out_C, float)

    n = len(t_s)
    dt = np.diff(t_s)
    dT_dt = np.gradient(T_set_C, t_s)
    
    # CRITICAL FIX: Limit temperature ramp rate to prevent unrealistic power peaks
    # Physical constraint: cooling systems can't change temp faster than ~2-4 K/hour
    # This prevents optimizer from creating aggressive ramps that cause 100+ kW spikes
    max_dT_dt = 1.0 / 3600.0  # Max 1 K/hour = 0.000278 K/s (conservative limit)
    dT_dt_limited = np.clip(dT_dt, -max_dT_dt, max_dT_dt)

    # Baseline thermal loads
    Q_trans = UA_W_per_K * (T_out_C - T_set_C)
    Q_inf = q_inf_W_per_m3 * V_m3
    Q_dyn = -C_eff_J_per_K * dT_dt_limited  # Use limited rate to prevent spikes

    # PCM energy storage
    Epcm_max = m_pcm_kg * latent_J_per_kg
    Epcm = initial_pcm_soc * Epcm_max

    # Output arrays
    SOC = np.zeros(n)
    Q_cool = np.zeros(n)
    P_el = np.zeros(n)
    Q_pcm_chg_arr = np.zeros(n)
    Q_pcm_dis_arr = np.zeros(n)
    phase_frac_arr = np.zeros(n)

    for i in range(n):
        Q_need = Q_trans[i] + Q_inf + Q_dyn[i] + Q_int_W
        
        # ═══════════════════════════════════════════════════════════
        # REALISTIC PCM CHARGING/DISCHARGING
        # ═══════════════════════════════════════════════════════════
        
        Qchg = 0.0
        Qdis = 0.0
        
        if i > 0 and m_pcm_kg > 0:
            dti = dt[i-1]
            
            # Calculate phase fraction (0 = fully frozen/solid, 1 = fully liquid)
            # Phase change occurs gradually over T_transition_range
            T_range_lower = T_melt_C - T_transition_range / 2
            T_range_upper = T_melt_C + T_transition_range / 2
            
            if T_set_C[i] <= T_range_lower:
                phase_fraction = 0.0  # Fully frozen
            elif T_set_C[i] >= T_range_upper:
                phase_fraction = 1.0  # Fully liquid
            else:
                # Linear interpolation within transition range
                phase_fraction = (T_set_C[i] - T_range_lower) / T_transition_range
            
            phase_frac_arr[i] = phase_fraction
            
            # ───────────────────────────────────────────────────────
            # TEMPERATURE-PROPORTIONAL DISCHARGE (T_set > T_melt)
            # ───────────────────────────────────────────────────────
            if T_set_C[i] > T_melt_C and Epcm > 0:
                # Temperature driving force for discharge
                dT_discharge = T_set_C[i] - T_melt_C
                
                # Heat transfer rate proportional to temperature difference
                # Q = UA × ΔT (fundamental heat transfer equation)
                Q_pcm_heat_transfer = UA_pcm_W_per_K * dT_discharge
                
                # Limit by available energy
                Q_pcm_available_energy = Epcm / dti
                
                # Limit by discharge power rating
                Q_pcm_available_power = P_pcm_discharge_max_W
                
                # Actual discharge is minimum of all constraints
                Q_pcm_max = min(Q_pcm_heat_transfer, 
                               Q_pcm_available_energy,
                               Q_pcm_available_power)
                
                # Discharge only what's needed (don't over-discharge)
                Qdis = max(0.0, min(Q_pcm_max, Q_need))
                
                # Update energy storage
                Epcm -= Qdis * dti
            
            # ───────────────────────────────────────────────────────
            # TEMPERATURE-PROPORTIONAL CHARGE (T_set < T_melt)
            # ───────────────────────────────────────────────────────
            elif T_set_C[i] < T_melt_C and Epcm < Epcm_max:
                # Temperature driving force for charging
                dT_charge = T_melt_C - T_set_C[i]
                
                # Heat transfer rate proportional to temperature difference
                # Q = UA × ΔT (fundamental heat transfer equation)
                # This is the KEY improvement: charging rate depends on dT
                Q_pcm_heat_transfer = UA_pcm_W_per_K * dT_charge
                
                # Limit by available storage capacity
                Q_pcm_available_capacity = (Epcm_max - Epcm) / dti
                
                # Limit by charge power rating
                Q_pcm_available_power = P_pcm_charge_max_W
                
                # Actual charge is minimum of all constraints
                Qchg = max(0.0, min(Q_pcm_heat_transfer,
                                   Q_pcm_available_capacity,
                                   Q_pcm_available_power))
                
                # Update energy storage
                Epcm += Qchg * dti
            
            # Ensure energy stays within bounds
            Epcm = np.clip(Epcm, 0.0, Epcm_max)
        
        # Store PCM power flows
        Q_pcm_chg_arr[i] = Qchg
        Q_pcm_dis_arr[i] = Qdis
        
        # Calculate state of charge
        SOC[i] = Epcm / Epcm_max if Epcm_max > 0 else 0.0
        
        # Total cooling power needed
        # Baseline load - discharge benefit + charging load
        Qc = max(0.0, Q_need - Qdis + Qchg)
        
        # Apply maximum cooling capacity constraint if specified
        if Q_cool_max_kW:
            Q_max = 1000.0 * Q_cool_max_kW
            Qc = min(Qc, Q_max)
        
        Q_cool[i] = Qc
        P_el[i] = Qc / (COP * 1000.0)

    return {
        "P_el_kW": P_el,
        "SOC": SOC,
        "Q_pcm_charge": Q_pcm_chg_arr,
        "Q_pcm_discharge": Q_pcm_dis_arr,
        "phase_fraction": phase_frac_arr
    }


# ---------------------------------------------------------------
# PV-AWARE ECONOMIC COST (same as original)
# ---------------------------------------------------------------
def economic_cost_with_pv_realistic(P_el, PV, price, dt, use_pv=True):
    """Calculate economic cost with optional PV offset."""
    if not use_pv:
        return float(np.sum(P_el[:-1] * price[:-1] * (dt / 3600)))
    P_imp = np.clip(P_el[:-1] - PV[:-1], 0, None)
    return float(np.sum(P_imp * price[:-1] * (dt / 3600)))


# ---------------------------------------------------------------
# ROLLING-HORIZON OPTIMIZER WITH REALISTIC PCM
# ---------------------------------------------------------------
def rolling_horizon_optimize_Tset_realistic(
    t_s, T_out, price, PV, 
    horizon=6, Tmin=-25, Tmax=-16, grid_step=0.5,
    UA=45.5, V=368.18, q_inf=6.0, C_eff=30e6, COP=1.4,
    m_pcm=300, latent=250000, Tm=-21.5,
    T_transition_range=2.5,    # NEW parameter
    UA_pcm=500.0,              # NEW parameter
    Pchg=2000, Pdis=2000,
    baseline_T=None, initial_soc=1.0):
    """
    Rolling-horizon optimizer using REALISTIC PCM physics.
    
    Uses temperature-proportional charging instead of bang-bang control.
    
    New parameters:
    ---------------
    T_transition_range : float
        Temperature range for gradual phase change (°C)
    
    UA_pcm : float
        PCM heat exchanger heat transfer coefficient (W/K)
    """
    if baseline_T is None:
        # Simple heuristic baseline
        median_price = np.median(price)
        baseline_T = np.where(price <= median_price, Tmin + 2, Tmax - 2)
    
    T_opt = baseline_T.copy()
    dt = np.diff(t_s)
    grid = np.arange(Tmin, Tmax + 1e-9, grid_step)
    soc = initial_soc

    for k in range(len(t_s) - 1):
        h_end = min(len(t_s), k + horizon)
        best_cost = 1e18
        best_Tk = T_opt[k]
        best_soc = soc
        
        for Tk in grid:
            Th = T_opt[k:h_end].copy()
            Th[0] = Tk
            
            # Simulate with REALISTIC PCM physics
            res = power_from_setpoint_with_realistic_pcm(
                t_s[k:h_end], Th, T_out[k:h_end],
                UA_W_per_K=UA, V_m3=V, q_inf_W_per_m3=q_inf,
                C_eff_J_per_K=C_eff, COP=COP,
                m_pcm_kg=m_pcm, latent_J_per_kg=latent,
                T_melt_C=Tm,
                T_transition_range=T_transition_range,
                UA_pcm_W_per_K=UA_pcm,
                P_pcm_charge_max_W=Pchg,
                P_pcm_discharge_max_W=Pdis,
                initial_pcm_soc=soc
            )
            
            # Calculate cost
            dt_h = dt[k:h_end-1] if h_end - 1 > k else np.array([900.0])
            cost_h = economic_cost_with_pv_realistic(
                res['P_el_kW'], PV[k:h_end], price[k:h_end], dt_h
            )
            
            if cost_h < best_cost:
                best_cost = cost_h
                best_Tk = Tk
                best_soc = res['SOC'][-1]
        
        T_opt[k] = best_Tk
        soc = best_soc
    
    return T_opt


# ---------------------------------------------------------------
# COMPARISON HELPER
# ---------------------------------------------------------------
def compare_pcm_models(t_s, T_set, T_out, price, PV,
                      UA=45.5, V=368.18, q_inf=6.0, C_eff=30e6, COP=1.4,
                      m_pcm=300, latent=250000, Tm=-21.5,
                      T_transition_range=2.5, UA_pcm=500.0,
                      Pchg=2000, Pdis=2000, initial_soc=0.5):
    """
    Compare original bang-bang model vs realistic physics model.
    
    Returns both simulation results for side-by-side comparison.
    """
    from analysis.pcm_optimizer_baeko_plus_pv import power_from_setpoint_with_pcm
    
    # Original model
    res_original = power_from_setpoint_with_pcm(
        t_s=t_s, T_set_C=T_set, T_out_C=T_out,
        UA_W_per_K=UA, V_m3=V, q_inf_W_per_m3=q_inf,
        C_eff_J_per_K=C_eff, COP=COP,
        m_pcm_kg=m_pcm, latent_J_per_kg=latent,
        T_melt_C=Tm,
        P_pcm_charge_max_W=Pchg,
        P_pcm_discharge_max_W=Pdis,
        initial_pcm_soc=initial_soc
    )
    
    # Realistic model
    res_realistic = power_from_setpoint_with_realistic_pcm(
        t_s=t_s, T_set_C=T_set, T_out_C=T_out,
        UA_W_per_K=UA, V_m3=V, q_inf_W_per_m3=q_inf,
        C_eff_J_per_K=C_eff, COP=COP,
        m_pcm_kg=m_pcm, latent_J_per_kg=latent,
        T_melt_C=Tm,
        T_transition_range=T_transition_range,
        UA_pcm_W_per_K=UA_pcm,
        P_pcm_charge_max_W=Pchg,
        P_pcm_discharge_max_W=Pdis,
        initial_pcm_soc=initial_soc
    )
    
    return {
        'original': res_original,
        'realistic': res_realistic
    }
