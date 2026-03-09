"""
Test configuration for Tiefkühlung 1 cooling model testing.

This file contains all configurable parameters specifically for testing
Tiefkühlung 1 with constant inputs.

The key is to include two types of load at every timestamp:

Steady‑state load to hold the target temperature (conduction + infiltration ± internal loads).
Dynamic (sensible) load to move the room (air + contents) from the previous temperature to the new setpoint (this depends on the effective thermal capacity CeffC_{\text{eff}}Ceff​).

Below is a minimal‑yet‑physical, production‑ready algorithm (no PCM) that returns a time series of cooling power and electrical power.


"""


# =============================================================================
# TEST PARAMETERS
# =============================================================================

# Constant outside temperature for testing (Fallback)
CONSTANT_OUTSIDE_TEMP_C = 15.0  # °C

# Power data path (for calculating average)
LASTGANG_PATH = r"C:\Users\MichaelDotan\Desktop\PotenzialAnalyse\BÄKO\Lastgang_Strom_2024__BÄKO_Bremerhaven (1).xlsx"

# Test period - Extended to 1 month for meaningful PCM analysis
TEST_START_DATE = "2024-01-01 00:00:00"
TEST_END_DATE = "2024-02-01 00:00:00"  # 1 month test period (January 2024)


# Location (Bremerhaven)
PV_LOCATION_LAT = 53.5488
PV_LOCATION_LON = 8.5833

# PV arrays configuration (5 arrays from BÄKO system)
## defined as : North= 0, East = 90, South = 180, West = 270
PV_ARRAYS = [
    {'power_kw': 99.45 / 2, 'orientation_deg': 90, 'tilt_deg': 10,
     'base_efficiency': 0.93, 'shading_loss': 0.012, 'inverter_efficiency': 0.96},
    {'power_kw': 99.45 / 2, 'orientation_deg': 270, 'tilt_deg': 10,
     'base_efficiency': 0.93, 'shading_loss': 0.012, 'inverter_efficiency': 0.96},
    {'power_kw': 76.95 / 2, 'orientation_deg': 90, 'tilt_deg': 10,
     'base_efficiency': 0.93, 'shading_loss': 0.012, 'inverter_efficiency': 0.96},
    {'power_kw': 76.95 / 2, 'orientation_deg': 270, 'tilt_deg': 10,
     'base_efficiency': 0.93, 'shading_loss': 0.012, 'inverter_efficiency': 0.96},
    {'power_kw': 22.5, 'orientation_deg': 180, 'tilt_deg': 90,
     'base_efficiency': 0.93, 'shading_loss': 0.015, 'inverter_efficiency': 0.96},
]

P_Share_Pluskühlung_1 = 0.0341
P_Share_Pluskühlung_2 = 0.2370
P_Share_Tiefkühlung_1 = 0.3105
P_Share_Tiefkühlung_2 = 0.4184
#P_Share_Tiefkühlung_2 = 0.4284

COOLING_SYSTEMS = [
    {
        'name': 'Pluskühlung 1',
        'room_area_sqm': 31.2,          # Room floor area in m²
        'room_height_m': 2.85,            # Room height in m
        'default_temp_c': 2.0,           # Default operating temperature in °C
        'min_temp_allowed_c': 0.0,       # Minimum allowed temperature in °C
        'max_temp_allowed_c': 4.0,       # Maximum allowed temperature in °C
        'insulation_thickness_m': 0.15,  # Insulation thickness in m
        'insulation_type': 'mineral_wool',  # Insulation material type
        'room_content_mass_kg': 6240,   # Mass of room contents (shelving, products, etc.) in kg
                                        # Estimated: ~200 kg/m² × 31.2 m² = 6,240 kg
                                        # Typical range: 150-400 kg/m² for cold storage rooms
    },
    {
        'name': 'Pluskühlung 2',
        'room_area_sqm': 232.8,
        'room_height_m': 2.85,
        'default_temp_c': 2.0,
        'min_temp_allowed_c': 0.0,
        'max_temp_allowed_c': 4.0,
        'insulation_thickness_m': 0.15,
        'insulation_type': 'mineral_wool',
        'room_content_mass_kg': 46560,  # Estimated: ~200 kg/m² × 232.8 m² = 46,560 kg
    },
    {
        'name': 'Tiefkühlung 1',
        'room_area_sqm': 135.36,        # Floor area (matches ceiling area)
        'room_height_m': 2.72,          # Room height (V = 135.36 × 2.72 = 368.18 m³)
        'default_temp_c': -20.0,
        'min_temp_allowed_c': -25.0,
        'max_temp_allowed_c': -16.0,
        'insulation_thickness_m': 0.14,  # Wall insulation (140 mm)
        'insulation_type': 'pur',        # Polyurethane insulation
        'room_content_mass_kg': 27072,  # Estimated: ~200 kg/m² × 135.36 m² = 27,072 kg
        # NEW PARAMETERS (from detailed analysis):
        # A_walls = 126.58 m², U_walls = 0.167 W/(m²·K)
        # A_ceiling = 135.36 m², U_ceiling = 0.138 W/(m²·K)  
        # A_door = 2.0 m², U_door = 0.5 W/(m²·K)
        # UA_total = 40.82 W/K
        # V = 368.18 m³, m_air ≈ 513.35 kg (at -20°C), C_air ≈ 0.51 MJ/K
        # Q_infil ≈ 2.21 kW (baseline infiltration)
        # Note: These will be used to override calculated values in Step 6
    },
    {
        'name': 'Tiefkühlung 2',
        'room_area_sqm': 84.6,
        'room_height_m': 5.49,
        'default_temp_c': -20.0,
        'min_temp_allowed_c': -25.0,
        'max_temp_allowed_c': -16.0,
        'insulation_thickness_m': 0.12,
        'insulation_type': 'pur',
        'room_content_mass_kg': 16920,  # Estimated: ~200 kg/m² × 84.6 m² = 16,920 kg
    },
]

# Available insulation types (see utils/insulation_calculator.py for full list):
# - 'mineral_wool': λ ≈ 0.040 W/(m·K)
# - 'pur': Polyurethane, λ ≈ 0.025 W/(m·K)
# - 'pir': Polyisocyanurate, λ ≈ 0.025 W/(m·K)
# - 'eps': Expanded Polystyrene, λ ≈ 0.035 W/(m·K)
# - 'xps': Extruded Polystyrene, λ ≈ 0.035 W/(m·K)


rooms_for_pcm_sweep = [
    # ----------------------------------------
    # PLUSKÜHLUNG 1  (31.2 m², 2.85 m; mineral wool 150 mm; 0..4 °C)
    # ----------------------------------------
    dict(
        name="Pluskühlung 1",
        V_m3=88.9,                     # 31.2 * 2.85
        UA_W_per_K=25.6,               # walls + ceiling (no insulated floor assumed)
        q_inf_W_per_m3=6.0,            # BÄKO default
        C_eff_J_per_K=24e6,            # ~6.24 t content at cp~3.6 + air (reasonable for plus cooling)
        COP=2.3,                       # chilled conservative
        pcm=dict(
            T_melt_C=+1.0,             # ~1–2 K below cold pre-charge
            P_pcm_charge_W=2000,
            P_pcm_discharge_W=2000,
            mass_sweep_kg=[100, 200, 300, 400, 500]
        )
    ),

    # ----------------------------------------
    # PLUSKÜHLUNG 2  (232.8 m², 2.85 m; mineral wool 150 mm; 0..4 °C)
    # ----------------------------------------
    dict(
        name="Pluskühlung 2",
        V_m3=663.5,                    # 232.8 * 2.85
        UA_W_per_K=109.8,              # walls + ceiling (no insulated floor assumed)
        q_inf_W_per_m3=6.0,
        C_eff_J_per_K=170e6,           # ~46.6 t content at cp~3.6 + air
        COP=2.4,
        pcm=dict(
            T_melt_C=+1.0,
            P_pcm_charge_W=4000,
            P_pcm_discharge_W=4000,
            mass_sweep_kg=[400, 600, 800, 1000, 1200, 1600]
        )
    ),

    # ----------------------------------------
    # TIEFKÜHLUNG 1  (135.36 m², 2.72 m; PUR; −25..−16 °C)  -- already done
    # ----------------------------------------
    dict(
        name="Tiefkühlung 1",
        V_m3=368.18,                   # given
        UA_W_per_K=40.82,              # given (walls+ceiling+floor from your calc)
        q_inf_W_per_m3=6.0,            # baseline ~2.21 kW at this volume
        C_eff_J_per_K=52e6,            # Corrected: ~27t frozen content at cp~1.9 + air ≈ 52 MJ/K
        COP=1.4,                       # CO₂ deep-freeze conservative
        pcm=dict(
            T_melt_C=-21.5,            # ~1–3 K below cold pre-charge around -22 °C
            P_pcm_charge_W=2000,
            P_pcm_discharge_W=2000,
            mass_sweep_kg=[400, 600, 800, 1000, 1200]
        )
    ),

    # ----------------------------------------
    # TIEFKÜHLUNG 2  (84.6 m², 5.49 m; PUR 120 mm; −25..−16 °C)
    # ----------------------------------------
    dict(
        name="Tiefkühlung 2",
        V_m3=464.5,                    # 84.6 * 5.49
        UA_W_per_K=63.1,               # walls + ceiling + floor; PUR 120 mm → U≈0.17
        q_inf_W_per_m3=6.0,
        C_eff_J_per_K=33e6,            # ~16.9 t frozen content at cp~1.9 + air
        COP=1.4,
        pcm=dict(
            T_melt_C=-21.5,
            P_pcm_charge_W=2000,
            P_pcm_discharge_W=2000,
            mass_sweep_kg=[400, 600, 800, 1000, 1200]
        )
    ),
]




# ---------------------------------------------------------------------
# 2) Parameter dictionary for each system
#     - PCM is disabled by default (m_pcm_kg=0.0). Turn on in simulate_system(...).
# ---------------------------------------------------------------------
SYSTEMS = {
    # ------------------------------------------------------------
    # PLUSKÜHLUNG 1 (0..4 °C)
    # ------------------------------------------------------------
    "Pluskühlung 1": {
        "UA_W_per_K": 25.6,
        "V_m3": 88.9,
        "q_inf_W_per_m3": 6.0,
        "C_eff_J_per_K": 24e6,
        "COP": 3.5, # 2.3 
        "Q_int_W": 0.0,
        "T_set_bounds_C": (0.0, 4.0),
        "pcm": {
            "m_pcm_kg": 0.0,                   # disabled by default; override in simulate_system
            "latent_J_per_kg": 250_000.0,
            # T_melt from two-node sweep optimisation (Jan 2024):
            # 1.5°C gives best cost saving (+45.8%) with 1500 kg.
            # charges when T_set < 1.2°C (cheap hours), discharges when T_set ≥ 1.5°C
            "T_melt_C": 1.5,
            "hysteresis_K": 0.3,
            "P_pcm_charge_max_W": 3_000.0,
            "P_pcm_discharge_max_W": 3_000.0,
            "initial_pcm_soc": 1.0,
        },
        "Q_cool_max_kW": None,
    },

    # ------------------------------------------------------------
    # PLUSKÜHLUNG 2 (0..4 °C)
    # ------------------------------------------------------------
    "Pluskühlung 2": {
        "UA_W_per_K": 109.8,
        "V_m3": 663.5,
        "q_inf_W_per_m3": 6.0,
        "C_eff_J_per_K": 170e6,
        "COP": 3.5, # 2.4
        "Q_int_W": 0.0,
        "T_set_bounds_C": (0.0, 4.0),
        "pcm": {
            "m_pcm_kg": 0.0,                   # disabled by default; override in simulate_system
            "latent_J_per_kg": 250_000.0,
            # T_melt from two-node sweep optimisation (Jan 2024):
            # 1.5°C gives best cost saving (+8.8%) with 1500 kg.
            "T_melt_C": 1.5,
            "hysteresis_K": 0.3,
            "P_pcm_charge_max_W": 8_000.0,
            "P_pcm_discharge_max_W": 8_000.0,
            "initial_pcm_soc": 1.0,
        },
        "Q_cool_max_kW": None,
    },

    # ------------------------------------------------------------
    # TIEFKÜHLUNG 1 (−25..−16 °C)
    # ------------------------------------------------------------
    "Tiefkühlung 1": {
        "UA_W_per_K": 45.5,
        "V_m3": 368.18,
        "q_inf_W_per_m3": 6.0,
        "C_eff_J_per_K": 52e6,
        "COP": 2.5, # 1.4
        "Q_int_W": 0.0,
        "T_set_bounds_C": (-25.0, -16.0),
        "pcm": {
            "m_pcm_kg": 0.0,                   # disabled by default; override in simulate_system
            "latent_J_per_kg": 250_000.0,
            # T_melt from two-node sweep optimisation (Jan 2024):
            # -21.0°C gives best cost saving (+12.4%) with 2000 kg.
            "T_melt_C": -21.0,
            "hysteresis_K": 0.3,
            "P_pcm_charge_max_W": 5_000.0,
            "P_pcm_discharge_max_W": 5_000.0,
            "initial_pcm_soc": 1.0,
        },
        "Q_cool_max_kW": None,
    },

    # ------------------------------------------------------------
    # TIEFKÜHLUNG 2 (−25..−16 °C)
    # ------------------------------------------------------------
    "Tiefkühlung 2": {
        "UA_W_per_K": 63.1,
        "V_m3": 464.5,
        "q_inf_W_per_m3": 6.0,
        "C_eff_J_per_K": 33e6,
        "COP": 2.5, # 1.4
        "Q_int_W": 0.0,
        "T_set_bounds_C": (-25.0, -16.0),
        "pcm": {
            "m_pcm_kg": 0.0,                   # disabled by default; override in simulate_system
            "latent_J_per_kg": 250_000.0,
            # T_melt from two-node sweep optimisation (Jan 2024):
            # -20.5°C gives best cost saving (+9.9%) with 2000 kg.
            "T_melt_C": -20.5,
            "hysteresis_K": 0.3,
            "P_pcm_charge_max_W": 5_000.0,
            "P_pcm_discharge_max_W": 5_000.0,
            "initial_pcm_soc": 1.0,
        },
        "Q_cool_max_kW": None,
    },
}


# =============================================================================
# 3) ELECTRICITY TARIFF STRUCTURE (BÄKO Bremerhaven)
# =============================================================================
# German industrial tariff components:
#   1. Energy charge (spot price) — already modelled via EPEX spot
#   2. Peak demand charge (Leistungspreis) — billed on highest 15-min peak/month
#   3. Grid fees (Netzentgelte) — split into energy + demand components
#   4. Taxes, levies, surcharges — mostly fixed per kWh
#
# Sources: typical Wesernetz / SWB Bremerhaven industrial tariffs 2024
TARIFF = {
    # Peak demand charge — billed per kW of monthly peak (15-min max)
    # Typical German industrial: €50–150/kW/year → €4.2–12.5/kW/month
    "peak_demand_charge_eur_per_kw_year": 90.0,    # €/kW/year

    # Grid fees — energy component (on top of spot price)
    "grid_fee_energy_eur_per_kwh": 0.04,            # ~4 ct/kWh

    # Grid fees — demand component (similar to peak demand)
    "grid_fee_demand_eur_per_kw_year": 40.0,         # €/kW/year

    # EEG surcharge + other levies (reduced for industrial)
    "levies_eur_per_kwh": 0.02,                      # ~2 ct/kWh

    # Total non-spot energy surcharge = grid_fee_energy + levies
    # (convenience sum; used when calculating total cost per kWh)
}

# Combined peak-related charges (demand + grid demand)
# PCM peak shaving benefit = peak_reduction_kW × total_demand_charge / 12
TARIFF["total_demand_charge_eur_per_kw_year"] = (
    TARIFF["peak_demand_charge_eur_per_kw_year"]
    + TARIFF["grid_fee_demand_eur_per_kw_year"]
)

# =============================================================================
# 4) SEASONAL ANALYSIS PERIODS
# =============================================================================
# Monthly outdoor temperature averages for Bremerhaven (DWD climate normals)
SEASONAL_PROFILES = {
    "winter": {
        "label": "January (Winter)",
        "start": "2024-01-01",
        "end": "2024-02-01",
        "T_out_avg_C": 3.0,
        "T_out_amplitude_C": 4.0,    # diurnal swing ±4°C
        "pv_capacity_factor": 0.04,   # ~4% CF in January
    },
    "summer": {
        "label": "July (Summer)",
        "start": "2024-07-01",
        "end": "2024-08-01",
        "T_out_avg_C": 18.0,
        "T_out_amplitude_C": 6.0,    # diurnal swing ±6°C
        "pv_capacity_factor": 0.14,   # ~14% CF in July
    },
    "shoulder": {
        "label": "April (Shoulder)",
        "start": "2024-04-01",
        "end": "2024-05-01",
        "T_out_avg_C": 9.0,
        "T_out_amplitude_C": 5.0,
        "pv_capacity_factor": 0.10,
    },
}
