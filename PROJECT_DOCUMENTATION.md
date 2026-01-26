# Phase-Change Cooling System Analysis - Project Documentation

## Project Overview

This project provides tools for analyzing the potential of phase-change cooling systems, optimizing temperature schedules based on energy prices and PV availability, and calculating energy and cost savings.

### Key Features
- **Energy Consumption Analysis**: Calculate and compare energy consumption before and after optimization
- **Cost Optimization**: Optimize temperature schedules based on energy prices and PV surplus
- **Phase-Change Modeling**: Specialized models for phase-change cooling systems with enhanced PCM modeling
- **PV Integration**: Analyze self-consumption with photovoltaic systems
- **Multi-System Support**: Separate optimization for different cooling system types (Pluskühlung, Tiefkühlung)
- **Visualization**: Generate comprehensive plots and reports

## System Configuration

All system parameters are centralized in `config.py`. Key settings include:

### Cooling System Parameters
- **COP (Coefficient of Performance)**: 2.5 (dimensionless, kW/kW)
- **Power Price**: 100 €/kW
- **Ramp Rates**: Cooling -1.0 K/h, Warming 2.0 K/h

### System Specifications (`COOLING_SYSTEMS`)
Each cooling system is defined with:
- Room area (m²)
- Room height (m)
- Default temperature (°C)
- Temperature range (min/max)
- Insulation properties (thickness, type)
- Content mass (kg)

### PCM Parameters
**Pluskühlung** (Water/ice):
- Latent heat capacity: 334,000 J/kg
- PCM mass: 1,000 kg
- Phase change temperature: 0°C
- Latent heat factor: 1.1

**Tiefkühlung** (Salt solution):
- Latent heat capacity: 250,000 J/kg
- PCM mass: 1,000 kg
- Phase change temperature: -20°C
- Latent heat factor: 1.1

### Enhanced PCM Model Parameters
- **Phase Change Range**: 2.5°C (temperature range over which phase change occurs)
- **Proximity Factor**: 1.25 (factor for proximity effect)
- **Base Benefit Factor**: 0.15 (base benefit when near phase change temp)

### Validation Tolerance
- **Pluskühlung**: 2.0°C (relaxed for excellent accuracy)
- **Tiefkühlung**: 1.0°C (strict to drive improvements)

### Optimization Constraints
- **Max Temperature Deviation (Tiefkühlung)**: 2.0°C from default
- **U-Value Override**: 0.20 W/(m²·K) (optional, set to None to use calculated)

## Optimization Strategy

### Temperature Schedule Types

1. **Price-Based Schedule** (`price_like_schedule`)
   - Low prices → colder temps (more cooling)
   - High prices → warmer temps (less cooling)
   - Automatically uses constrained schedule for Tiefkühlung (max 2°C deviation)

2. **Cost-Aware Schedule** (`cost_aware_schedule`)
   - Considers both price timing and energy consumption costs
   - Prevents excessive cooling that increases total costs

3. **Constrained Price Schedule** (`constrained_price_schedule`)
   - Price-based with maximum deviation limit
   - Prevents optimization backfire

4. **Constant Schedule** (`constant at X`)
   - Constant temperature (e.g., "constant at -20")

5. **Altering Step Schedule** (`altering_step_schedule`)
   - Alternates between min/max based on price threshold

### PV Self-Consumption Optimization

When PV surplus is available:
- Shifts cooling to PV surplus periods
- Creates cooling ramps during surplus
- Maintains constant phase at minimum temperature
- Creates warming ramps after surplus ends

### System-Specific Strategies

**Pluskühlung**:
- Unconstrained price-based optimization
- Excellent performance (49.1% grid savings)

**Tiefkühlung**:
- Constrained price-based optimization (max 2°C deviation)
- Prevents excessive cooling that increases costs
- Improved performance (34.9% grid savings, recovered from -8.4%)

## Parameter Settings Guide

### How to Modify Parameters

All parameters are in `config.py`. Key sections:

1. **COP**: Adjust if validation shows systematic bias
   - Lower COP = more cooling power needed
   - Current: 2.5 (calibrated)

2. **U-Value**: Override calculated value if needed
   - Set `U_VALUE_OVERRIDE_W_PER_M2_K` to desired value
   - Set to `None` to use calculated from insulation properties
   - Current: 0.20 W/(m²·K)

3. **Heat Capacity**: Adjust calibration factor
   - `HEAT_CAPACITY_CALIBRATION_FACTOR`: 1.5 (50% increase)
   - Higher = more thermal mass = slower temperature changes

4. **PCM Parameters**: System-specific
   - Modify in `COOLING_SYSTEMS` or use system-specific constants
   - Enhanced PCM model parameters in config

5. **Optimization Constraints**: System-specific
   - `MAX_TEMP_DEVIATION_FROM_DEFAULT_TIEFKUEHLUNG = 2.0`
   - Limits how far Tiefkühlung can deviate from default

### Calibration Process

If validation errors are high:

1. **Check COP**: Adjust if systematic bias
2. **Check U-Value**: Verify insulation calculations
3. **Check Heat Capacity**: Adjust if transient errors
4. **Check PCM Parameters**: Verify PCM properties
5. **Check Optimization Strategy**: Consider constrained schedules

## Running Analysis

### 48-Hour Analysis
```bash
pixi run python run_48h_may_2024_analysis.py
```

### Full-Year Analysis
```bash
pixi run python run_full_year_2024_analysis.py
```

### Required Data Files
- Power usage data (Lastgang)
- CAMS solar radiation data
- Spot market prices (from API or CSV)

## Results Interpretation

### Validation Errors

**Short-term (days/weeks)**:
- Mean error < 2°C: Excellent
- Mean error 2-5°C: Good
- Mean error > 5°C: Needs calibration

**Long-term (months/years)**:
- High errors expected due to error accumulation
- Focus on economic results (savings) as primary metric
- Use periodic validation for accuracy assessment

### Economic Results

**Grid Savings**: Percentage reduction in grid costs
- Positive = savings achieved
- Negative = costs increased (needs optimization adjustment)

**Absolute Savings**: Total cost savings in €
- Primary metric for economic evaluation
- More reliable than percentage for long-term analysis

## Current Performance

### 48-Hour Analysis (May 1-2, 2024)
- **Pluskühlung**: 49.1% savings, 2.92€, Validation PASSED
- **Tiefkühlung**: 34.9% savings, 2.07€, Validation improved
- **Total**: ~5.00€ savings

### Full-Year 2024 Analysis
- **Pluskühlung**: 5.2% savings, 537.14€
- **Tiefkühlung**: 10.1% savings, 1,037.98€
- **Total**: 1,575.12€ annual savings

## File Structure

```
phase_change_cooling_analysis/
├── README.md                    # Project overview
├── PROJECT_DOCUMENTATION.md    # This file - comprehensive documentation
├── config.py                    # Central configuration file
├── analysis/                    # Core analysis modules
│   ├── phase_change_analysis_tool.py
│   ├── phase_change_models.py
│   ├── enhanced_pcm_model.py
│   ├── schedule_creators.py
│   ├── cost_aware_schedule_creator.py
│   ├── temperature_validation.py
│   ├── multi_system_optimizer.py
│   └── pv_self_consumption_optimizer.py
├── utils/                       # Utility modules
│   ├── data_processing.py
│   ├── plotting.py
│   ├── insulation_calculator.py
│   └── api_data_fetcher.py
├── run_48h_may_2024_analysis.py      # 48-hour analysis script
├── run_full_year_2024_analysis.py    # Full-year analysis script
└── reports/                     # Analysis results
```

## Key Improvements Implemented

1. **Enhanced PCM Model**: Continuous phase change with thermal buffering
2. **Cost-Aware Optimization**: Prevents excessive cooling that increases costs
3. **System-Specific Strategies**: Different optimization for each system type
4. **Constrained Schedules**: Limits temperature deviation to prevent backfire
5. **Parameter Tuning**: Optimized PCM parameters for best accuracy

## References

- Configuration: `config.py`
- Analysis Tool: `analysis/phase_change_analysis_tool.py`
- PCM Model: `analysis/enhanced_pcm_model.py`
- Optimization: `analysis/cost_aware_schedule_creator.py`
- **PCM Models Structure**: `docs/PCM_MODELS_STRUCTURE.md` - Detailed documentation of PCM model architecture and mathematics
- **Analysis Workflow**: `docs/ANALYSIS_WORKFLOW_FLOWCHART.md` - Complete workflow flowchart from input data to optimized results

