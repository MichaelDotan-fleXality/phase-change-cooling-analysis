# pcm_optimizer_baeko_plus_pv.py
# Full BÄKO PCM optimizer with PV support (USE_PV toggle)
# NOTE: This version integrates PV into:
#  - cost function
#  - PCM sweep
#  - rolling-horizon optimizer
#  - heuristic effective price
# --------------------------------------------------------------

USE_PV = True  # Toggle PV integration ON/OFF

import numpy as np
import csv
import math
import matplotlib.pyplot as plt

# ---------------------------------------------------------------
# BÄKO PCM MODEL
# ---------------------------------------------------------------
def power_from_setpoint_with_pcm(
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
    hysteresis_K=0.3,
    P_pcm_charge_max_W=2000.0,
    P_pcm_discharge_max_W=2000.0,
    initial_pcm_soc=1.0,
    Q_cool_max_kW=None):

    t_s = np.asarray(t_s, float)
    T_set_C = np.asarray(T_set_C, float)
    if np.isscalar(T_out_C): T_out_C = np.full_like(T_set_C, float(T_out_C))
    else: T_out_C = np.asarray(T_out_C, float)

    n = len(t_s)
    dt = np.diff(t_s)
    dT_dt = np.gradient(T_set_C, t_s)

    Q_trans = UA_W_per_K * (T_out_C - T_set_C)
    Q_inf = q_inf_W_per_m3 * V_m3
    Q_dyn = -C_eff_J_per_K * dT_dt

    Epcm_max = m_pcm_kg * latent_J_per_kg
    Epcm = initial_pcm_soc * Epcm_max

    SOC = np.zeros(n)
    Q_cool = np.zeros(n)
    P_el = np.zeros(n)

    for i in range(n):
        Q_need = Q_trans[i] + Q_inf + Q_dyn[i] + Q_int_W
        Qchg = 0; Qdis = 0
        if i>0 and m_pcm_kg>0:
            dti = dt[i-1]
            if T_set_C[i] >= T_melt_C:
                avail = min(Epcm/dti, P_pcm_discharge_max_W)
                Qdis = max(0, min(avail, Q_need))
                Epcm -= Qdis*dti
            elif T_set_C[i] <= T_melt_C - hysteresis_K:
                cap = min((Epcm_max-Epcm)/dti, P_pcm_charge_max_W)
                Qchg = max(0, cap)
                Epcm += Qchg*dti
            Epcm = np.clip(Epcm, 0, Epcm_max)
        SOC[i] = Epcm/Epcm_max if Epcm_max>0 else 0
        Qc = max(0, Q_need - Qdis + Qchg)
        if Q_cool_max_kW:
            Q_max = 1000*Q_cool_max_kW
            Qc = min(Qc, Q_max)
        Q_cool[i] = Qc
        P_el[i] = Qc/(COP*1000)

    return {"P_el_kW":P_el, "SOC":SOC}

# ---------------------------------------------------------------
# PV-AWARE ECONOMIC COST
# ---------------------------------------------------------------
def economic_cost_with_pv(P_el, PV, price, dt):
    if not USE_PV:
        return float(np.sum(P_el[:-1]*price[:-1]*(dt/3600)))
    P_imp = np.clip(P_el[:-1] - PV[:-1], 0, None)
    return float(np.sum(P_imp * price[:-1] * (dt/3600)))

# ---------------------------------------------------------------
# HEURISTIC SETPOINT (PV-AWARE)
# ---------------------------------------------------------------
def generate_Tset_heuristic(price, PV, Tmin=-25, Tmax=-16, Tcold=-23, Twarm=-18.5, max_dT=0.5):
    if USE_PV:
        price_eff = np.clip(price - 0.05*PV, 0, None)
    else:
        price_eff = price
    med = np.nanmedian(price_eff)
    Traw = np.where(price_eff<=med, Tcold, Twarm)
    Traw = np.clip(Traw, Tmin, Tmax)
    T = Traw.copy()
    for i in range(1,len(T)):
        d = T[i]-T[i-1]
        if abs(d)>max_dT: T[i]=T[i-1]+np.sign(d)*max_dT
    return T

# ---------------------------------------------------------------
# ROLLING-HORIZON OPTIMIZER (PV-AWARE)
# ---------------------------------------------------------------
def rolling_horizon_optimize_Tset(t_s, T_out, price, PV, horizon=6, Tmin=-25, Tmax=-16, grid_step=0.5,
                                  UA=45.5, V=368.18, q_inf=6.0, C_eff=30e6, COP=1.4, m_pcm=300,
                                  latent=250000, Tm=-21.5, Pchg=2000, Pdis=2000,
                                  baseline_T=None, initial_soc=1.0):
    if baseline_T is None:
        baseline_T = generate_Tset_heuristic(price, PV)
    T_opt = baseline_T.copy()
    dt = np.diff(t_s)
    grid = np.arange(Tmin, Tmax+1e-9, grid_step)
    soc = initial_soc

    for k in range(len(t_s)-1):
        h_end = min(len(t_s), k+horizon)
        best_cost = 1e18
        best_Tk = T_opt[k]
        for Tk in grid:
            Th = T_opt[k:h_end].copy()
            Th[0] = Tk
            res = power_from_setpoint_with_pcm(t_s[k:h_end], Th, T_out[k:h_end], UA, V, q_inf, C_eff, COP,
                                               m_pcm_kg=m_pcm, latent_J_per_kg=latent, T_melt_C=Tm,
                                               P_pcm_charge_max_W=Pchg, P_pcm_discharge_max_W=Pdis,
                                               initial_pcm_soc=soc)
            cost_h = economic_cost_with_pv(res['P_el_kW'], PV[k:h_end], price[k:h_end], dt[k:h_end-1] if h_end-1>k else np.array([0]))
            if cost_h<best_cost:
                best_cost=cost_h; best_Tk=Tk; best_soc=res['SOC'][-1]
        T_opt[k]=best_Tk; soc=best_soc
    return T_opt

# ---------------------------------------------------------------
# PCM SWEEP WITH PV SUPPORT
# ---------------------------------------------------------------
def sweep_pcm_configs(t_s, T_set, T_out, price, PV,
                      masses=(0,50,100,150,200,300,400,500,600,800,1000,1200)):
    dt=np.diff(t_s)
    rows=[]; best=None; best_cost=1e18
    for m in masses:
        sim = power_from_setpoint_with_pcm(t_s, T_set, T_out, m_pcm_kg=m)
        P_el=sim['P_el_kW']
        cost=economic_cost_with_pv(P_el, PV, price, dt)
        peak=float(np.max(P_el))
        imp=np.sum(np.clip(P_el[:-1]-PV[:-1],0,None)*(dt/3600))
        self_used=np.sum(np.minimum(P_el[:-1],PV[:-1])*(dt/3600))
        total_pv=np.sum(PV[:-1]*(dt/3600))
        row={"mass":m,"cost":cost,"peak":peak,"import_kwh":imp,"pv_self_used":self_used,"pv_total":total_pv}
        rows.append(row)
        if cost<best_cost: best_cost=cost; best=(row,sim)
    return best, rows

# ---------------------------------------------------------------
# PLOTS
# ---------------------------------------------------------------
def plot_cost_peak(rows):
    rows=sorted(rows,key=lambda r:r['mass'])
    m=[r['mass'] for r in rows]; c=[r['cost'] for r in rows]; p=[r['peak'] for r in rows]
    plt.figure(); plt.plot(m,c,'-o'); plt.title('Cost vs PCM mass'); plt.xlabel('PCM Mass [kg]'); plt.ylabel('Cost [EUR]'); plt.grid(True, alpha=0.3); plt.savefig('cost_vs_mass.png'); plt.close()
    plt.figure(); plt.plot(m,p,'-o'); plt.title('Peak vs PCM mass'); plt.xlabel('PCM Mass [kg]'); plt.ylabel('Peak P_el [kW]'); plt.grid(True, alpha=0.3); plt.savefig('peak_vs_mass.png'); plt.close()

def plot_metrics_vs_mass(rows, system_name=None, save_path=None):
    rows=sorted(rows,key=lambda r:r['mass'])
    m=[r['mass'] for r in rows]
    c=[r['cost'] for r in rows]
    p=[r['peak'] for r in rows]
    imp=[r['import_kwh'] for r in rows]
    su=[r['pv_self_used'] for r in rows]
    pvt=[r.get('pv_total', float('nan')) for r in rows]
    sc=[(su[i]/pvt[i] if (i<len(pvt) and pvt[i] and pvt[i]>0) else float('nan')) for i in range(len(rows))]
    fig, axes = plt.subplots(2, 3, figsize=(14, 7))
    axes = axes.flatten()
    axes[0].plot(m, c, '-o'); axes[0].set_title((system_name+': ' if system_name else '')+'Cost vs Mass'); axes[0].set_xlabel('PCM Mass [kg]'); axes[0].set_ylabel('Cost [EUR]'); axes[0].grid(True, alpha=0.3)
    axes[1].plot(m, p, '-o'); axes[1].set_title((system_name+': ' if system_name else '')+'Peak vs Mass'); axes[1].set_xlabel('PCM Mass [kg]'); axes[1].set_ylabel('Peak P_el [kW]'); axes[1].grid(True, alpha=0.3)
    axes[2].plot(m, imp, '-o'); axes[2].set_title((system_name+': ' if system_name else '')+'Grid Import vs Mass'); axes[2].set_xlabel('PCM Mass [kg]'); axes[2].set_ylabel('Import [kWh]'); axes[2].grid(True, alpha=0.3)
    axes[3].plot(m, su, '-o'); axes[3].set_title((system_name+': ' if system_name else '')+'PV Self-Used vs Mass'); axes[3].set_xlabel('PCM Mass [kg]'); axes[3].set_ylabel('PV Self-Used [kWh]'); axes[3].grid(True, alpha=0.3)
    axes[4].plot(m, sc, '-o'); axes[4].set_title((system_name+': ' if system_name else '')+'Self-Consumption Ratio vs Mass'); axes[4].set_xlabel('PCM Mass [kg]'); axes[4].set_ylabel('Self-Consumption Ratio [-]'); axes[4].grid(True, alpha=0.3)
    axes[5].plot(m, pvt, '-o'); axes[5].set_title((system_name+': ' if system_name else '')+'PV Total vs Mass'); axes[5].set_xlabel('PCM Mass [kg]'); axes[5].set_ylabel('PV Total [kWh]'); axes[5].grid(True, alpha=0.3)
    fig.suptitle('PCM Sweep (PV-aware)'+(' — '+system_name if system_name else ''))
    plt.tight_layout()
    if save_path: plt.savefig(save_path)
    plt.show()

# ---------------------------------------------------------------
# MAIN DEMO
# ---------------------------------------------------------------
if __name__=='__main__':
    hours=np.arange(0,24,1/6)
    t_s=(hours*3600)
    T_out=15+5*np.sin(2*np.pi*hours/24)
    price=0.15+0.10*(np.sin(2*np.pi*(hours-8)/24)>0)

    # Dummy PV input (replace with real time series)
    PV = 20*np.maximum(0,np.sin(2*np.pi*(hours-6)/24))  # 20 kW midday

    T_heur=generate_Tset_heuristic(price,PV)
    T_opt=rolling_horizon_optimize_Tset(t_s,T_out,price,PV,baseline_T=T_heur)

    USE_OPT=False
    T_set = T_opt if USE_OPT else T_heur

    best, rows=sweep_pcm_configs(t_s,T_set,T_out,price,PV)
    plot_cost_peak(rows)
    print(best[0])
