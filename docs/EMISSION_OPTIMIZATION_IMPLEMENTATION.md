# Emission Optimization Implementation

This document describes the emission-based optimization features added to the phase-change cooling analysis tool.

## Overview

The tool now supports **two optimization modes**:
1. **Cost optimization** - Optimizes based on energy prices (existing)
2. **Emission optimization** - Optimizes based on CO₂ emission factors (new)

Both modes generate electrical load profiles as output, allowing comparison of cost-optimized vs. emission-optimized control strategies.

## New Components

### 1. Emission Schedule Creators

**File**: `analysis/emission_schedule_creators.py`

Two new schedule creators:

#### `create_emission_like_schedule()`
- Creates temperature schedule based on CO₂ emission factors
- **Low emissions** → Lower temperatures (more cooling when grid is clean)
- **High emissions** → Higher temperatures (less cooling when grid is dirty)
- Similar to `create_price_like_schedule()` but uses emission factors instead of prices

#### `create_smoothed_emission_schedule()`
- Creates smoothed emission-based schedule
- Uses rolling average of emission factors to reduce rapid temperature changes
- Similar to `create_smoothed_price_schedule()` but uses emission factors

### 2. Modified Analysis Tool

**File**: `analysis/phase_change_analysis_tool.py`

**New Parameters**:
- `emission_factor_col`: Column name for emission factors (g CO₂/kWh or kg CO₂/kWh)
- `optimization_mode`: "cost" or "emission" (default: "cost")
- `smoothing_window_hours`: Hours for smoothing window (optional)

**New Schedule Types**:
- `"emission_like_schedule"`: Direct emission-based optimization
- `"smoothed_emission_schedule"`: Smoothed emission-based optimization

**Modified Behavior**:
- `spotmarket_energy_price_in_euro_per_mwh_col` is now optional (not needed for emission optimization)
- Price-related parameters have default values for emission-only analysis

### 3. EcoCool Analysis Script

**File**: `run_ecocool_emission_analysis.py`

Complete script for running EcoCool analysis with both cost and emission optimization.

**Features**:
- Loads EcoCool data from separate directory
- Handles emission factors and spot prices
- Runs both cost-optimized and emission-optimized analyses
- Generates separate reports for comparison

## Usage

### For EcoCool System

```python
python run_ecocool_emission_analysis.py
```

This will:
1. Load EcoCool data from `C:\Users\MichaelDotan\ecocool-optimization-analysis\data`
2. Run cost-optimized analysis (if prices available)
3. Run emission-optimized analysis
4. Generate reports in `reports/ecocool_cost_optimized_2024/` and `reports/ecocool_emission_optimized_2024/`

### For Custom Analysis

```python
from analysis.phase_change_analysis_tool import run_phase_change_analysis

# Emission optimization
run_phase_change_analysis(
    data=df,
    evu_col="Standortverbrauch",
    cooling_power_col="Standortverbrauch",
    spotmarket_energy_price_in_euro_per_mwh_col=None,  # Not needed
    schedule_temp_type="emission_like_schedule",
    emission_factor_col="Emission Factor (g CO₂/kWh)",
    optimization_mode="emission",
    # ... other parameters
)
```

## Data Requirements

### For Emission Optimization

**Required**:
- Power consumption data (kW)
- Emission factors (g CO₂/kWh or kg CO₂/kWh)

**Optional**:
- Spot prices (for cost comparison)

### Data Format

**Emission Factors**:
- Column name: Any (specified in `emission_factor_col` parameter)
- Units: g CO₂/kWh or kg CO₂/kWh (auto-detected and converted)
- Format: CSV with timestamp column

**Example**:
```csv
timestamp,emission_factor
2024-01-01 00:00:00,350.5
2024-01-01 00:15:00,320.2
...
```

## System Separation

### BÄKO Systems (Pluskühlung, Tiefkühlung)
- **Data location**: Project data directory
- **Analysis scripts**: `run_48h_may_2024_analysis.py`, `run_full_year_2024_analysis.py`, etc.
- **Optimization**: Cost-based (price optimization)

### EcoCool System
- **Data location**: `C:\Users\MichaelDotan\ecocool-optimization-analysis\data`
- **Analysis script**: `run_ecocool_emission_analysis.py`
- **Optimization**: Both cost and emission-based

## Output

Both optimization modes generate:
1. **Temperature schedule** (°C) - Optimized temperature profile
2. **Electrical load profile** (kW) - `"Cooling Power After Optimization"` column in `results.xlsx`
3. **Cost/emission savings** - Comparison with baseline
4. **Validation reports** - Temperature validation errors

### Electrical Load Profile

The electrical load profile is generated in the same way for both modes:
- Temperature schedule → Cooling load → Electrical power
- Saved to `results.xlsx` as `"Cooling Power After Optimization"`

This is the **key output** requested: an electrical load profile that can be evaluated for cost and emission savings.

## Comparison: Cost vs. Emission Optimization

### Cost Optimization
- **Input**: Spot market prices (€/MWh)
- **Strategy**: Cool more when prices are low, warm when prices are high
- **Goal**: Minimize energy costs

### Emission Optimization
- **Input**: CO₂ emission factors (g CO₂/kWh)
- **Strategy**: Cool more when emissions are low, warm when emissions are high
- **Goal**: Minimize CO₂ emissions

### Example Scenario

**Time 10:00**:
- Price: 30 €/MWh (low)
- Emission: 500 g CO₂/kWh (high)

**Cost optimization**: Cool more (low price)
**Emission optimization**: Warm more (high emissions)

**Result**: Different schedules, different load profiles, different savings

## Calibration

For EcoCool parametrization (calibration), you can:

1. **Use existing calibration tools**:
   - Modify `calibrate_pluskuehlung.py` for EcoCool
   - Adjust parameters (COP, U-value, heat capacity) to match measured data

2. **Manual calibration**:
   - Run analysis with initial parameters
   - Compare simulated vs. measured temperatures
   - Adjust parameters in `run_ecocool_emission_analysis.py`
   - Re-run until validation errors are acceptable

3. **Automated calibration** (future):
   - Create `calibrate_ecocool.py` similar to existing calibration scripts
   - Use optimization to find best parameters

## Next Steps

1. **Run EcoCool analysis**: Execute `run_ecocool_emission_analysis.py`
2. **Calibrate parameters**: Adjust COP, U-value, etc. to match measured data
3. **Compare results**: Analyze cost vs. emission savings
4. **Generate reports**: Use results for decision-making

## Files Modified/Created

### New Files
- `analysis/emission_schedule_creators.py` - Emission-based schedule creators
- `run_ecocool_emission_analysis.py` - EcoCool analysis script
- `docs/EMISSION_OPTIMIZATION_IMPLEMENTATION.md` - This document

### Modified Files
- `analysis/phase_change_analysis_tool.py` - Added emission optimization support

## Notes

- **System separation**: BÄKO and EcoCool are analyzed separately with different data sources
- **Backward compatibility**: Existing BÄKO analysis scripts continue to work unchanged
- **Flexible input**: Supports both g CO₂/kWh and kg CO₂/kWh (auto-converted)
- **Same output format**: Both modes generate the same electrical load profile format

