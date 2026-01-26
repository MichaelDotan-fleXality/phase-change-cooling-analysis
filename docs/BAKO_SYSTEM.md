# BÄKO System Documentation

## Overview

BÄKO systems include two cooling system types:
- **Pluskühlung**: Operating at 0-4°C range (water/ice PCM)
- **Tiefkühlung**: Operating at -25°C to -16°C range (salt solution PCM)

## System Configuration

### Pluskühlung

**Temperature Range**:
- Default: 0-4°C
- Min allowed: -2°C
- Max allowed: 4°C

**PCM Parameters**:
- Phase change temperature: 0.0°C (water/ice)
- Latent heat capacity: 334,000 J/kg
- PCM mass: 1,000 kg
- Latent heat factor: 1.1 (10% enhancement)

**Optimization**:
- Schedule type: `price_like_schedule` (dynamic) or `smoothed_price_schedule` (less dynamic)
- Max temperature deviation: None (full range allowed)

### Tiefkühlung

**Temperature Range**:
- Default: -20°C
- Min allowed: -25°C
- Max allowed: -16°C

**PCM Parameters**:
- Phase change temperature: -20.0°C (salt solution)
- Latent heat capacity: 250,000 J/kg
- PCM mass: 1,000 kg
- Latent heat factor: 1.1 (10% enhancement)

**Optimization**:
- Schedule type: `constrained_price_schedule`
- Max temperature deviation: 2.0°C (limited to prevent excessive cooling)

## Calibrated Parameters

**From `config.py`** (calibrated for BÄKO systems):
```python
COP = 2.8  # Calibrated from initial 4.0
U_VALUE_CALIBRATION_FACTOR = 0.85  # 15% reduction (better insulation)
HEAT_CAPACITY_CALIBRATION_FACTOR = 1.8  # 80% increase (more thermal mass)
```

**Validation Tolerances**:
- Pluskühlung: 2.0°C (relaxed, excellent accuracy ~1.86°C mean error)
- Tiefkühlung: 1.0°C (strict, drives improvements)

## Analysis Scripts

### Available Scripts

1. **48-Hour Analysis**:
   - `run_48h_may_2024_analysis.py` - Dynamic schedule
   - `run_48h_may_2024_analysis_smoothed.py` - Smoothed schedule

2. **8-Day Analysis**:
   - `run_8d_may_2024_analysis.py` - Dynamic schedule
   - `run_8d_may_2024_analysis_smoothed.py` - Smoothed schedule

3. **Full Year Analysis**:
   - `run_full_year_2024_analysis.py` - Dynamic schedule
   - `run_full_year_2024_analysis_smoothed.py` - Smoothed schedule

### Usage

```bash
# Run 48-hour analysis with dynamic schedule
python run_48h_may_2024_analysis.py

# Run 48-hour analysis with smoothed schedule
python run_48h_may_2024_analysis_smoothed.py
```

## Input Data

**Required Files**:
- Power consumption data (Lastgang Excel file)
- Solar radiation data (CAMS CSV file)
- Spot market prices (API or CSV)

**Data Sources**:
- Power: `Lastgang_Strom_102025_BÄKO_Bremerhaven.csv`
- Solar: `CAMS solar radiation time-series2025.csv`
- Prices: Fetched from API or CSV file

## Output

**Report Location**: `reports/bako/[analysis_name]/`

**Generated Files**:
- `results_combined.xlsx` - Combined results for both systems
- `savings_combined.xlsx` - Cost and energy savings
- HTML reports for visualization
- System-specific subfolders (pluskühlung/, tiefkühlung/)

## Optimization Strategy

**Cost Optimization**:
- Low prices → Cool more (store energy)
- High prices → Warm up (use stored energy)
- PV surplus → Cool more (use free energy)

**Schedule Types**:
- **Dynamic** (`price_like_schedule`): Rapid response to price changes
- **Smoothed** (`smoothed_price_schedule`): Gradual response (4-hour smoothing window)

## System Properties

**Calculated from**:
- Room area and height
- Insulation properties (thickness, type)
- Content mass
- Applied calibration factors

**U-Value**: Calculated from insulation, then multiplied by `U_VALUE_CALIBRATION_FACTOR`

**Heat Capacity**: Calculated from mass × specific heat, then multiplied by `HEAT_CAPACITY_CALIBRATION_FACTOR`

## See Also

- [Complete Workflow](COMPLETE_WORKFLOW_EXPLANATION.md)
- [Parameter Determination](PARAMETER_DETERMINATION.md)
- [Folder Structure](FOLDER_STRUCTURE.md)

