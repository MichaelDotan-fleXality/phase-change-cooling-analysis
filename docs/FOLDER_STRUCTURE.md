# Project Folder Structure

This document describes the organized folder structure for data and reports, separated by system (BÄKO and EcoCool).

## Directory Structure

```
phase_change_cooling_analysis/
├── data/
│   ├── bako/              # BÄKO system input data (reserved)
│   │   └── README.md
│   └── ecocool/           # EcoCool system input data
│       ├── power_data_ecocool_2024.csv
│       ├── emission_factor_2024.csv
│       ├── spot_prices_2024.csv
│       ├── ecocool_2024.csv
│       ├── spot_prices_full_2024.csv
│       ├── cleaned_fetched_data_full_2024.csv
│       ├── test_ecocool.csv
│       └── README.md
│
├── reports/
│   ├── bako/              # BÄKO system analysis reports
│   │   ├── 48h_analysis_may_2024/
│   │   ├── 48h_analysis_may_2024_smoothed/
│   │   ├── 8d_analysis_may_2024/
│   │   ├── 8d_analysis_may_2024_smoothed/
│   │   ├── full_year_2024_analysis/
│   │   └── full_year_2024_analysis_smoothed/
│   │
│   └── ecocool/           # EcoCool system analysis reports
│       ├── cost_optimized_2024/
│       └── emission_optimized_2024/
│
├── analysis/               # Analysis modules
├── utils/                  # Utility modules
├── docs/                   # Documentation
└── run_*.py               # Analysis scripts
```

## Data Directories

### `data/bako/`
- **Purpose**: Reserved for BÄKO system input data files
- **Current status**: Directory created, ready for BÄKO-specific data files
- **Note**: Currently, BÄKO data is loaded from original locations in analysis scripts

### `data/ecocool/`
- **Purpose**: Contains all EcoCool system input data files
- **Files**:
  - `power_data_ecocool_2024.csv` - Power consumption data (kW)
  - `emission_factor_2024.csv` - CO₂ emission factors (g CO₂/kWh or kg CO₂/kWh)
  - `spot_prices_2024.csv` - Spot market energy prices (€/MWh)
  - `ecocool_2024.csv` - EcoCool measured data
  - Additional supporting files

## Report Directories

### `reports/bako/`
- **Purpose**: All BÄKO system analysis reports
- **Subdirectories**:
  - `48h_analysis_may_2024/` - 48-hour analysis (dynamic schedule)
  - `48h_analysis_may_2024_smoothed/` - 48-hour analysis (smoothed schedule)
  - `8d_analysis_may_2024/` - 8-day analysis (dynamic schedule)
  - `8d_analysis_may_2024_smoothed/` - 8-day analysis (smoothed schedule)
  - `full_year_2024_analysis/` - Full year analysis (dynamic schedule)
  - `full_year_2024_analysis_smoothed/` - Full year analysis (smoothed schedule)

### `reports/ecocool/`
- **Purpose**: All EcoCool system analysis reports
- **Subdirectories**:
  - `cost_optimized_2024/` - Cost-optimized analysis results
  - `emission_optimized_2024/` - Emission-optimized analysis results

## Script Updates

### BÄKO Analysis Scripts
All BÄKO analysis scripts have been updated to use the new report directory structure:
- `run_48h_may_2024_analysis.py` → `reports/bako/48h_analysis_may_2024/`
- `run_48h_may_2024_analysis_smoothed.py` → `reports/bako/48h_analysis_may_2024_smoothed/`
- `run_8d_may_2024_analysis.py` → `reports/bako/8d_analysis_may_2024/`
- `run_8d_may_2024_analysis_smoothed.py` → `reports/bako/8d_analysis_may_2024_smoothed/`
- `run_full_year_2024_analysis.py` → `reports/bako/full_year_2024_analysis/`
- `run_full_year_2024_analysis_smoothed.py` → `reports/bako/full_year_2024_analysis_smoothed/`

### EcoCool Analysis Script
- `run_ecocool_emission_analysis.py` → Uses `data/ecocool/` for input and `reports/ecocool/` for output

## Benefits

1. **Clear separation**: BÄKO and EcoCool systems are clearly separated
2. **Easy navigation**: All data and reports for each system are in dedicated folders
3. **Scalability**: Easy to add more systems in the future
4. **Organization**: Cleaner project structure

## Migration Notes

- **Existing reports**: Old reports in `reports/` root directory remain unchanged
- **New reports**: All new analyses will use the new folder structure
- **Data files**: EcoCool data has been copied to `data/ecocool/` from the original location

