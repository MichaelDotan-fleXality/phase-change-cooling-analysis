# Phase-Change Cooling Analysis Tool - Documentation

## Overview

This tool analyzes the potential of phase-change cooling systems, optimizing temperature schedules based on energy prices (cost optimization) or CO₂ emission factors (emission optimization), and calculates energy and cost savings.

## Key Features

- **Cost Optimization**: Optimize temperature schedules based on spot market energy prices
- **Emission Optimization**: Optimize temperature schedules based on CO₂ emission factors
- **Phase-Change Modeling**: Enhanced PCM models with continuous phase change and thermal buffering
- **PV Integration**: Analyze self-consumption with photovoltaic systems
- **Multi-System Support**: Separate analysis for BÄKO and EcoCool systems
- **Electrical Load Profile**: Generates electrical load profiles as output (not just temperature curves)

## Quick Start

### For BÄKO Systems

```bash
# 48-hour analysis
python run_48h_may_2024_analysis.py

# Full year analysis
python run_full_year_2024_analysis.py
```

### For EcoCool System

```bash
# Cost and emission optimization
python run_ecocool_emission_analysis.py
```

## Documentation Structure

### Main Documentation
- **[Complete Workflow](COMPLETE_WORKFLOW_EXPLANATION.md)**: Detailed explanation of the entire analysis process from data loading to report generation

### System-Specific Guides
- **[BÄKO System Guide](BAKO_SYSTEM.md)**: BÄKO system configuration, parameters, and usage
- **[EcoCool System Guide](ECOCOOL_SYSTEM.md)**: EcoCool system configuration, optimization modes, and calibration

### Technical Documentation
- **[Parameter Determination](PARAMETER_DETERMINATION.md)**: How system parameters are calibrated and adjusted
- **[Emission Optimization](EMISSION_OPTIMIZATION_IMPLEMENTATION.md)**: Emission-based optimization implementation details
- **[Folder Structure](FOLDER_STRUCTURE.md)**: Project organization, data locations, and report structure
- **[Notebook Fixes and Corrections](NOTEBOOK_FIXES_AND_CORRECTIONS.md)**: Tracking document for fixes applied during notebook testing (for review and application to main scripts)

## Main Workflow

1. **Load Input Data**: Power consumption, solar radiation, energy prices/emission factors
2. **Process & Align Data**: Resample to 15-minute intervals, align timestamps
3. **Calculate PV Power**: Convert solar radiation to electrical power
4. **Configure Cooling Systems**: Load system specifications (U-value, heat capacity, temperature limits)
5. **Create Temperature Schedule**: Optimize based on prices/emissions
6. **PV Optimization** (optional): Adjust schedule for PV self-consumption
7. **Calculate Cooling Power**: Convert temperature schedule to electrical load profile
8. **Calculate Costs**: Energy and power costs before/after optimization
9. **Validate Temperature**: Simulate temperature from cooling power and compare with target
10. **Generate Reports**: HTML reports and Excel files with results

## Output

The tool generates:
- **Temperature Schedule** (°C): Optimized temperature profile
- **Electrical Load Profile** (kW): `"Cooling Power After Optimization"` in `results.xlsx`
- **Cost/Savings Analysis**: Energy and cost comparison
- **Validation Reports**: Temperature validation errors

## System Separation

- **BÄKO Systems**: Pluskühlung and Tiefkühlung (cost optimization)
  - Data: `data/bako/` (reserved)
  - Reports: `reports/bako/`
  
- **EcoCool System**: Cost and emission optimization
  - Data: `data/ecocool/`
  - Reports: `reports/ecocool/`

## Configuration

All parameters are in `config.py`:
- System specifications (room area, insulation, content mass)
- Temperature limits
- PCM parameters
- Calibration factors (U-value, heat capacity, COP)
- Optimization settings

## See Also

- [Complete Workflow Explanation](COMPLETE_WORKFLOW_EXPLANATION.md)
- [BÄKO System Guide](BAKO_SYSTEM.md)
- [EcoCool System Guide](ECOCOOL_SYSTEM.md)

