# Phase-Change Cooling System Potential Analysis

This project provides tools for analyzing the potential of phase-change cooling systems, optimizing temperature schedules based on energy prices and PV availability, and calculating energy and cost savings.

## Features

- **Energy Consumption Analysis**: Calculate and compare energy consumption before and after optimization
- **Cost Optimization**: Optimize temperature schedules based on energy prices and PV surplus
- **Phase-Change Modeling**: Enhanced PCM models with continuous phase change and thermal buffering
- **PV Integration**: Analyze self-consumption with photovoltaic systems
- **Multi-System Support**: Separate optimization for different cooling system types
- **Visualization**: Generate comprehensive plots and reports

## Quick Start

### Installation

```bash
# Install pixi (if not already installed)
# Windows (PowerShell)
iwr https://pixi.sh/install.ps1 -useb | iex

# Install dependencies
pixi install
```

### Run Analysis

```bash
# 48-hour analysis
pixi run python run_48h_may_2024_analysis.py

# Full-year analysis
pixi run python run_full_year_2024_analysis.py
```

## Configuration

All system parameters are configured in `config.py`. Key settings:

- **COP**: 2.5 (Coefficient of Performance)
- **U-Value**: 0.20 W/(m²·K) (override, or calculated from insulation)
- **PCM Parameters**: System-specific (see `config.py`)
- **Optimization Constraints**: Max 2°C deviation for Tiefkühlung

## Documentation

- **`PROJECT_DOCUMENTATION.md`**: Comprehensive project documentation, optimization strategy, and parameter settings
- **`docs/PCM_MODELS_STRUCTURE.md`**: Detailed documentation of PCM (Phase-Change Material) models structure, mathematics, and implementation
- **`README.md`**: This file - quick start guide

## Current Performance

- **48-Hour**: Pluskühlung 49.1% savings, Tiefkühlung 34.9% savings
- **Full-Year**: 1,575€ total annual savings

## Project Structure

```
phase_change_cooling_analysis/
├── README.md
├── requirements.txt
├── analysis/
│   ├── phase_change_analysis_tool.py    # Main analysis tool
│   ├── phase_change_models.py          # Phase-change specific models
│   └── schedule_creators.py            # Temperature schedule generation
├── notebooks/
│   ├── potential_analysis.ipynb        # Main analysis notebook
│   ├── phase_change_modeling.ipynb     # Phase-change system modeling
│   └── optimization_example.ipynb       # Optimization examples
├── utils/
│   ├── data_processing.py             # Data processing utilities
│   └── plotting.py                     # Plotting utilities
└── examples/
    └── sample_data.csv                 # Example data file
```

## Installation

### Option 1: Using Pixi (Recommended)

1. Install pixi (if not already installed):
```bash
# Windows (PowerShell)
iwr https://pixi.sh/install.ps1 -useb | iex

# Or download from https://pixi.sh/
```

2. Install dependencies and activate environment:
```bash
pixi install
pixi shell
```

3. Run example:
```bash
pixi run run-example
```

4. Start Jupyter notebook:
```bash
pixi run notebook
```

### Option 2: Using pip (Traditional)

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install Jupyter (if using notebooks):
```bash
pip install jupyter
```

## Quick Start

### 1. Install Dependencies

**Using Pixi (Recommended):**
```bash
pixi install
pixi shell
```

**Or using pip:**
```bash
pip install -r requirements.txt
```

### 2. Run Example Script

**Using Pixi:**
```bash
pixi run run-example
```

**Or directly:**
```bash
python run_example.py
```

This will:
- Create sample data
- Run the analysis
- Generate reports in `reports/example_analysis/`

### 3. Using the Script Programmatically

```python
from analysis.phase_change_analysis_tool import run_phase_change_analysis
import pandas as pd

# Load your data
df = pd.read_csv("examples/sample_data.csv", index_col=0, parse_dates=True)

# Run analysis
run_phase_change_analysis(
    data=df,
    evu_col="EVU Meter",
    cooling_power_col="Cooling Power",
    spotmarket_energy_price_in_euro_per_mwh_col="Spot Market Price (€/MWh)",
    const_energy_price_in_euro_per_mwh_col=None,
    power_price_in_euro_per_kw=100,
    eer=3.5,
    schedule_temp_type="price_like_schedule",
    dflt_indoor_temp=2.0,
    min_temp_allowed=0.0,
    max_temp_allowed=4.0,
    mapping_of_walls_properties={
        "walls": {"area": 400, "heat_transfer_coef": 10}
    },
    mapping_of_content_properties={
        "air": {"mass": 1300, "specific_heat_capacity": 1005}
    },
    cooling_ramp_slope_in_k_per_h=-1.0,
    warming_ramp_slope_in_k_per_h=2.0,
    report_directory="reports/my_analysis",
    latent_heat_capacity_in_j_per_kg=334000,
    pcm_mass_in_kg=1000,
    phase_change_temp_in_c=0.0,
    latent_heat_factor=1.1,
)
```

### 4. Using the Notebooks

**Using Pixi:**
```bash
pixi run notebook
```

**Or directly:**
```bash
jupyter notebook
```

Then open `notebooks/potential_analysis.ipynb` and follow the examples.

## Phase-Change Cooling Specifics

Phase-change cooling systems differ from traditional systems in several ways:

1. **Latent Heat**: Uses latent heat of vaporization/condensation, providing higher energy density
2. **Efficiency Metrics**: Uses COP (Coefficient of Performance) values
3. **Thermal Storage**: Phase-change materials can provide thermal storage capabilities
4. **Operating Characteristics**: Different power profiles due to phase transitions

## Key Parameters

- **Latent Heat Capacity**: Energy absorbed/released during phase change (kJ/kg)
- **Phase Change Temperature**: Temperature at which phase transition occurs
- **COP**: Coefficient of Performance - efficiency metric for the cooling system
- **Refrigerant Properties**: Properties of the working fluid

## License

This project is provided as-is for analysis purposes.

