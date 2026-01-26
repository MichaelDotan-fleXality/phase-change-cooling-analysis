# BÄKO Potential Analysis: Step-by-Step Manual

This manual provides detailed instructions for running the BÄKO potential analysis manually, step by step, with function calls and expected outputs. This allows you to review and verify each step of the process.

## Prerequisites

- Python environment with all dependencies installed (via `pixi install`)
- Input data files:
  - Lastgang Excel file (power consumption)
  - CAMS solar radiation CSV file
  - Spot market prices (API or CSV)
- Configuration file (`config.py`) with system parameters

---

## Step 1: Load Power Consumption Data

### Function/Module
- **Location**: `run_48h_may_2024_analysis.py` (data loading section)
- **Function**: Direct pandas Excel reading

### Code
```python
import pandas as pd

# Define file path
lastgang_path = r"C:\Users\MichaelDotan\Desktop\PotenzialAnalyse\BÄKO\Lastgang_Strom_2024__BÄKO_Bremerhaven (1).xlsx"

# Read Excel file - use 'Zeitreihe' sheet
excel_file = pd.ExcelFile(lastgang_path)
df_lastgang = pd.read_excel(excel_file, sheet_name='Zeitreihe')

# Combine date and time columns
df_lastgang['Datum'] = pd.to_datetime(df_lastgang['Datum'])
df_lastgang['timestamp'] = df_lastgang['Datum'] + pd.to_timedelta(df_lastgang['Uhrzeit'])
df_lastgang = df_lastgang.set_index('timestamp')

# Filter for analysis period
start_date = pd.Timestamp("2024-05-01 00:00:00")
end_date = pd.Timestamp("2024-05-02 23:59:59")
df_lastgang = df_lastgang.loc[start_date:end_date]

# Resample to 15-minute intervals
df_lastgang = df_lastgang.resample('15min').mean()

# Rename power column
df_lastgang['Standortverbrauch'] = df_lastgang['Wert [kW]']
```

### Expected Output
- DataFrame with datetime index (15-minute intervals)
- Column: `Standortverbrauch` (gross consumption in kW)
- Time range: 2024-05-01 00:00:00 to 2024-05-02 23:45:00
- Shape: ~192 rows (48 hours × 4 intervals/hour)

### Verification
```python
print(f"Shape: {df_lastgang.shape}")
print(f"Time range: {df_lastgang.index.min()} to {df_lastgang.index.max()}")
print(f"Power range: {df_lastgang['Standortverbrauch'].min():.2f} to {df_lastgang['Standortverbrauch'].max():.2f} kW")
print(df_lastgang[['Standortverbrauch']].head())
```

---

## Step 2: Load Solar Radiation Data

### Function/Module
- **Location**: `utils/data_processing.py`
- **Function**: `read_cams_solar_radiation()`

### Code
```python
from utils.data_processing import read_cams_solar_radiation

# Define file path
cams_path = r"C:\Users\MichaelDotan\Desktop\PotenzialAnalyse\BÄKO\CAMS solar radiation time-series2024.csv"

# Load solar radiation data
df_solar = read_cams_solar_radiation(cams_path)

# Align with power data index
df_solar = df_solar.reindex(df_lastgang.index, method='nearest')

# Fill missing values
df_solar['GHI'] = df_solar['GHI'].fillna(method='ffill').fillna(method='bfill')
```

### Expected Output
- DataFrame with same index as power data
- Column: `GHI` (Global Horizontal Irradiance in W/m²)
- Values typically: 0-1000 W/m² (0 at night, up to 1000 during peak sun)

### Verification
```python
print(f"Solar data shape: {df_solar.shape}")
print(f"GHI range: {df_solar['GHI'].min():.1f} to {df_solar['GHI'].max():.1f} W/m²")
print(f"Missing values: {df_solar['GHI'].isna().sum()}")
print(df_solar[['GHI']].head())
```

---

## Step 3: Load Spot Market Prices

### Function/Module
- **Location**: `utils/data_processing.py` or `utils/api_data_fetcher.py`
- **Function**: `load_spot_market_prices()` or `fetch_spotmarket_prices()`

### Code (API method)
```python
from utils.api_data_fetcher import fetch_spotmarket_prices

# Fetch prices from API
df_prices = fetch_spotmarket_prices(
    start_date=start_date,
    end_date=end_date
)

# Resample to 15-minute intervals
df_prices = df_prices.resample('15min').mean()

# Align with power data
df_prices = df_prices.reindex(df_lastgang.index, method='nearest')
```

### Code (CSV method)
```python
from utils.data_processing import load_spot_market_prices

# Load from CSV
df_prices = load_spot_market_prices(spot_price_path)

# Align with power data
df_prices = df_prices.reindex(df_lastgang.index, method='nearest')
```

### Expected Output
- DataFrame with same index as power data
- Column: `Spot Market Price (€/MWh)` or `price`
- Values typically: 20-150 €/MWh

### Verification
```python
print(f"Price data shape: {df_prices.shape}")
print(f"Price range: {df_prices['Spot Market Price (€/MWh)'].min():.2f} to {df_prices['Spot Market Price (€/MWh)'].max():.2f} €/MWh")
print(df_prices.head())
```

---

## Step 4: Merge All Input Data

### Function/Module
- **Location**: `run_48h_may_2024_analysis.py`
- **Function**: DataFrame merging

### Code
```python
# Merge all data
df = df_lastgang.copy()
df = df.join(df_solar[['GHI']], how='left')
df = df.join(df_prices[['Spot Market Price (€/MWh)']], how='left')

# Ensure no missing values in critical columns
df['GHI'] = df['GHI'].fillna(0)
df['Spot Market Price (€/MWh)'] = df['Spot Market Price (€/MWh)'].fillna(df['Spot Market Price (€/MWh)'].mean())
```

### Expected Output
- Combined DataFrame with columns:
  - `Standortverbrauch` (kW)
  - `GHI` (W/m²)
  - `Spot Market Price (€/MWh)`
- All aligned to same 15-minute index

### Verification
```python
print(f"Combined data shape: {df.shape}")
print(f"Columns: {df.columns.tolist()}")
print(f"Missing values per column:\n{df.isna().sum()}")
print(df.head())
```

---

## Step 5: Calculate PV Power

### Function/Module
- **Location**: `utils/data_processing.py`
- **Function**: `calculate_pv_power_from_irradiance_multiple_arrays()`

### Code
```python
from utils.data_processing import calculate_pv_power_from_irradiance_multiple_arrays
from config import PV_ARRAYS, PV_LOCATION_LAT, PV_LOCATION_LON

# Calculate PV power from solar irradiance
df['PV Power'] = calculate_pv_power_from_irradiance_multiple_arrays(
    ghi=df['GHI'],
    arrays=PV_ARRAYS,
    location_lat=PV_LOCATION_LAT,
    location_lon=PV_LOCATION_LON,
    index=df.index
)
```

### Expected Output
- New column: `PV Power` (kW)
- Values: 0 at night, up to peak capacity during peak sun
- Should match PV array configuration from `config.py`

### Verification
```python
print(f"PV Power range: {df['PV Power'].min():.2f} to {df['PV Power'].max():.2f} kW")
print(f"PV Power sum: {df['PV Power'].sum():.2f} kWh (total generation)")
print(df[['GHI', 'PV Power']].head(10))
```

---

## Step 6: Configure Cooling System Properties

### Function/Module
- **Location**: `utils/insulation_calculator.py` and `run_48h_may_2024_analysis.py`
- **Function**: `calculate_heat_transfer_coefficient()`

### Code
```python
from utils.insulation_calculator import calculate_heat_transfer_coefficient
from config import (
    COOLING_SYSTEMS,
    U_VALUE_CALIBRATION_FACTOR,
    U_VALUE_OVERRIDE_W_PER_M2_K,
)

# For each cooling system (Pluskühlung, Tiefkühlung)
mapping_of_walls_properties = {}
mapping_of_content_properties = {}

for system_name, system_config in COOLING_SYSTEMS.items():
    # Calculate U-value
    if U_VALUE_OVERRIDE_W_PER_M2_K is not None:
        u_value = U_VALUE_OVERRIDE_W_PER_M2_K
    else:
        u_value = calculate_heat_transfer_coefficient(
            insulation_thickness=system_config['insulation_thickness'],
            insulation_type=system_config['insulation_type']
        )
        u_value = u_value * U_VALUE_CALIBRATION_FACTOR
    
    # Calculate overall heat transfer coefficient (U × Area)
    overall_u = u_value * system_config['wall_area']
    
    # Store wall properties
    mapping_of_walls_properties[system_name] = {
        "area": system_config['wall_area'],
        "heat_transfer_coef": u_value
    }
    
    # Calculate heat capacity
    total_mass = system_config['content_mass'] + system_config['air_mass']
    heat_capacity = total_mass * system_config['specific_heat_capacity']
    
    # Store content properties
    mapping_of_content_properties[system_name] = {
        "mass": total_mass,
        "specific_heat_capacity": system_config['specific_heat_capacity']
    }
    
    print(f"{system_name}:")
    print(f"  U-value: {u_value:.4f} W/(m²·K)")
    print(f"  Overall U: {overall_u:.2f} W/K")
    print(f"  Heat capacity: {heat_capacity/1e6:.2f} MJ/K")
```

### Expected Output
- Dictionary `mapping_of_walls_properties` with area and heat transfer coefficient
- Dictionary `mapping_of_content_properties` with mass and specific heat capacity
- Temperature limits from `COOLING_SYSTEMS` config

### Verification
```python
print("Wall properties:", mapping_of_walls_properties)
print("Content properties:", mapping_of_content_properties)
```

---

## Step 7: Create Temperature Schedule

### Function/Module
- **Location**: `analysis/schedule_creators.py` or `analysis/cost_aware_schedule_creator.py`
- **Function**: `create_price_like_schedule()` or `create_constrained_price_schedule()`

### Code (Price-Like Schedule)
```python
from analysis.schedule_creators import create_price_like_schedule
from config import (
    SCHEDULE_TEMP_TYPE_PLUSKUEHLUNG,
    SCHEDULE_TEMP_TYPE_TIEFKUEHLUNG,
    PHASE_CHANGE_TEMP_PLUSKUEHLUNG_C,
    PHASE_CHANGE_TEMP_TIEFKUEHLUNG_C,
    PCM_MASS_PLUSKUEHLUNG_KG,
    PCM_MASS_TIEFKUEHLUNG_KG,
)

# For each system, create temperature schedule
for system_name, system_config in COOLING_SYSTEMS.items():
    # Set temperature constraints
    df[f'{system_name}_Min Temp Allowed'] = system_config['min_temp_allowed']
    df[f'{system_name}_Max Temp Allowed'] = system_config['max_temp_allowed']
    df[f'{system_name}_Default Indoor Temp'] = system_config['dflt_indoor_temp']
    
    # Get schedule type for this system
    if 'Pluskühlung' in system_name:
        schedule_type = SCHEDULE_TEMP_TYPE_PLUSKUEHLUNG
        phase_change_temp = PHASE_CHANGE_TEMP_PLUSKUEHLUNG_C if PCM_MASS_PLUSKUEHLUNG_KG > 0 else None
    elif 'Tiefkühlung' in system_name:
        schedule_type = SCHEDULE_TEMP_TYPE_TIEFKUEHLUNG
        phase_change_temp = PHASE_CHANGE_TEMP_TIEFKUEHLUNG_C if PCM_MASS_TIEFKUEHLUNG_KG > 0 else None
    else:
        schedule_type = "price_like_schedule"
        phase_change_temp = None
    
    # Create schedule
    if schedule_type == "price_like_schedule":
        df[f'{system_name}_Temperature Schedule'] = create_price_like_schedule(
            df=df,
            spotmarket_energy_price_col='Spot Market Price (€/MWh)',
            min_temp_allowed_col=f'{system_name}_Min Temp Allowed',
            max_temp_allowed_col=f'{system_name}_Max Temp Allowed',
            ramp_slope_in_k_per_h=abs(COOLING_RAMP_SLOPE_IN_K_PER_H),
            phase_change_temp=phase_change_temp,
        )
    elif schedule_type == "constrained_price_schedule":
        from analysis.cost_aware_schedule_creator import create_constrained_price_schedule
        df[f'{system_name}_Temperature Schedule'] = create_constrained_price_schedule(
            df=df,
            spotmarket_energy_price_col='Spot Market Price (€/MWh)',
            min_temp_allowed_col=f'{system_name}_Min Temp Allowed',
            max_temp_allowed_col=f'{system_name}_Max Temp Allowed',
            dflt_indoor_temp_col=f'{system_name}_Default Indoor Temp',
            ramp_slope_in_k_per_h=abs(COOLING_RAMP_SLOPE_IN_K_PER_H),
            max_deviation_from_default=2.0,  # From config
            phase_change_temp=phase_change_temp,
        )
```

### Expected Output
- New column for each system: `{system_name}_Temperature Schedule` (°C)
- Values within allowed temperature range
- Follows price pattern (low price → cold temp, high price → warm temp)

### Verification
```python
for system_name in COOLING_SYSTEMS.keys():
    col = f'{system_name}_Temperature Schedule'
    print(f"\n{system_name} Temperature Schedule:")
    print(f"  Range: {df[col].min():.2f} to {df[col].max():.2f} °C")
    print(f"  Mean: {df[col].mean():.2f} °C")
    print(f"  First 5 values:\n{df[col].head()}")
    
    # Plot to visualize
    import matplotlib.pyplot as plt
    plt.figure(figsize=(12, 4))
    plt.plot(df.index, df[col], label='Temperature Schedule')
    plt.plot(df.index, df['Spot Market Price (€/MWh)'] / df['Spot Market Price (€/MWh)'].max() * (df[col].max() - df[col].min()) + df[col].min(), 
             label='Normalized Price (scaled)', alpha=0.5)
    plt.xlabel('Time')
    plt.ylabel('Temperature (°C)')
    plt.title(f'{system_name} Temperature Schedule')
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()
```

---

## Step 8: PV Self-Consumption Optimization (Optional)

### Function/Module
- **Location**: `analysis/pv_self_consumption_optimizer.py`
- **Function**: `optimize_pv_self_consumption()`

### Code
```python
from analysis.pv_self_consumption_optimizer import optimize_pv_self_consumption
from utils.data_processing import determine_surplus_phases

# Determine surplus phases (when PV > consumption)
surplus_phases = determine_surplus_phases(
    df=df,
    pv_power_col='PV Power',
    site_consumption_col='Standortverbrauch'
)

# Convert surplus phases to daily format
from analysis.phase_change_analysis_tool import _convert_surplus_phases_to_daily_format
surplus_phases_by_day = _convert_surplus_phases_to_daily_format(df, surplus_phases)

# Optimize each system's schedule
for system_name, system_config in COOLING_SYSTEMS.items():
    schedule_col = f'{system_name}_Temperature Schedule'
    
    df[schedule_col] = optimize_pv_self_consumption(
        schedule_temp=df[schedule_col],
        expected_surplus_phases=surplus_phases_by_day,
        shortest_surplus_phase_allowed="1h",
        cooling_ramp_slope_in_k_per_h=COOLING_RAMP_SLOPE_IN_K_PER_H,
        warming_ramp_slope_in_k_per_h=WARMING_RAMP_SLOPE_IN_K_PER_H,
        min_temp_allowed=system_config['min_temp_allowed'],
        max_temp_allowed=system_config['max_temp_allowed'],
        phase_change_temp=phase_change_temp,
    )
```

### Expected Output
- Modified temperature schedules that cool more during PV surplus phases
- Schedules still respect ramp rate constraints

### Verification
```python
print(f"Number of surplus phases: {len(surplus_phases)}")
print(f"Total surplus time: {sum((end - start).total_seconds() / 3600 for start, end in surplus_phases):.1f} hours")

# Compare schedules before and after PV optimization
# (Save original schedule before optimization for comparison)
```

---

## Step 9: Calculate Cooling Power (Temperature → Electrical Load)

### Function/Module
- **Location**: `analysis/phase_change_models.py`
- **Function**: `calculate_phase_change_cooling_power()`

### Code
```python
from analysis.phase_change_models import calculate_phase_change_cooling_power
from config import (
    COP,
    LATENT_HEAT_CAPACITY_PLUSKUEHLUNG_J_PER_KG,
    LATENT_HEAT_CAPACITY_TIEFKUEHLUNG_J_PER_KG,
    PCM_MASS_PLUSKUEHLUNG_KG,
    PCM_MASS_TIEFKUEHLUNG_KG,
    PHASE_CHANGE_TEMP_PLUSKUEHLUNG_C,
    PHASE_CHANGE_TEMP_TIEFKUEHLUNG_C,
    LATENT_HEAT_FACTOR_PLUSKUEHLUNG,
    LATENT_HEAT_FACTOR_TIEFKUEHLUNG,
)

# For each system, calculate cooling power
for system_name, system_config in COOLING_SYSTEMS.items():
    # Get system-specific parameters
    if 'Pluskühlung' in system_name:
        latent_heat = LATENT_HEAT_CAPACITY_PLUSKUEHLUNG_J_PER_KG
        pcm_mass = PCM_MASS_PLUSKUEHLUNG_KG
        phase_change_temp = PHASE_CHANGE_TEMP_PLUSKUEHLUNG_C
        latent_heat_factor = LATENT_HEAT_FACTOR_PLUSKUEHLUNG
    elif 'Tiefkühlung' in system_name:
        latent_heat = LATENT_HEAT_CAPACITY_TIEFKUEHLUNG_J_PER_KG
        pcm_mass = PCM_MASS_TIEFKUEHLUNG_KG
        phase_change_temp = PHASE_CHANGE_TEMP_TIEFKUEHLUNG_C
        latent_heat_factor = LATENT_HEAT_FACTOR_TIEFKUEHLUNG
    else:
        latent_heat = 200000
        pcm_mass = 0
        phase_change_temp = 0
        latent_heat_factor = 1.0
    
    # Get wall and content properties
    wall_props = mapping_of_walls_properties[system_name]
    content_props = mapping_of_content_properties[system_name]
    
    # Calculate overall heat transfer coefficient
    overall_u = wall_props['area'] * wall_props['heat_transfer_coef']
    
    # Calculate overall heat capacity
    overall_heat_capacity = content_props['mass'] * content_props['specific_heat_capacity']
    
    # Calculate cooling power
    df[f'{system_name}_Cooling Power After Optimization'] = calculate_phase_change_cooling_power(
        df=df,
        cooling_power_col='Standortverbrauch',  # Baseline cooling
        schedule_temp_col=f'{system_name}_Temperature Schedule',
        dflt_indoor_temp_col=f'{system_name}_Default Indoor Temp',
        overall_heat_transfer_coef_in_w_per_k=overall_u,
        overall_heat_capacity_in_j_per_k=overall_heat_capacity,
        latent_heat_capacity_in_j_per_kg=latent_heat,
        pcm_mass_in_kg=pcm_mass,
        phase_change_temp_in_c=phase_change_temp,
        cop=COP,
        latent_heat_factor=latent_heat_factor,
    )
```

### Expected Output
- New column for each system: `{system_name}_Cooling Power After Optimization` (kW)
- **This is the electrical load profile!**
- Values represent electrical power consumption for cooling

### Verification
```python
for system_name in COOLING_SYSTEMS.keys():
    col = f'{system_name}_Cooling Power After Optimization'
    print(f"\n{system_name} Cooling Power:")
    print(f"  Range: {df[col].min():.2f} to {df[col].max():.2f} kW")
    print(f"  Mean: {df[col].mean():.2f} kW")
    print(f"  Total energy: {df[col].sum() * 0.25:.2f} kWh")  # 0.25 hours per 15-min interval
    
    # Compare with baseline
    baseline_col = 'Standortverbrauch'
    print(f"  Baseline mean: {df[baseline_col].mean():.2f} kW")
    print(f"  Difference: {df[col].mean() - df[baseline_col].mean():.2f} kW")
```

---

## Step 10: Calculate EVU and Grid Power After Optimization

### Function/Module
- **Location**: `analysis/phase_change_analysis_tool.py`
- **Function**: Direct calculation

### Code
```python
# For each system
for system_name in COOLING_SYSTEMS.keys():
    cooling_after_col = f'{system_name}_Cooling Power After Optimization'
    
    # Calculate EVU after optimization
    # EVU_after = EVU_before - cooling_before + cooling_after
    df[f'{system_name}_EVU After Optimization'] = (
        df['Standortverbrauch']  # EVU before (gross consumption)
        - df['Standortverbrauch']  # Subtract baseline cooling (assuming it's part of Standortverbrauch)
        + df[cooling_after_col]  # Add optimized cooling
    )
    
    # Calculate site consumption (same as EVU for gross consumption)
    df[f'{system_name}_Site Consumption After'] = df[f'{system_name}_EVU After Optimization']
    
    # Calculate EVU Meter (net grid exchange)
    if 'PV Power' in df.columns:
        df[f'{system_name}_EVU Meter After'] = (
            df[f'{system_name}_EVU After Optimization'] - df['PV Power']
        )
    else:
        df[f'{system_name}_EVU Meter After'] = df[f'{system_name}_EVU After Optimization']
    
    # Calculate grid power (only when drawing from grid)
    df[f'{system_name}_Grid Power After'] = df[f'{system_name}_EVU Meter After'].clip(lower=0)
```

### Expected Output
- New columns:
  - `{system_name}_EVU After Optimization` (gross consumption)
  - `{system_name}_Site Consumption After` (same as EVU)
  - `{system_name}_EVU Meter After` (net grid exchange)
  - `{system_name}_Grid Power After` (only positive values, when drawing from grid)

### Verification
```python
for system_name in COOLING_SYSTEMS.keys():
    print(f"\n{system_name} Power Calculations:")
    print(f"  EVU After: {df[f'{system_name}_EVU After Optimization'].mean():.2f} kW (mean)")
    print(f"  Grid Power After: {df[f'{system_name}_Grid Power After'].mean():.2f} kW (mean)")
    if 'PV Power' in df.columns:
        print(f"  PV Power: {df['PV Power'].mean():.2f} kW (mean)")
        print(f"  Self-consumption: {(df['PV Power'] - df[f'{system_name}_EVU Meter After'].clip(lower=0)).sum() * 0.25:.2f} kWh")
```

---

## Step 11: Calculate Costs and Savings

### Function/Module
- **Location**: `analysis/phase_change_analysis_tool.py`
- **Function**: `_calculate_savings()`

### Code
```python
from utils.data_processing import convert_power_to_energy
from config import POWER_PRICE_IN_EURO_PER_KW

# For each system
for system_name in COOLING_SYSTEMS.keys():
    # Calculate grid power before (baseline)
    if 'PV Power' in df.columns:
        df[f'{system_name}_EVU Meter Before'] = df['Standortverbrauch'] - df['PV Power']
        df[f'{system_name}_Grid Power Before'] = df[f'{system_name}_EVU Meter Before'].clip(lower=0)
    else:
        df[f'{system_name}_Grid Power Before'] = df['Standortverbrauch']
    
    grid_before_col = f'{system_name}_Grid Power Before'
    grid_after_col = f'{system_name}_Grid Power After'
    
    # Convert prices to ct/kWh
    df[f'{system_name}_Spot Market Price (ct/kWh)'] = df['Spot Market Price (€/MWh)'] * 0.1
    
    # Calculate hourly energy costs
    time_step_hours = 0.25  # 15 minutes
    df[f'{system_name}_Cost Before (€/h)'] = (
        df[grid_before_col] * time_step_hours 
        * df[f'{system_name}_Spot Market Price (ct/kWh)'] / 100
    )
    df[f'{system_name}_Cost After (€/h)'] = (
        df[grid_after_col] * time_step_hours 
        * df[f'{system_name}_Spot Market Price (ct/kWh)'] / 100
    )
    
    # Calculate cumulative energy consumption
    df[f'{system_name}_Energy Consumption Before (kWh)'] = convert_power_to_energy(df[grid_before_col])
    df[f'{system_name}_Energy Consumption After (kWh)'] = convert_power_to_energy(df[grid_after_col])
    
    # Calculate total costs
    grid_costs_before = df[f'{system_name}_Cost Before (€/h)'].sum()
    grid_costs_after = df[f'{system_name}_Cost After (€/h)'].sum()
    
    # Calculate power costs (based on max power)
    max_power_before = df[grid_before_col].max()
    max_power_after = df[grid_after_col].max()
    power_cost_before = max_power_before * POWER_PRICE_IN_EURO_PER_KW
    power_cost_after = max_power_after * POWER_PRICE_IN_EURO_PER_KW
    
    # Total costs
    total_cost_before = grid_costs_before + power_cost_before
    total_cost_after = grid_costs_after + power_cost_after
    
    # Calculate savings
    absolute_savings = total_cost_before - total_cost_after
    relative_savings = (absolute_savings / total_cost_before * 100) if total_cost_before > 0 else 0
    
    print(f"\n{system_name} Cost Analysis:")
    print(f"  Energy cost before: {grid_costs_before:.2f} €")
    print(f"  Energy cost after: {grid_costs_after:.2f} €")
    print(f"  Power cost before: {power_cost_before:.2f} €")
    print(f"  Power cost after: {power_cost_after:.2f} €")
    print(f"  Total cost before: {total_cost_before:.2f} €")
    print(f"  Total cost after: {total_cost_after:.2f} €")
    print(f"  Absolute savings: {absolute_savings:.2f} €")
    print(f"  Relative savings: {relative_savings:.1f} %")
```

### Expected Output
- Cost columns for each system
- Savings metrics (absolute and relative)

### Verification
```python
# Check cost calculations
print("\nCost Verification:")
print(f"Energy consumption before: {df[f'{system_name}_Energy Consumption Before (kWh)'].iloc[-1]:.2f} kWh")
print(f"Energy consumption after: {df[f'{system_name}_Energy Consumption After (kWh)'].iloc[-1]:.2f} kWh")
print(f"Energy savings: {df[f'{system_name}_Energy Consumption Before (kWh)'].iloc[-1] - df[f'{system_name}_Energy Consumption After (kWh)'].iloc[-1]:.2f} kWh")
```

---

## Step 12: Validate Temperature Schedule

### Function/Module
- **Location**: `analysis/temperature_validation.py`
- **Function**: `validate_temperature_schedule()` and `simulate_temperature_from_cooling_power()`

### Code
```python
from analysis.temperature_validation import validate_temperature_schedule, save_validation_report
from config import (
    VALIDATION_TOLERANCE_PLUSKUEHLUNG_C,
    VALIDATION_TOLERANCE_TIEFKUEHLUNG_C,
)

# For each system
for system_name, system_config in COOLING_SYSTEMS.items():
    # Get validation tolerance
    if 'Pluskühlung' in system_name:
        tolerance = VALIDATION_TOLERANCE_PLUSKUEHLUNG_C
    elif 'Tiefkühlung' in system_name:
        tolerance = VALIDATION_TOLERANCE_TIEFKUEHLUNG_C
    else:
        tolerance = 1.0
    
    # Get system properties
    wall_props = mapping_of_walls_properties[system_name]
    content_props = mapping_of_content_properties[system_name]
    overall_u = wall_props['area'] * wall_props['heat_transfer_coef']
    overall_heat_capacity = content_props['mass'] * content_props['specific_heat_capacity']
    
    # Validate temperature schedule
    validation_results = validate_temperature_schedule(
        df=df,
        target_temp_col=f'{system_name}_Temperature Schedule',
        cooling_power_col=f'{system_name}_Cooling Power After Optimization',
        initial_temp=system_config['dflt_indoor_temp'],
        overall_heat_transfer_coef_in_w_per_k=overall_u,
        overall_heat_capacity_in_j_per_k=overall_heat_capacity,
        cop=COP,
        latent_heat_factor=latent_heat_factor,
        baseline_cooling_power_col='Standortverbrauch',
        dflt_indoor_temp=system_config['dflt_indoor_temp'],
        tolerance=tolerance,
    )
    
    # Add simulated temperature to DataFrame
    df[f'{system_name}_Simulated Temperature'] = validation_results['simulated_temperature']
    df[f'{system_name}_Temperature Error'] = validation_results['errors']
    
    # Print validation summary
    print(f"\n{system_name} Validation Results:")
    print(f"  Mean Absolute Error: {validation_results['mean_abs_error']:.3f} °C")
    print(f"  Max Error: {validation_results['max_error']:.3f} °C")
    print(f"  RMSE: {validation_results['rmse']:.3f} °C")
    print(f"  Within Tolerance ({tolerance}°C): {validation_results['within_tolerance']:.1f}%")
    print(f"  Validation Status: {'PASSED' if validation_results['validation_passed'] else 'FAILED'}")
```

### Expected Output
- New columns:
  - `{system_name}_Simulated Temperature` (°C)
  - `{system_name}_Temperature Error` (°C)
- Validation metrics: MAE, Max Error, RMSE, Within Tolerance %

### Verification
```python
# Plot validation results
import matplotlib.pyplot as plt

for system_name in COOLING_SYSTEMS.keys():
    fig, axes = plt.subplots(2, 1, figsize=(12, 8))
    
    # Plot 1: Temperature comparison
    axes[0].plot(df.index, df[f'{system_name}_Temperature Schedule'], 
                 label='Target Schedule', linewidth=2)
    axes[0].plot(df.index, df[f'{system_name}_Simulated Temperature'], 
                 label='Simulated', linewidth=2, linestyle='--')
    axes[0].set_ylabel('Temperature (°C)')
    axes[0].set_title(f'{system_name} Temperature Validation')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    
    # Plot 2: Error
    axes[1].plot(df.index, df[f'{system_name}_Temperature Error'], 
                 label='Error', color='red')
    axes[1].axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    axes[1].set_ylabel('Error (°C)')
    axes[1].set_xlabel('Time')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()
```

---

## Step 13: Generate Reports

### Function/Module
- **Location**: `analysis/phase_change_analysis_tool.py` and `utils/plotting.py`
- **Function**: `_generate_plots()` and Excel export

### Code
```python
import os
from utils.plotting import PhaseChangePlotter

# Create report directory
report_directory = "reports/bako/manual_analysis"
os.makedirs(report_directory, exist_ok=True)

# For each system, generate reports
for system_name in COOLING_SYSTEMS.keys():
    system_report_dir = os.path.join(report_directory, system_name)
    os.makedirs(system_report_dir, exist_ok=True)
    
    # Prepare DataFrame for this system
    system_df = df[[
        'Standortverbrauch',
        'PV Power',
        'Spot Market Price (€/MWh)',
        f'{system_name}_Temperature Schedule',
        f'{system_name}_Cooling Power After Optimization',
        f'{system_name}_Grid Power Before',
        f'{system_name}_Grid Power After',
        f'{system_name}_Cost Before (€/h)',
        f'{system_name}_Cost After (€/h)',
        f'{system_name}_Energy Consumption Before (kWh)',
        f'{system_name}_Energy Consumption After (kWh)',
        f'{system_name}_Simulated Temperature',
        f'{system_name}_Temperature Error',
    ]].copy()
    
    # Rename columns for plotting (remove system name prefix)
    rename_dict = {
        f'{system_name}_Temperature Schedule': 'Temperature Schedule',
        f'{system_name}_Cooling Power After Optimization': 'Cooling Power After Optimization',
        f'{system_name}_Grid Power Before': 'Grid Power Before',
        f'{system_name}_Grid Power After': 'Grid Power After',
        f'{system_name}_Cost Before (€/h)': 'Cost Before (€/h)',
        f'{system_name}_Cost After (€/h)': 'Cost After (€/h)',
        f'{system_name}_Energy Consumption Before (kWh)': 'Energy Consumption Before (kWh)',
        f'{system_name}_Energy Consumption After (kWh)': 'Energy Consumption After (kWh)',
        f'{system_name}_Simulated Temperature': 'Simulated Temperature',
        f'{system_name}_Temperature Error': 'Temperature Error',
    }
    system_df = system_df.rename(columns=rename_dict)
    
    # Save Excel report
    excel_path = os.path.join(system_report_dir, 'results.xlsx')
    system_df.to_excel(excel_path, index=True)
    print(f"\n{system_name} Excel report saved: {excel_path}")
    
    # Generate plots
    plotter = PhaseChangePlotter(system_df)
    
    # Grid power comparison
    plotter.plot_comparison(
        before_col='Grid Power Before',
        after_col='Grid Power After',
        title=f'{system_name} Grid Power Comparison',
        save_path=os.path.join(system_report_dir, 'grid_power_comparison.html'),
    )
    
    # Cost comparison
    plotter.plot_comparison(
        before_col='Cost Before (€/h)',
        after_col='Cost After (€/h)',
        title=f'{system_name} Cost Comparison',
        save_path=os.path.join(system_report_dir, 'cost_comparison.html'),
    )
    
    # Energy consumption comparison
    plotter.plot_comparison(
        before_col='Energy Consumption Before (kWh)',
        after_col='Energy Consumption After (kWh)',
        title=f'{system_name} Energy Consumption Comparison',
        save_path=os.path.join(system_report_dir, 'energy_consumption_comparison.html'),
    )
    
    # Comprehensive analysis
    plotter.plot_power_curves(
        power_cols=['PV Power'] if 'PV Power' in system_df.columns else [],
        energy_price_col='Spot Market Price (€/MWh)',
        temp_col='Temperature Schedule',
        title=f'{system_name} Comprehensive Analysis',
        save_path=os.path.join(system_report_dir, 'comprehensive_analysis.html'),
    )
    
    print(f"{system_name} HTML plots saved to: {system_report_dir}")
```

### Expected Output
- Excel file: `results.xlsx` with all time series data
- HTML plots:
  - `grid_power_comparison.html`
  - `cost_comparison.html`
  - `energy_consumption_comparison.html`
  - `comprehensive_analysis.html`

### Verification
```python
# Check that files were created
import os
for system_name in COOLING_SYSTEMS.keys():
    system_report_dir = os.path.join(report_directory, system_name)
    files = os.listdir(system_report_dir)
    print(f"\n{system_name} Report Files:")
    for file in files:
        file_path = os.path.join(system_report_dir, file)
        size = os.path.getsize(file_path) / 1024  # KB
        print(f"  {file}: {size:.1f} KB")
```

---

## Complete Manual Execution Script

For convenience, here's a complete script that runs all steps sequentially:

```python
"""
Complete BÄKO Potential Analysis - Manual Step-by-Step Execution
Run each step individually to review and verify outputs
"""

# Import all required modules
import pandas as pd
import numpy as np
import os
from datetime import datetime

# Step 1-4: Load and merge data (see steps above)
# ... (data loading code)

# Step 5: Calculate PV power
# ... (PV calculation code)

# Step 6: Configure systems
# ... (system configuration code)

# Step 7: Create temperature schedules
# ... (schedule creation code)

# Step 8: PV optimization (optional)
# ... (PV optimization code)

# Step 9: Calculate cooling power
# ... (cooling power calculation code)

# Step 10: Calculate EVU and grid power
# ... (EVU calculation code)

# Step 11: Calculate costs
# ... (cost calculation code)

# Step 12: Validate
# ... (validation code)

# Step 13: Generate reports
# ... (report generation code)

print("\n" + "="*70)
print("MANUAL ANALYSIS COMPLETE")
print("="*70)
print(f"Results saved to: {report_directory}")
```

---

## Summary

This manual provides step-by-step instructions for running the BÄKO potential analysis manually. Each step includes:

1. **Function/Module location**: Where to find the code
2. **Code example**: Exact code to run
3. **Expected output**: What to expect from each step
4. **Verification**: How to check that the step worked correctly

By following these steps, you can:
- Review each intermediate result
- Understand how the analysis works
- Debug issues at specific steps
- Modify parameters and see immediate effects
- Validate the analysis process

For automated execution, use the existing run scripts (e.g., `run_48h_may_2024_analysis.py`), which execute all steps automatically.

