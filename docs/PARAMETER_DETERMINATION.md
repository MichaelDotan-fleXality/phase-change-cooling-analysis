# Parameter Determination for Cooling Systems

This document explains how parameters for different cooling systems (BÄKO and EcoCool) are determined.

## Overview

**Current Approach**: **Manual calibration** based on validation results, NOT automated parameter fitting.

The parameters are determined through an iterative process:
1. Start with theoretical/calculated values
2. Run simulation
3. Compare simulated vs. measured temperatures
4. Manually adjust calibration factors
5. Repeat until validation errors are acceptable

## Parameter Types

### 1. **Theoretical/Calculated Parameters**

These are determined from physical properties and system specifications:

#### U-Value (Heat Transfer Coefficient)
- **Source**: Calculated from insulation properties
- **Method**: `calculate_heat_transfer_coefficient(insulation_thickness, insulation_type)`
- **Location**: `utils/insulation_calculator.py`
- **Formula**: Based on insulation material properties (thermal conductivity, thickness)

#### Heat Capacity
- **Source**: Calculated from mass and specific heat capacity
- **Method**: `mass × specific_heat_capacity`
- **Components**:
  - Air mass: `volume × air_density`
  - Content mass: From system specifications
  - Specific heat: Material properties (air ≈ 1005 J/(kg·K))

#### COP (Coefficient of Performance)
- **Source**: Manufacturer specifications or typical values
- **Typical range**: 2.5 - 5.0 for commercial cooling systems
- **Initial value**: Often starts at 4.0 or from manufacturer data

### 2. **Calibration Factors**

These are multipliers applied to theoretical values to match real-world behavior:

#### U-Value Calibration Factor
- **Parameter**: `U_VALUE_CALIBRATION_FACTOR` in `config.py`
- **Current value**: `0.85` (15% reduction)
- **Purpose**: Adjusts calculated U-value to match measured heat transfer
- **Formula**: `U_calibrated = U_theoretical × U_VALUE_CALIBRATION_FACTOR`

**Why needed?**
- Theoretical calculations don't account for:
  - Air leaks
  - Imperfect insulation
  - Thermal bridges
  - Real-world installation conditions

#### Heat Capacity Calibration Factor
- **Parameter**: `HEAT_CAPACITY_CALIBRATION_FACTOR` in `config.py`
- **Current value**: `1.8` (80% increase)
- **Purpose**: Adjusts calculated heat capacity to match measured thermal inertia
- **Formula**: `C_calibrated = C_theoretical × HEAT_CAPACITY_CALIBRATION_FACTOR`

**Why needed?**
- Theoretical calculations don't account for:
  - Additional thermal mass (shelves, equipment)
  - Air circulation effects
  - Complex geometry

#### COP Calibration
- **Parameter**: `COP` in `config.py`
- **Current value**: `2.8` (calibrated from initial 4.0)
- **Purpose**: Adjusts cooling efficiency to match measured power consumption

**Why needed?**
- Manufacturer COP may be:
  - Under ideal conditions
  - Not accounting for real-world operation
  - System-specific variations

## Calibration Process

### Step-by-Step Manual Calibration

1. **Initial Setup**
   ```python
   # Start with theoretical values
   U_VALUE_CALIBRATION_FACTOR = 1.0  # No adjustment
   HEAT_CAPACITY_CALIBRATION_FACTOR = 1.0  # No adjustment
   COP = 4.0  # Typical value
   ```

2. **Run Analysis**
   - Run analysis with initial parameters
   - Generate validation report
   - Check validation errors (MAE, Max Error, RMSE)

3. **Analyze Validation Errors**
   - **Negative bias** (simulated temp > measured temp): Overestimating cooling
   - **Positive bias** (simulated temp < measured temp): Underestimating cooling

4. **Adjust Parameters**

   **For Negative Bias (Overestimating Cooling)**:
   - **Decrease U-value**: `U_VALUE_CALIBRATION_FACTOR = 0.8-0.9` (better insulation)
   - **Increase heat capacity**: `HEAT_CAPACITY_CALIBRATION_FACTOR = 1.1-1.3` (more thermal mass)
   - **Increase COP**: `COP = 3.0-3.5` (more efficient, less power needed)

   **For Positive Bias (Underestimating Cooling)**:
   - **Increase U-value**: `U_VALUE_CALIBRATION_FACTOR = 1.1-1.2` (worse insulation)
   - **Decrease heat capacity**: `HEAT_CAPACITY_CALIBRATION_FACTOR = 0.8-0.9` (less thermal mass)
   - **Decrease COP**: `COP = 2.0-2.5` (less efficient, more power needed)

5. **Iterate**
   - Update parameters in `config.py`
   - Re-run analysis
   - Check if errors improved
   - Repeat until errors are acceptable

### Example: BÄKO System Calibration

**Initial State**:
```python
COP = 4.0
U_VALUE_CALIBRATION_FACTOR = 1.0
HEAT_CAPACITY_CALIBRATION_FACTOR = 1.0
```

**After First Validation**:
- MAE: 3.5°C (too high)
- Bias: Negative (overestimating cooling)
- Max Error: 8.2°C

**Adjustments**:
```python
COP = 2.5  # Reduce from 4.0 (less efficient)
U_VALUE_CALIBRATION_FACTOR = 0.9  # Better insulation
HEAT_CAPACITY_CALIBRATION_FACTOR = 1.5  # More thermal mass
```

**After Second Validation**:
- MAE: 2.1°C (improved)
- Bias: Still slightly negative
- Max Error: 5.8°C

**Final Adjustments**:
```python
COP = 2.8  # Fine-tune
U_VALUE_CALIBRATION_FACTOR = 0.85  # Further reduce
HEAT_CAPACITY_CALIBRATION_FACTOR = 1.8  # Further increase
```

**Final Validation**:
- MAE: 1.2°C ✓ (acceptable)
- Bias: Minimal
- Max Error: 3.5°C ✓ (acceptable)

## System-Specific Parameters

### BÄKO Systems

**Pluskühlung**:
- Uses global calibration factors from `config.py`
- System-specific: `PHASE_CHANGE_TEMP = 0.0°C` (water/ice)
- System-specific: `LATENT_HEAT_CAPACITY = 334,000 J/kg` (water)

**Tiefkühlung**:
- Uses global calibration factors from `config.py`
- System-specific: `PHASE_CHANGE_TEMP = -20.0°C` (salt solution)
- System-specific: `LATENT_HEAT_CAPACITY = 200,000 J/kg` (salt solution)

### EcoCool System

**Current Status**: Parameters need to be calibrated
- **Initial values**: Set in `run_ecocool_emission_analysis.py`
- **COP**: `2.5` (to be calibrated)
- **U-value**: Calculated from insulation properties (to be calibrated)
- **Heat capacity**: Calculated from mass (to be calibrated)

**Calibration Needed**:
1. Run analysis with initial parameters
2. Compare with measured EcoCool data (`ecocool_2024.csv`)
3. Adjust parameters to match measured behavior
4. Save calibrated parameters

## Automated Parameter Fitting (Future)

Currently, **NO automated parameter fitting** is implemented. However, this could be added:

### Potential Approach

1. **Objective Function**: Minimize validation errors (MAE, RMSE)
2. **Parameters to Fit**:
   - `U_VALUE_CALIBRATION_FACTOR`
   - `HEAT_CAPACITY_CALIBRATION_FACTOR`
   - `COP`
   - PCM parameters (if applicable)

3. **Optimization Method**:
   - Grid search
   - Bayesian optimization
   - Gradient-based optimization (if differentiable)

4. **Constraints**:
   - Physical bounds (e.g., COP > 1.0)
   - Reasonable ranges (e.g., U-value factor: 0.5 - 1.5)

### Example Implementation (Conceptual)

```python
from scipy.optimize import minimize

def objective_function(params):
    """Minimize validation errors."""
    u_factor, c_factor, cop = params
    
    # Update config
    config.U_VALUE_CALIBRATION_FACTOR = u_factor
    config.HEAT_CAPACITY_CALIBRATION_FACTOR = c_factor
    config.COP = cop
    
    # Run analysis
    results = run_analysis(...)
    
    # Calculate validation errors
    mae = calculate_mae(results)
    
    return mae

# Optimize
result = minimize(
    objective_function,
    x0=[0.85, 1.8, 2.8],  # Initial guess
    bounds=[(0.5, 1.5), (0.5, 2.5), (1.5, 5.0)],  # Parameter bounds
    method='L-BFGS-B'
)

# Save optimized parameters
config.U_VALUE_CALIBRATION_FACTOR = result.x[0]
config.HEAT_CAPACITY_CALIBRATION_FACTOR = result.x[1]
config.COP = result.x[2]
```

## Current Parameter Values

### BÄKO Systems (Calibrated)

**From `config.py`**:
```python
COP = 2.8  # Calibrated from 4.0
U_VALUE_CALIBRATION_FACTOR = 0.85  # 15% reduction
HEAT_CAPACITY_CALIBRATION_FACTOR = 1.8  # 80% increase
```

**System-Specific**:
```python
# Pluskühlung
PHASE_CHANGE_TEMP_PLUSKUEHLUNG_C = 0.0
LATENT_HEAT_CAPACITY_PLUSKUEHLUNG_J_PER_KG = 334000

# Tiefkühlung
PHASE_CHANGE_TEMP_TIEFKUEHLUNG_C = -20.0
LATENT_HEAT_CAPACITY_TIEFKUEHLUNG_J_PER_KG = 200000
```

### EcoCool System (To Be Calibrated)

**From `run_ecocool_emission_analysis.py`**:
```python
COP = 2.5  # Initial value, needs calibration
# U-value: Calculated from insulation (needs calibration factor)
# Heat capacity: Calculated from mass (needs calibration factor)
```

## Validation Metrics

Parameters are adjusted to minimize:

1. **Mean Absolute Error (MAE)**: Average temperature difference
2. **Max Error**: Maximum temperature difference
3. **RMSE**: Root Mean Square Error
4. **Within Tolerance**: Percentage of points within acceptable range

**Target Values** (for BÄKO):
- MAE < 2.0°C
- Max Error < 5.0°C
- Within Tolerance > 80%

## Summary

**Current Method**: **Manual calibration** (iterative adjustment based on validation)

**Process**:
1. Start with theoretical/calculated values
2. Run simulation → Get validation errors
3. Analyze bias (positive/negative)
4. Adjust calibration factors
5. Repeat until errors acceptable

**NOT Currently Used**: Automated parameter fitting/optimization

**Future Enhancement**: Could implement automated parameter fitting using optimization algorithms (scipy.optimize, Bayesian optimization, etc.)

**Key Parameters**:
- **U-value calibration factor**: Adjusts heat transfer
- **Heat capacity calibration factor**: Adjusts thermal mass
- **COP**: Adjusts cooling efficiency

All parameters are stored in `config.py` (for BÄKO) or in the analysis script (for EcoCool).

