"""
Temperature Validation Module for Phase-Change Cooling Systems.

This module validates the optimization by simulating the resulting temperatures
from the calculated cooling power and comparing them to the target schedule.
"""

import pandas as pd
import numpy as np
from typing import Union, Optional, Dict
import os


def simulate_temperature_from_cooling_power(
    df: pd.DataFrame,
    cooling_power_col: str,
    initial_temp: Union[int, float],
    overall_heat_transfer_coef_in_w_per_k: Union[int, float],
    overall_heat_capacity_in_j_per_k: Union[int, float],
    cop: Union[int, float],
    latent_heat_factor: Union[int, float] = 1.0,
    outside_temp_col: Optional[str] = None,
    baseline_cooling_power_col: Optional[str] = None,
    dflt_indoor_temp: Optional[Union[int, float]] = None,
) -> pd.Series:
    """
    Simulate temperature evolution from cooling power using thermal dynamics.
    
    This function performs a forward simulation to determine what temperature
    would result from applying the calculated cooling power, validating the
    optimization model.
    
    Thermal balance equation:
        C × dT/dt = Q_heat_in - Q_cooling
    Where:
        - C = heat capacity (J/K)
        - dT/dt = temperature change rate (°C/s)
        - Q_heat_in = heat transfer from outside (W)
        - Q_cooling = cooling capacity = electrical_power × COP × latent_heat_factor
    
    Parameters:
    -----------
    df : pd.DataFrame
        Input DataFrame with time series data
    cooling_power_col : str
        Column name for calculated cooling power (electrical, in kW)
    initial_temp : float
        Initial temperature in degrees Celsius
    overall_heat_transfer_coef_in_w_per_k : float
        Overall heat transfer coefficient in W/K
    overall_heat_capacity_in_j_per_k : float
        Overall sensible heat capacity in J/K
    cop : float
        Coefficient of Performance - dimensionless ratio (cooling capacity in kW / electrical power in kW)
    latent_heat_factor : float, optional
        Factor for latent heat benefits (default: 1.0)
    outside_temp_col : str, optional
        Column name for outside temperature. If not provided, will be estimated
        from baseline cooling power.
    baseline_cooling_power_col : str, optional
        Column name for baseline cooling power. Used to estimate outside temperature
        if outside_temp_col is not provided.
    dflt_indoor_temp : float, optional
        Default indoor temperature. Used with baseline cooling power to estimate
        outside temperature.
    
    Returns:
    --------
    pd.Series
        Simulated temperature evolution
    """
    df = df.copy()
    
    # Calculate time step in seconds
    if len(df) < 2:
        time_step_sec = 900  # Default 15 minutes
    else:
        time_step_sec = (df.index[1] - df.index[0]).total_seconds()
    
    # Use outside temperature if provided, otherwise estimate from date/month
    if outside_temp_col and outside_temp_col in df.columns:
        outside_temp = df[outside_temp_col]
    else:
        # Estimate outside temperature based on date/month
        # This is more reliable than estimating from cooling power
        # IMPORTANT: Calculate per timestamp to handle multi-month periods correctly
        if len(df) > 0:
            # Typical outdoor temperatures in Germany (Bremerhaven region) by month
            # Values in degrees Celsius
            monthly_avg_temp = {
                1: 2.0,   # January
                2: 2.5,   # February
                3: 5.0,   # March
                4: 9.0,   # April
                5: 14.0,  # May
                6: 17.0,  # June
                7: 19.0,  # July
                8: 19.0,  # August
                9: 15.0,  # September
                10: 11.0, # October
                11: 6.0,  # November
                12: 3.0,  # December
            }
            
            # Calculate base temperature for each timestamp based on its month
            base_temps = df.index.map(lambda x: monthly_avg_temp.get(x.month, 15.0))
            base_temp_series = pd.Series(base_temps, index=df.index)
            
            # Add daily variation (colder at night, warmer during day)
            hours = df.index.hour + df.index.minute / 60.0
            daily_variation = 5.0 * np.sin(2 * np.pi * (hours - 6) / 24)  # ±5C daily variation
            
            outside_temp = base_temp_series + daily_variation
            
            # Print info about temperature range
            months_present = sorted(df.index.month.unique())
            if len(months_present) == 1:
                month = months_present[0]
                base_temp = monthly_avg_temp.get(month, 15.0)
                print(f"[INFO] Using estimated outside temperature based on month ({month}): {base_temp:.1f}C average, with daily variation")
            else:
                temp_range = f"{base_temp_series.min():.1f}C to {base_temp_series.max():.1f}C"
                print(f"[INFO] Using estimated outside temperature for {len(months_present)} months: {temp_range} average, with daily variation")
        else:
            # Fallback to constant
            outside_temp = pd.Series(20.0, index=df.index)
            print("[WARNING] Using constant outside temperature (20C) - no date information available")
    
    # Initialize temperature series
    simulated_temp = pd.Series(index=df.index, dtype=float)
    simulated_temp.iloc[0] = initial_temp
    
    # Convert units
    W_TO_KW = 1e-3
    
    # Simulate temperature evolution step by step
    for i in range(1, len(df)):
        current_temp = simulated_temp.iloc[i-1]
        current_outside_temp = outside_temp.iloc[i] if isinstance(outside_temp, pd.Series) else outside_temp
        
        # Calculate heat transfer from outside (W)
        # Q_heat_in = U × (T_outside - T_inside)
        heat_transfer_in = (
            overall_heat_transfer_coef_in_w_per_k 
            * (current_outside_temp - current_temp)
        )
        
        # Calculate cooling capacity from electrical power (W)
        # COP is dimensionless (kW/kW), so cooling capacity = electrical_power × COP × latent_heat_factor
        # Both in same units (W or kW)
        electrical_power_w = df[cooling_power_col].iloc[i] * 1000  # Convert kW to W
        cooling_capacity = electrical_power_w * cop * latent_heat_factor  # W (since COP is dimensionless)
        
        # Net heat flow into the system (W)
        # Positive = heating, Negative = cooling
        net_heat_flow = heat_transfer_in - cooling_capacity
        
        # Calculate temperature change
        # C × dT/dt = Q_net
        # Therefore: dT = (Q_net × dt) / C
        temp_change = (net_heat_flow * time_step_sec) / overall_heat_capacity_in_j_per_k
        
        # Update temperature
        simulated_temp.iloc[i] = current_temp + temp_change
    
    return simulated_temp


def validate_temperature_schedule(
    df: pd.DataFrame,
    target_temp_col: str,
    cooling_power_col: str,
    initial_temp: Union[int, float],
    overall_heat_transfer_coef_in_w_per_k: Union[int, float],
    overall_heat_capacity_in_j_per_k: Union[int, float],
    cop: Union[int, float],
    latent_heat_factor: Union[int, float] = 1.0,
    outside_temp_col: Optional[str] = None,
    baseline_cooling_power_col: Optional[str] = None,
    dflt_indoor_temp: Optional[Union[int, float]] = None,
    tolerance: float = 1.0,  # °C tolerance
) -> Dict:
    """
    Validate temperature schedule by simulating resulting temperatures.
    
    This function:
    1. Simulates the temperature that would result from the calculated cooling power
    2. Compares simulated temperature with target schedule temperature
    3. Reports discrepancies and validation statistics
    
    Parameters:
    -----------
    df : pd.DataFrame
        Input DataFrame with time series data
    target_temp_col : str
        Column name for target temperature schedule
    cooling_power_col : str
        Column name for calculated cooling power
    initial_temp : float
        Initial temperature in degrees Celsius
    overall_heat_transfer_coef_in_w_per_k : float
        Overall heat transfer coefficient in W/K
    overall_heat_capacity_in_j_per_k : float
        Overall sensible heat capacity in J/K
    cop : float
        Coefficient of Performance - dimensionless ratio (cooling capacity in kW / electrical power in kW)
    latent_heat_factor : float, optional
        Factor for latent heat benefits (default: 1.0)
    outside_temp_col : str, optional
        Column name for outside temperature
    baseline_cooling_power_col : str, optional
        Column name for baseline cooling power (for estimating outside temp)
    dflt_indoor_temp : float, optional
        Default indoor temperature (for estimating outside temp)
    tolerance : float, optional
        Temperature tolerance in °C for validation (default: 1.0)
    
    Returns:
    --------
    dict
        Validation results containing:
        - 'simulated_temperature': pd.Series with simulated temperatures
        - 'mean_error': Mean absolute error between simulated and target (°C)
        - 'max_error': Maximum absolute error (°C)
        - 'rmse': Root mean square error (°C)
        - 'within_tolerance': Percentage of time points within tolerance
        - 'validation_passed': Boolean indicating if validation passed
        - 'error_statistics': Detailed error statistics
    """
    # Simulate temperature
    simulated_temp = simulate_temperature_from_cooling_power(
        df=df,
        cooling_power_col=cooling_power_col,
        initial_temp=initial_temp,
        overall_heat_transfer_coef_in_w_per_k=overall_heat_transfer_coef_in_w_per_k,
        overall_heat_capacity_in_j_per_k=overall_heat_capacity_in_j_per_k,
        cop=cop,
        latent_heat_factor=latent_heat_factor,
        outside_temp_col=outside_temp_col,
        baseline_cooling_power_col=baseline_cooling_power_col,
        dflt_indoor_temp=dflt_indoor_temp,
    )
    
    # Get target temperatures
    target_temp = df[target_temp_col]
    
    # Calculate errors
    errors = simulated_temp - target_temp
    abs_errors = errors.abs()
    
    # Calculate statistics
    mean_error = errors.mean()
    mean_abs_error = abs_errors.mean()
    max_error = abs_errors.max()
    rmse = np.sqrt((errors ** 2).mean())
    
    # Percentage within tolerance
    within_tolerance = (abs_errors <= tolerance).sum() / len(abs_errors) * 100
    
    # Validation passed if mean absolute error is within tolerance
    validation_passed = mean_abs_error <= tolerance
    
    # Error statistics
    error_stats = {
        'mean_error': mean_error,
        'mean_abs_error': mean_abs_error,
        'max_error': max_error,
        'rmse': rmse,
        'std_error': errors.std(),
        'within_tolerance_pct': within_tolerance,
        'min_error': errors.min(),
        'max_error': errors.max(),
        'q25_error': errors.quantile(0.25),
        'q50_error': errors.median(),
        'q75_error': errors.quantile(0.75),
    }
    
    results = {
        'simulated_temperature': simulated_temp,
        'target_temperature': target_temp,
        'errors': errors,
        'mean_error': mean_error,
        'mean_abs_error': mean_abs_error,
        'max_error': max_error,
        'rmse': rmse,
        'within_tolerance': within_tolerance,
        'validation_passed': validation_passed,
        'error_statistics': error_stats,
    }
    
    return results


def save_validation_report(
    validation_results: Dict,
    report_directory: str,
    system_group_name: Optional[str] = None,
) -> None:
    """
    Save validation report to Excel file.
    
    Parameters:
    -----------
    validation_results : dict
        Results from validate_temperature_schedule()
    report_directory : str
        Directory path for saving reports
    system_group_name : str, optional
        Name of system group for file naming
    """
    os.makedirs(report_directory, exist_ok=True)
    
    # Create DataFrame with validation data
    validation_df = pd.DataFrame({
        'Simulated Temperature (°C)': validation_results['simulated_temperature'],
        'Target Temperature (°C)': validation_results['target_temperature'],
        'Error (°C)': validation_results['errors'],
        'Absolute Error (°C)': validation_results['errors'].abs(),
    })
    
    # Create summary DataFrame
    summary_data = {
        'Metric': [
            'Mean Error (°C)',
            'Mean Absolute Error (°C)',
            'Max Absolute Error (°C)',
            'RMSE (°C)',
            'Within Tolerance (%)',
            'Validation Passed',
        ],
        'Value': [
            validation_results['mean_error'],
            validation_results['mean_abs_error'],
            validation_results['max_error'],
            validation_results['rmse'],
            validation_results['within_tolerance'],
            'Yes' if validation_results['validation_passed'] else 'No',
        ],
    }
    summary_df = pd.DataFrame(summary_data)
    
    # Detailed error statistics
    error_stats_df = pd.DataFrame([validation_results['error_statistics']])
    
    # Save to Excel
    filename = "temperature_validation.xlsx"
    if system_group_name:
        filename = f"temperature_validation_{system_group_name}.xlsx"
    
    filepath = os.path.join(report_directory, filename)
    
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        # Remove timezone information from index if present (Excel doesn't support timezone-aware datetimes)
        validation_df_to_write = validation_df.copy()
        if isinstance(validation_df_to_write.index, pd.DatetimeIndex) and validation_df_to_write.index.tz is not None:
            validation_df_to_write.index = validation_df_to_write.index.tz_localize(None)
        
        validation_df_to_write.to_excel(writer, sheet_name="Validation Data", index=True)
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        error_stats_df.to_excel(writer, sheet_name="Error Statistics", index=False)
    
    print(f"\n[OK] Temperature validation report saved to: {filepath}")
    print(f"  Mean Absolute Error: {validation_results['mean_abs_error']:.2f} C")
    print(f"  Max Error: {validation_results['max_error']:.2f} C")
    print(f"  Within Tolerance: {validation_results['within_tolerance']:.1f}%")
    print(f"  Validation Status: {'PASSED' if validation_results['validation_passed'] else 'FAILED'}")

