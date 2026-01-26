# EcoCool System Documentation

## Overview

EcoCool is a separate cooling system analyzed with both **cost optimization** and **emission optimization** capabilities.

## System Configuration

### Temperature Settings

- **Default indoor temp**: -20.0°C (typical for deep freeze)
- **Min allowed**: -25.0°C
- **Max allowed**: -15.0°C

### System Performance

- **COP**: 2.5 (to be calibrated)
- **Cooling ramp**: -1.0 K/h
- **Warming ramp**: 2.0 K/h
- **Power price**: 100.0 €/kW per month

### Thermal Properties (To Be Calibrated)

**Wall Properties**:
- Wall area: 100.0 m² (example, should be measured)
- Insulation thickness: 0.15 m
- Insulation type: polyurethane
- U-value: Calculated from insulation properties

**Content Properties**:
- Content mass: 5,000 kg (air + contents)
- Specific heat capacity: 1,005 J/(kg·K) (air)

### PCM Parameters

Currently configured without PCM:
- PCM mass: 0.0 kg
- Latent heat factor: 1.0 (no PCM benefit)

**Note**: PCM can be added later if applicable.

## Optimization Modes

### 1. Cost Optimization

**Input**: Spot market energy prices (€/MWh)

**Strategy**:
- Low prices → Cool more (store energy)
- High prices → Warm up (use stored energy)

**Schedule Type**: `price_like_schedule`

### 2. Emission Optimization

**Input**: CO₂ emission factors (g CO₂/kWh or kg CO₂/kWh)

**Strategy**:
- Low emissions → Cool more (when grid is clean)
- High emissions → Warm up (when grid is dirty)

**Schedule Type**: `emission_like_schedule` or `smoothed_emission_schedule`

## Analysis Script

**File**: `run_ecocool_emission_analysis.py`

**Usage**:
```bash
python run_ecocool_emission_analysis.py
```

**What it does**:
1. Loads EcoCool data from `data/ecocool/`
2. Runs cost-optimized analysis (if prices available)
3. Runs emission-optimized analysis
4. Generates separate reports for comparison

## Input Data

**Location**: `data/ecocool/`

**Required Files**:
- `power_data_ecocool_2024.csv` - Power consumption (kW)
- `emission_factor_2024.csv` - CO₂ emission factors (g CO₂/kWh or kg CO₂/kWh)

**Optional Files**:
- `spot_prices_2024.csv` - Spot market prices (€/MWh) for cost comparison

**Data Format**:
- CSV files with timestamp column
- Emission factors auto-detected (g or kg CO₂/kWh)
- Prices auto-converted to €/MWh if needed

## Output

**Report Locations**:
- Cost-optimized: `reports/ecocool/cost_optimized_2024/`
- Emission-optimized: `reports/ecocool/emission_optimized_2024/`

**Generated Files**:
- `results.xlsx` - Results with electrical load profile
- `savings.xlsx` - Cost/emission savings
- HTML reports for visualization

**Key Output**: **Electrical Load Profile** (`"Cooling Power After Optimization"` column in `results.xlsx`)

## Calibration

**Status**: Parameters need to be calibrated

**Calibration Process**:
1. Run analysis with initial parameters
2. Compare simulated vs. measured temperatures (from `ecocool_2024.csv`)
3. Adjust parameters in `run_ecocool_emission_analysis.py`:
   - COP
   - U-value calibration factor
   - Heat capacity calibration factor
4. Re-run until validation errors are acceptable

**Target Validation Errors**:
- MAE < 2.0°C
- Max Error < 5.0°C
- Within Tolerance > 80%

## Parameter Adjustment

**For Negative Bias** (overestimating cooling):
- Decrease U-value: Better insulation
- Increase heat capacity: More thermal mass
- Increase COP: More efficient

**For Positive Bias** (underestimating cooling):
- Increase U-value: Worse insulation
- Decrease heat capacity: Less thermal mass
- Decrease COP: Less efficient

## Comparison: Cost vs. Emission

The tool generates both optimizations for comparison:

**Cost Optimization**:
- Minimizes energy costs
- Responds to price signals
- May use high-emission energy if cheap

**Emission Optimization**:
- Minimizes CO₂ emissions
- Responds to emission factors
- May use expensive energy if clean

**Result**: Different schedules, different load profiles, different savings

## See Also

- [Emission Optimization Implementation](EMISSION_OPTIMIZATION_IMPLEMENTATION.md)
- [Parameter Determination](PARAMETER_DETERMINATION.md)
- [Complete Workflow](COMPLETE_WORKFLOW_EXPLANATION.md)
- [Folder Structure](FOLDER_STRUCTURE.md)

