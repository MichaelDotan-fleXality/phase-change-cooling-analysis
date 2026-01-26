"""
Full-Year 2024 Potential Analysis
Runs a full potential analysis for the entire year 2024.
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime
from analysis.phase_change_analysis_tool import run_phase_change_analysis
from utils.data_processing import (
    read_cams_solar_radiation,
    calculate_pv_power_from_irradiance_multiple_arrays,
    load_spot_market_prices,
)
from utils.api_data_fetcher import fetch_spotmarket_prices
from utils.insulation_calculator import calculate_heat_transfer_coefficient
from analysis.multi_system_optimizer import optimize_separate_systems

# Import configuration
try:
    from config import (
        COOLING_RAMP_SLOPE_IN_K_PER_H,
        WARMING_RAMP_SLOPE_IN_K_PER_H,
        SCHEDULE_TEMP_TYPE,
        COP,
        POWER_PRICE_IN_EURO_PER_KW,
        LATENT_HEAT_CAPACITY_IN_J_PER_KG,
        PCM_MASS_IN_KG,
        PHASE_CHANGE_TEMP_IN_C,
        LATENT_HEAT_FACTOR,
        COOLING_POWER_FRACTION,
        PV_ARRAYS,
        PV_LOCATION_LAT,
        PV_LOCATION_LON,
        COOLING_SYSTEMS,
        U_VALUE_CALIBRATION_FACTOR,
        U_VALUE_OVERRIDE_W_PER_M2_K,
    )
except ImportError:
    # Fallback to defaults if config.py doesn't exist
    COOLING_RAMP_SLOPE_IN_K_PER_H = -1.0
    WARMING_RAMP_SLOPE_IN_K_PER_H = 2.0
    SCHEDULE_TEMP_TYPE = "price_like_schedule"
    COP = 3.5
    POWER_PRICE_IN_EURO_PER_KW = 100
    LATENT_HEAT_CAPACITY_IN_J_PER_KG = 334000
    PCM_MASS_IN_KG = 1000
    PHASE_CHANGE_TEMP_IN_C = 0.0
    LATENT_HEAT_FACTOR = 1.1
    COOLING_POWER_FRACTION = 0.4
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
    PV_LOCATION_LAT = 53.5488
    PV_LOCATION_LON = 8.5833

print("=" * 70)
print("Full-Year 2024 Potential Analysis - DYNAMIC SCHEDULE")
print("=" * 70)
print(f"Schedule Type: {SCHEDULE_TEMP_TYPE} (Dynamic)")

# =============================================================================
# CONFIGURATION
# =============================================================================
# Data file paths
lastgang_path = r"C:\Users\MichaelDotan\Desktop\PotenzialAnalyse\BÄKO\Lastgang_Strom_2024__BÄKO_Bremerhaven (1).xlsx"
# CAMS solar radiation data for 2024
cams_path = r"C:\Users\MichaelDotan\Desktop\PotenzialAnalyse\BÄKO\CAMS solar radiation time-series2024.csv"
spot_price_path = None  # Will use API

# Analysis period: Full year 2024
start_date = pd.Timestamp("2024-01-01 00:00:00")
end_date = pd.Timestamp("2024-12-31 23:59:59")

# PV location (from config)
pv_location_lat = PV_LOCATION_LAT
pv_location_lon = PV_LOCATION_LON

# Report directory
report_directory = "reports/bako/full_year_2024_analysis"

# =============================================================================
# 1. LOAD POWER USAGE DATA
# =============================================================================
print("\n1. Loading power usage data (Lastgang)...")
print(f"   File: {lastgang_path}")
print(f"   Period: {start_date.date()} to {end_date.date()}")

try:
    # Read Excel file - use 'Zeitreihe' sheet which contains the time series data
    excel_file = pd.ExcelFile(lastgang_path)
    if 'Zeitreihe' in excel_file.sheet_names:
        df_power = pd.read_excel(lastgang_path, sheet_name='Zeitreihe')
        print(f"   [INFO] Reading from 'Zeitreihe' sheet")
    else:
        df_power = pd.read_excel(lastgang_path, sheet_name=0)
        print(f"   [INFO] Reading from first sheet")
    
    print(f"   [INFO] Raw columns: {df_power.columns.tolist()}")
    print(f"   [INFO] Raw shape: {df_power.shape}")
    
    # Identify columns (expected: 'Datum', 'Uhrzeit', 'Wert [kW]')
    date_col = None
    time_col = None
    power_col = None
    
    for col in df_power.columns:
        col_lower = str(col).lower()
        if 'datum' in col_lower or 'date' in col_lower:
            date_col = col
        elif 'zeit' in col_lower or 'time' in col_lower or 'uhr' in col_lower:
            time_col = col
        elif 'wert' in col_lower or 'kw' in col_lower or 'leistung' in col_lower or 'power' in col_lower:
            power_col = col
    
    # Combine date and time columns
    if date_col and time_col:
        df_power['datetime'] = pd.to_datetime(
            df_power[date_col].astype(str) + ' ' + df_power[time_col].astype(str),
            format='%d.%m.%Y %H:%M',
            errors='coerce'
        )
    elif date_col:
        df_power['datetime'] = pd.to_datetime(df_power[date_col], errors='coerce')
    else:
        raise ValueError("Could not find date column in Excel file")
    
    df_power = df_power.dropna(subset=['datetime'])
    
    # Identify power column
    if not power_col:
        numeric_cols = df_power.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            power_col = numeric_cols[0]
        else:
            raise ValueError("Could not identify power column")
    
    # Rename power column to Standortverbrauch (gross consumption)
    # This represents the raw data from Lastgang (gross consumption)
    df_power.rename(columns={power_col: 'Standortverbrauch'}, inplace=True)
    df_power = df_power[['datetime', 'Standortverbrauch']]
    df_power['Standortverbrauch'] = pd.to_numeric(df_power['Standortverbrauch'], errors='coerce')
    df_power = df_power.dropna()
    
    # Remove duplicate datetimes (keep first)
    duplicates = df_power['datetime'].duplicated()
    if duplicates.sum() > 0:
        print(f"   [INFO] Removing {duplicates.sum()} duplicate datetime entries...")
        df_power = df_power[~duplicates]
    
    # Set datetime as index
    df_power.set_index('datetime', inplace=True)
    
    # Filter for 2024
    df_power = df_power[(df_power.index >= start_date) & (df_power.index <= end_date)]
    
    # Ensure 15-minute frequency
    if len(df_power) > 0:
        # Check current frequency
        if len(df_power) > 1:
            time_diff_min = (df_power.index[1] - df_power.index[0]).total_seconds() / 60
            if time_diff_min != 15:
                print(f"   [INFO] Resampling from {time_diff_min:.0f}-minute to 15-minute intervals...")
                df_power = df_power.resample('15min').mean()
                df_power = df_power.interpolate(method='linear', limit_direction='both')
            else:
                # Ensure continuous 15-minute index
                expected_index = pd.date_range(start=df_power.index.min(), end=df_power.index.max(), freq='15min')
                df_power = df_power.reindex(expected_index, method='nearest')
                df_power = df_power.interpolate(method='linear', limit_direction='both')
    
    print(f"   [OK] Loaded {len(df_power)} data points")
    print(f"   [OK] Date range: {df_power.index.min()} to {df_power.index.max()}")
    print(f"   [OK] Power range: {df_power['Standortverbrauch'].min():.2f} - {df_power['Standortverbrauch'].max():.2f} kW")
    
except Exception as e:
    print(f"   [ERROR] Failed to load power data: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# =============================================================================
# 2. LOAD CAMS SOLAR RADIATION DATA
# =============================================================================
print("\n2. Loading CAMS solar radiation data...")
print(f"   File: {cams_path}")

try:
    if os.path.exists(cams_path):
        solar_data = read_cams_solar_radiation(cams_path)
        
        # Filter for 2024
        solar_data = solar_data[(solar_data.index >= start_date) & (solar_data.index <= end_date)]
        
        # Remove any duplicate indices before alignment
        if solar_data.index.duplicated().any():
            print(f"   [INFO] Removing {solar_data.index.duplicated().sum()} duplicate indices from CAMS data...")
            solar_data = solar_data[~solar_data.index.duplicated(keep='first')]
        
        # Ensure both indices are timezone-naive or in same timezone for alignment
        if solar_data.index.tz is not None:
            solar_data.index = solar_data.index.tz_localize(None)
        if df_power.index.tz is not None:
            df_power.index = df_power.index.tz_localize(None)
        
        # Align with power data index
        solar_data = solar_data.reindex(df_power.index, method='nearest')
        
        # Fill any missing values
        if solar_data.isna().any().any():
            print(f"   [INFO] Filling missing values...")
            solar_data = solar_data.interpolate(method='linear', limit_direction='both')
            solar_data = solar_data.fillna(0)
        
        print(f"   [OK] Loaded {len(solar_data)} data points")
        if 'GHI' in solar_data.columns:
            print(f"   [OK] GHI range: {solar_data['GHI'].min():.2f} - {solar_data['GHI'].max():.2f} W/m²")
    else:
        print(f"   [WARNING] CAMS file not found: {cams_path}")
        print("   [INFO] Continuing without solar data...")
        solar_data = None
        
except Exception as e:
    print(f"   [ERROR] Failed to load CAMS data: {e}")
    import traceback
    traceback.print_exc()
    print("   [WARNING] Continuing without solar data...")
    solar_data = None

# =============================================================================
# 3. CALCULATE PV POWER FROM SOLAR RADIATION
# =============================================================================
print("\n3. Calculating PV power from solar radiation...")

# PV arrays configuration (from config)
pv_arrays = PV_ARRAYS

if solar_data is not None:
    try:
        df_power["PV Power"] = calculate_pv_power_from_irradiance_multiple_arrays(
            solar_data=solar_data,
            pv_arrays=pv_arrays,
            location_lat=pv_location_lat,
            location_lon=pv_location_lon,
            use_pvlib=True,
        )
        print(f"   [OK] PV power calculated")
        print(f"   [OK] PV power range: {df_power['PV Power'].min():.3f} - {df_power['PV Power'].max():.3f} kW")
        total_pv_energy = (df_power['PV Power'].sum() * 
                          (df_power.index[1] - df_power.index[0]).total_seconds() / 3600)
        print(f"   [OK] Total PV energy for 2024: {total_pv_energy:.2f} kWh")
    except Exception as e:
        print(f"   [ERROR] Failed to calculate PV power: {e}")
        import traceback
        traceback.print_exc()
        df_power["PV Power"] = 0.0
else:
    print("   [WARNING] No solar data, setting PV power to 0")
    df_power["PV Power"] = 0.0

# =============================================================================
# 4. LOAD SPOT MARKET PRICES
# =============================================================================
print("\n4. Loading spot market prices...")

try:
    # Try to fetch from API (same method as original project)
    start_time_str = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_time_str = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    print(f"   [INFO] Fetching prices from API for full year 2024...")
    print(f"   [INFO] This may take a few minutes...")
    
    spot_prices_df = fetch_spotmarket_prices(
        start_time=start_time_str,
        end_time=end_time_str,
        csv_path=spot_price_path,  # Fallback to CSV if API not available
    )
    
    # Rename column to match expected format
    if "powerPrice" in spot_prices_df.columns:
        spot_prices_df = spot_prices_df.rename(columns={"powerPrice": "Spot Market Price (€/MWh)"})
    elif "Spot Market Price (€/MWh)" not in spot_prices_df.columns and len(spot_prices_df.columns) > 0:
        spot_prices_df.columns = ["Spot Market Price (€/MWh)"]
    
    # Align with power data index (handle timezone if needed)
    if spot_prices_df.index.tz is not None:
        spot_prices_df.index = spot_prices_df.index.tz_localize(None)
    if df_power.index.tz is not None:
        df_power.index = df_power.index.tz_localize(None)
    
    # Resample spot prices to match power data frequency (15 minutes)
    spot_prices_df = spot_prices_df.reindex(df_power.index, method='nearest')
    df_power["Spot Market Price (€/MWh)"] = spot_prices_df["Spot Market Price (€/MWh)"]
    
    # Fill any missing values
    if df_power["Spot Market Price (€/MWh)"].isna().any():
        print(f"   [INFO] Filling {df_power['Spot Market Price (€/MWh)'].isna().sum()} missing price values...")
        df_power["Spot Market Price (€/MWh)"] = df_power["Spot Market Price (€/MWh)"].interpolate(method='linear', limit_direction='both')
    
    # Save spot prices to CSV for easy access
    os.makedirs(report_directory, exist_ok=True)
    spot_prices_csv_path = os.path.join(report_directory, "spot_prices_from_api.csv")
    # Reset index to make dateTime a regular column (not index) for better CSV compatibility
    spot_prices_df_save = spot_prices_df.reset_index()
    spot_prices_df_save = spot_prices_df_save.rename(columns={spot_prices_df_save.columns[0]: "dateTime"})
    # Ensure dateTime is formatted as string with full date-time format
    spot_prices_df_save['dateTime'] = pd.to_datetime(spot_prices_df_save['dateTime']).dt.strftime('%Y-%m-%d %H:%M:%S')
    # Save with quoting to prevent Excel from misinterpreting the dateTime column
    spot_prices_df_save.to_csv(spot_prices_csv_path, index=False, quoting=1)  # quoting=1 means QUOTE_ALL
    print(f"   [OK] Loaded spot prices from API or CSV")
    print(f"   [OK] Price range: {df_power['Spot Market Price (€/MWh)'].min():.2f} - {df_power['Spot Market Price (€/MWh)'].max():.2f} €/MWh")
    print(f"   [OK] Spot prices saved to: {spot_prices_csv_path}")
    
except Exception as e:
    print(f"   [WARNING] Failed to load spot prices from API/CSV: {e}")
    print("   [INFO] Using simulated spot prices")
    # Use simulated prices with seasonal variation
    hours = df_power.index.hour + df_power.index.minute / 60
    day_of_year = df_power.index.dayofyear
    seasonal = 50 + 20 * np.sin(2 * np.pi * (day_of_year - 80) / 365)
    daily = 30 * np.sin(2 * np.pi * (hours - 6) / 24)
    df_power["Spot Market Price (€/MWh)"] = seasonal + daily

# =============================================================================
# 5. COOLING SYSTEM CONFIGURATION
# =============================================================================
print("\n5. Configuring cooling systems...")
print("   [INFO] Using total power consumption directly (no cooling power estimation)")
print("   [INFO] Total power range: {:.2f} - {:.2f} kW".format(
    df_power['Standortverbrauch'].min(), df_power['Standortverbrauch'].max()
))

# Use cooling system specifications from config.py
cooling_systems = COOLING_SYSTEMS

# Aggregate properties
total_wall_area = sum(sys['room_area_sqm'] for sys in cooling_systems)
total_content_mass = sum(sys['room_content_mass_kg'] for sys in cooling_systems)

# Weighted average U-value
# Check if U-value override is set in config
if U_VALUE_OVERRIDE_W_PER_M2_K is not None:
    # Use fixed U-value override
    avg_heat_transfer_coef = U_VALUE_OVERRIDE_W_PER_M2_K
    print(f"   [INFO] Using U-value override: {avg_heat_transfer_coef:.4f} W/(m²·K)")
else:
    # Calculate from insulation properties
    total_heat_transfer_area_coef = 0.0
    for sys in cooling_systems:
        u_value = calculate_heat_transfer_coefficient(
            sys['insulation_thickness_m'], sys['insulation_type']
        )
        total_heat_transfer_area_coef += sys['room_area_sqm'] * u_value
    
    avg_heat_transfer_coef = total_heat_transfer_area_coef / total_wall_area if total_wall_area > 0 else 0.1
    print(f"   [INFO] Calculated average U-value: {avg_heat_transfer_coef:.4f} W/(m²·K)")

# Apply calibration factor
avg_heat_transfer_coef = avg_heat_transfer_coef * U_VALUE_CALIBRATION_FACTOR
if U_VALUE_CALIBRATION_FACTOR != 1.0:
    print(f"   [INFO] Applied U-value calibration factor: {U_VALUE_CALIBRATION_FACTOR:.2f}")
    print(f"   [INFO] Final U-value: {avg_heat_transfer_coef:.4f} W/(m²·K)")

# Temperature range
dflt_indoor_temp = np.mean([sys['default_temp_c'] for sys in cooling_systems])
min_temp_allowed = min(sys['min_temp_allowed_c'] for sys in cooling_systems)
max_temp_allowed = max(sys['max_temp_allowed_c'] for sys in cooling_systems)

# Add air mass
# Calculate volume properly: sum individual room volumes
# Volume = floor_area × height (assuming room_area_sqm represents floor area)
# If room_area_sqm represents wall area, use: volume ≈ room_area × height / 4 (for rectangular rooms)
total_volume = sum(
    sys['room_area_sqm'] * sys.get('room_height_m', 3.0) 
    for sys in cooling_systems
)
air_mass = total_volume * 1.3  # Air density ~1.3 kg/m³
total_content_mass += air_mass

mapping_of_walls_properties = {
    "walls": {"area": total_wall_area, "heat_transfer_coef": avg_heat_transfer_coef}
}

mapping_of_content_properties = {
    "air_and_contents": {"mass": total_content_mass, "specific_heat_capacity": 1005}
}

print(f"   [OK] Total wall area: {total_wall_area} m²")
print(f"   [OK] Average U-value: {avg_heat_transfer_coef:.3f} W/(m²·K)")
print(f"   [OK] Total content mass: {total_content_mass:.1f} kg")
print(f"   [OK] Temperature range: {min_temp_allowed} to {max_temp_allowed} °C")

# =============================================================================
# 7. RUN ANALYSIS (SEPARATE SYSTEM OPTIMIZATION)
# =============================================================================
print("\n7. Running potential analysis with separate system optimization...")
print("=" * 70)
print("[NOTE] Full-year analysis may take several minutes...")
print(f"Schedule Type: {SCHEDULE_TEMP_TYPE} (Dynamic)")
print("=" * 70)

df = df_power.copy()

# Run separate optimization for Pluskühlung and Tiefkühlung
# Using total power consumption directly instead of estimated cooling power
optimize_separate_systems(
    data=df,
    evu_col="Standortverbrauch",  # Gross consumption (raw data)
    cooling_power_col="Standortverbrauch",  # Use total power directly
    spotmarket_energy_price_in_euro_per_mwh_col="Spot Market Price (€/MWh)",
    const_energy_price_in_euro_per_mwh_col=None,
    power_price_in_euro_per_kw=POWER_PRICE_IN_EURO_PER_KW,
        cop=COP,
    schedule_temp_type=SCHEDULE_TEMP_TYPE,
    cooling_systems=cooling_systems,
    cooling_ramp_slope_in_k_per_h=COOLING_RAMP_SLOPE_IN_K_PER_H,
    warming_ramp_slope_in_k_per_h=WARMING_RAMP_SLOPE_IN_K_PER_H,
    report_directory=report_directory,
    latent_heat_capacity_in_j_per_kg=LATENT_HEAT_CAPACITY_IN_J_PER_KG,
    pcm_mass_in_kg=PCM_MASS_IN_KG,
    phase_change_temp_in_c=PHASE_CHANGE_TEMP_IN_C,
    latent_heat_factor=LATENT_HEAT_FACTOR,
    pv_power_col="PV Power",
    show_plots=False,
)

print("\n" + "=" * 70)
print("Full-Year 2024 Analysis Complete!")
print("=" * 70)
print(f"\nResults saved to: {report_directory}")
print("\nGenerated files:")
print("  - comprehensive_analysis.html")
print("  - cooling_power_comparison.html")
print("  - cost_comparison.html")
print("  - energy_consumption_comparison.html")
print("  - grid_power_comparison.html")
print("  - before_optimization.html")
print("  - before_optimization_with_price.html")
print("  - results.xlsx")
print("  - savings.xlsx")
print("  - spot_prices_from_api.csv")

