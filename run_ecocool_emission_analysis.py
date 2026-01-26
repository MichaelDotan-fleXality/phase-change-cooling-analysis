"""
Run emission optimization analysis for EcoCool system.

This script analyzes the EcoCool cooling system with emission-based optimization,
comparing cost-optimized vs. emission-optimized control strategies.
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from analysis.phase_change_analysis_tool import run_phase_change_analysis
from utils.insulation_calculator import calculate_heat_transfer_coefficient

# =============================================================================
# DATA PATHS
# =============================================================================

# Project root directory
PROJECT_ROOT = Path(__file__).parent

# EcoCool data directory (within project)
ECOCOOL_DATA_DIR = PROJECT_ROOT / "data" / "ecocool"

# Input files
POWER_DATA_FILE = ECOCOOL_DATA_DIR / "power_data_ecocool_2024.csv"
EMISSION_FACTOR_FILE = ECOCOOL_DATA_DIR / "emission_factor_2024.csv"
SPOT_PRICE_FILE = ECOCOOL_DATA_DIR / "spot_prices_2024.csv"

# =============================================================================
# ECOCOOL SYSTEM PARAMETERS
# =============================================================================

# Temperature settings
DEFAULT_INDOOR_TEMP = -20.0  # °C (typical for deep freeze)
MIN_TEMP_ALLOWED = -25.0  # °C
MAX_TEMP_ALLOWED = -15.0  # °C

# System performance
COP = 2.5  # Coefficient of Performance (to be calibrated)
COOLING_RAMP_SLOPE = -1.0  # K/h (negative for cooling)
WARMING_RAMP_SLOPE = 2.0  # K/h (positive for warming)

# Power price (€/kW)
POWER_PRICE = 100.0  # €/kW per month (typical value)

# =============================================================================
# THERMAL PROPERTIES (to be calibrated)
# =============================================================================

# Wall properties (example values - should be calibrated)
WALL_AREA = 100.0  # m² (total wall area)
INSULATION_THICKNESS = 0.15  # m
INSULATION_TYPE = "polyurethane"  # Typical for cold storage

# Calculate U-value
U_VALUE = calculate_heat_transfer_coefficient(
    insulation_thickness_m=INSULATION_THICKNESS,
    insulation_type=INSULATION_TYPE
)

# Content properties
CONTENT_MASS = 5000.0  # kg (air + contents)
SPECIFIC_HEAT_CAPACITY = 1005.0  # J/(kg·K) (air)

# =============================================================================
# PCM PARAMETERS (if applicable)
# =============================================================================

# For EcoCool, we'll start without PCM (can be added later)
PCM_MASS = 0.0  # kg
LATENT_HEAT_CAPACITY = 200000.0  # J/kg (not used if PCM_MASS = 0)
PHASE_CHANGE_TEMP = -20.0  # °C (not used if PCM_MASS = 0)
LATENT_HEAT_FACTOR = 1.0  # No PCM benefit

# =============================================================================
# LOAD AND PREPARE DATA
# =============================================================================

def load_ecocool_data():
    """Load and prepare EcoCool data for analysis."""
    print("=" * 80)
    print("Loading EcoCool Data")
    print("=" * 80)
    
    # Load power data
    print(f"\n[INFO] Loading power data from: {POWER_DATA_FILE}")
    if not POWER_DATA_FILE.exists():
        raise FileNotFoundError(f"Power data file not found: {POWER_DATA_FILE}")
    
    df_power = pd.read_csv(POWER_DATA_FILE)
    print(f"   Loaded {len(df_power)} rows")
    print(f"   Columns: {df_power.columns.tolist()}")
    
    # Load emission factors
    print(f"\n[INFO] Loading emission factors from: {EMISSION_FACTOR_FILE}")
    if not EMISSION_FACTOR_FILE.exists():
        raise FileNotFoundError(f"Emission factor file not found: {EMISSION_FACTOR_FILE}")
    
    df_emission = pd.read_csv(EMISSION_FACTOR_FILE)
    print(f"   Loaded {len(df_emission)} rows")
    print(f"   Columns: {df_emission.columns.tolist()}")
    
    # Load spot prices (optional, for cost comparison)
    print(f"\n[INFO] Loading spot prices from: {SPOT_PRICE_FILE}")
    df_price = None
    if SPOT_PRICE_FILE.exists():
        df_price = pd.read_csv(SPOT_PRICE_FILE)
        print(f"   Loaded {len(df_price)} rows")
        print(f"   Columns: {df_price.columns.tolist()}")
    else:
        print("   [WARNING] Spot price file not found, cost optimization will be limited")
    
    # Merge data
    # Handle timestamp column for power data
    timestamp_col = None
    for col in ['interval', 'timestamp', 'Timestamp', 'time', 'Time', 'datetime', 'DateTime']:
        if col in df_power.columns:
            timestamp_col = col
            break
    
    if timestamp_col is None:
        # Create timestamp index if not present
        print("   [INFO] No timestamp column found, creating sequential timestamps")
        df_power.index = pd.date_range(
            start='2024-01-01 00:00:00',
            periods=len(df_power),
            freq='15min'
        )
        df_power.index.name = 'timestamp'
    else:
        df_power[timestamp_col] = pd.to_datetime(df_power[timestamp_col])
        df_power = df_power.set_index(timestamp_col)
    
    # Prepare emission factors separately (will join after resampling)
    emission_col = None
    df_emission_resampled = None
    
    # Find timestamp column in emission data
    emission_timestamp_col = None
    for col in ['dateTime', 'dateTime.1', 'timestamp', 'Timestamp', 'time', 'Time', 'datetime', 'DateTime']:
        if col in df_emission.columns:
            emission_timestamp_col = col
            break
    
    if emission_timestamp_col:
        df_emission[emission_timestamp_col] = pd.to_datetime(df_emission[emission_timestamp_col])
        df_emission = df_emission.set_index(emission_timestamp_col)
    
    # Find power column
    power_col = None
    for col in ['ElectricMeter_Kaelteanlage_power', 'processPowerEl', 'power', 'Power', 'consumption', 'Consumption']:
        if col in df_power.columns:
            power_col = col
            break
    
    if power_col is None:
        raise ValueError(f"Could not find power column in {POWER_DATA_FILE}. Available columns: {df_power.columns.tolist()}")
    
    # Find emission factor column
    for col in ['consumption_co2_intensity', 'emission_factor', 'emissionFactor', 'emission', 'Emission', 'co2', 'CO2']:
        if col in df_emission.columns:
            emission_col = col
            break
    
    if emission_col is None:
        raise ValueError(f"Could not find emission factor column in {EMISSION_FACTOR_FILE}. Available columns: {df_emission.columns.tolist()}")
    
    # Remove timezone if present from emission data
    if df_emission.index.tz is not None:
        df_emission.index = df_emission.index.tz_localize(None)
    
    # Resample emission factors to 15-minute intervals (will join after main df is resampled)
    df_emission_resampled = df_emission[[emission_col]].resample('15min').mean()
    
    # Merge dataframes (before resampling)
    df = df_power.copy()
    
    # Check if emission factors are in g CO₂/kWh or kg CO₂/kWh (before resampling)
    # Convert to g CO₂/kWh if needed (assume > 100 means it's in g, < 1 means it's in kg)
    if df_emission[emission_col].max() < 1.0:
        print(f"   [INFO] Converting emission factors from kg CO₂/kWh to g CO₂/kWh")
        df_emission[emission_col] = df_emission[emission_col] * 1000.0
    elif df_emission[emission_col].max() > 1000.0:
        print(f"   [INFO] Emission factors appear to be in g CO₂/kWh (max: {df_emission[emission_col].max():.1f} g/kWh)")
    
    # Prepare spot prices separately (will join after resampling)
    spot_price_col = None
    df_price_resampled = None
    if df_price is not None:
        # Find timestamp column in price data
        price_timestamp_col = None
        for col in ['timestamp', 'Timestamp', 'time', 'Time', 'datetime', 'DateTime', 'dateTime']:
            if col in df_price.columns:
                price_timestamp_col = col
                break
        
        if price_timestamp_col:
            df_price[price_timestamp_col] = pd.to_datetime(df_price[price_timestamp_col])
            df_price = df_price.set_index(price_timestamp_col)
        
        price_col = None
        for col in ['price', 'Price', 'spot_price', 'SpotPrice']:
            if col in df_price.columns:
                price_col = col
                break
        
        if price_col:
            # Convert to €/MWh if needed
            # Check if prices are very small (likely in €/kWh) or in ct/kWh
            max_price = df_price[price_col].max()
            if max_price < 1.0 and max_price > 0:
                # Likely in €/kWh, convert to €/MWh
                print(f"   [INFO] Converting prices from €/kWh to €/MWh (max: {max_price:.6f} €/kWh)")
                df_price[price_col] = df_price[price_col] * 1000.0
            elif max_price < 100.0 and max_price > 0:
                # Likely in ct/kWh, convert to €/MWh
                print(f"   [INFO] Converting prices from ct/kWh to €/MWh (max: {max_price:.2f} ct/kWh)")
                df_price[price_col] = df_price[price_col] * 10.0
            elif max_price <= 0:
                print(f"   [WARNING] Prices are non-positive (max: {max_price:.6f}), may cause issues")
            
            # Remove timezone if present
            if df_price.index.tz is not None:
                df_price.index = df_price.index.tz_localize(None)
            
            # Resample prices to 15-minute intervals (will join after main df is resampled)
            df_price_resampled = df_price[[price_col]].resample('15min').mean()
            spot_price_col = price_col
    
    # Rename power column to standard name
    df['Standortverbrauch'] = df[power_col]
    
    # Ensure index is DatetimeIndex and remove timezone if present
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    
    # Remove timezone information (Excel doesn't support timezone-aware datetimes)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    
    # Resample to 15-minute intervals if needed
    if df.index.freq is None or df.index.freq != pd.Timedelta('15min'):
        print(f"   [INFO] Resampling to 15-minute intervals")
        df = df.resample('15min').mean()
    
    # Join emission factors after resampling
    if df_emission_resampled is not None and emission_col:
        df = df.join(df_emission_resampled, how='left')
        # Forward fill and backward fill to handle missing values
        df[emission_col] = df[emission_col].ffill().bfill()
        if df[emission_col].isna().any():
            # If still missing, fill with mean
            mean_emission = df[emission_col].mean()
            if pd.notna(mean_emission):
                df[emission_col] = df[emission_col].fillna(mean_emission)
            else:
                print(f"   [WARNING] All emission factors are NaN, analysis may fail")
        
        # Rename emission column to standard name
        df['Emission Factor (g CO2/kWh)'] = df[emission_col]
    
    # Join spot prices after resampling
    if df_price_resampled is not None and spot_price_col:
        df = df.join(df_price_resampled, how='left')
        # Forward fill and backward fill to handle missing values
        df[spot_price_col] = df[spot_price_col].ffill().bfill()
        if df[spot_price_col].isna().any():
            # If still missing, fill with mean
            mean_price = df[spot_price_col].mean()
            if pd.notna(mean_price):
                df[spot_price_col] = df[spot_price_col].fillna(mean_price)
            else:
                print(f"   [WARNING] All prices are NaN, analysis may fail")
    
    print(f"\n[INFO] Final data shape: {df.shape}")
    print(f"   Time range: {df.index.min()} to {df.index.max()}")
    print(f"   Power column: Standortverbrauch (min: {df['Standortverbrauch'].min():.2f} kW, max: {df['Standortverbrauch'].max():.2f} kW)")
    print(f"   Emission column: Emission Factor (g CO2/kWh) (min: {df['Emission Factor (g CO2/kWh)'].min():.1f}, max: {df['Emission Factor (g CO2/kWh)'].max():.1f})")
    if spot_price_col:
        print(f"   Price column: {spot_price_col} (min: {df[spot_price_col].min():.2f} €/MWh, max: {df[spot_price_col].max():.2f} €/MWh)")
    
    return df, spot_price_col


# =============================================================================
# RUN ANALYSES
# =============================================================================

def run_cost_optimization(df, spot_price_col):
    """Run cost-optimized analysis."""
    print("\n" + "=" * 80)
    print("COST-OPTIMIZED ANALYSIS")
    print("=" * 80)
    
    report_dir = str(PROJECT_ROOT / "reports" / "ecocool" / "cost_optimized_2024")
    
    # Prepare wall and content properties
    mapping_of_walls_properties = {
        "walls": {
            "area": WALL_AREA,
            "heat_transfer_coef": U_VALUE,
        }
    }
    
    mapping_of_content_properties = {
        "air_and_contents": {
            "mass": CONTENT_MASS,
            "specific_heat_capacity": SPECIFIC_HEAT_CAPACITY,
        }
    }
    
    run_phase_change_analysis(
        data=df,
        evu_col="Standortverbrauch",
        cooling_power_col="Standortverbrauch",
        spotmarket_energy_price_in_euro_per_mwh_col=spot_price_col,
        const_energy_price_in_euro_per_mwh_col=None,
        power_price_in_euro_per_kw=POWER_PRICE,
        cop=COP,
        schedule_temp_type="price_like_schedule",
        dflt_indoor_temp=DEFAULT_INDOOR_TEMP,
        min_temp_allowed=MIN_TEMP_ALLOWED,
        max_temp_allowed=MAX_TEMP_ALLOWED,
        mapping_of_walls_properties=mapping_of_walls_properties,
        mapping_of_content_properties=mapping_of_content_properties,
        cooling_ramp_slope_in_k_per_h=COOLING_RAMP_SLOPE,
        warming_ramp_slope_in_k_per_h=WARMING_RAMP_SLOPE,
        report_directory=report_dir,
        latent_heat_capacity_in_j_per_kg=LATENT_HEAT_CAPACITY,
        pcm_mass_in_kg=PCM_MASS,
        phase_change_temp_in_c=PHASE_CHANGE_TEMP,
        latent_heat_factor=LATENT_HEAT_FACTOR,
        optimization_mode="cost",
        system_group_name="EcoCool",
        show_plots=False,
    )
    
    print(f"\n[INFO] Cost-optimized analysis complete. Results saved to: {report_dir}")
    return report_dir


def run_emission_optimization(df):
    """Run emission-optimized analysis."""
    print("\n" + "=" * 80)
    print("EMISSION-OPTIMIZED ANALYSIS")
    print("=" * 80)
    
    report_dir = str(PROJECT_ROOT / "reports" / "ecocool" / "emission_optimized_2024")
    
    # Prepare wall and content properties
    mapping_of_walls_properties = {
        "walls": {
            "area": WALL_AREA,
            "heat_transfer_coef": U_VALUE,
        }
    }
    
    mapping_of_content_properties = {
        "air_and_contents": {
            "mass": CONTENT_MASS,
            "specific_heat_capacity": SPECIFIC_HEAT_CAPACITY,
        }
    }
    
    run_phase_change_analysis(
        data=df,
        evu_col="Standortverbrauch",
        cooling_power_col="Standortverbrauch",
        spotmarket_energy_price_in_euro_per_mwh_col=None,  # Not used for emission optimization
        const_energy_price_in_euro_per_mwh_col=None,
        power_price_in_euro_per_kw=POWER_PRICE,
        cop=COP,
        schedule_temp_type="emission_like_schedule",
        dflt_indoor_temp=DEFAULT_INDOOR_TEMP,
        min_temp_allowed=MIN_TEMP_ALLOWED,
        max_temp_allowed=MAX_TEMP_ALLOWED,
        mapping_of_walls_properties=mapping_of_walls_properties,
        mapping_of_content_properties=mapping_of_content_properties,
        cooling_ramp_slope_in_k_per_h=COOLING_RAMP_SLOPE,
        warming_ramp_slope_in_k_per_h=WARMING_RAMP_SLOPE,
        report_directory=report_dir,
        latent_heat_capacity_in_j_per_kg=LATENT_HEAT_CAPACITY,
        pcm_mass_in_kg=PCM_MASS,
        phase_change_temp_in_c=PHASE_CHANGE_TEMP,
        latent_heat_factor=LATENT_HEAT_FACTOR,
        emission_factor_col="Emission Factor (g CO2/kWh)",
        optimization_mode="emission",
        system_group_name="EcoCool",
        show_plots=False,
    )
    
    print(f"\n[INFO] Emission-optimized analysis complete. Results saved to: {report_dir}")
    return report_dir


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("EcoCool Emission Optimization Analysis")
    print("=" * 80)
    print(f"Started at: {datetime.now()}")
    
    try:
        # Load data
        df, spot_price_col = load_ecocool_data()
        
        # Run cost-optimized analysis (if prices available)
        if spot_price_col:
            cost_report_dir = run_cost_optimization(df, spot_price_col)
        else:
            print("\n[WARNING] Skipping cost optimization (no price data)")
            cost_report_dir = None
        
        # Run emission-optimized analysis
        emission_report_dir = run_emission_optimization(df)
        
        print("\n" + "=" * 80)
        print("ANALYSIS COMPLETE")
        print("=" * 80)
        if cost_report_dir:
            print(f"Cost-optimized results: {cost_report_dir}")
        print(f"Emission-optimized results: {emission_report_dir}")
        print(f"\nCompleted at: {datetime.now()}")
        
    except Exception as e:
        print(f"\n[ERROR] Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

