"""
Emission-based temperature schedule creators for cooling optimization.

These functions create temperature schedules optimized for emission reduction
based on CO₂ emission factors, similar to price-based optimization.
"""

import pandas as pd
import numpy as np
from typing import Union


def create_emission_like_schedule(
    df: pd.DataFrame,
    emission_factor_col: str,
    min_temp_allowed_col: str,
    max_temp_allowed_col: str,
    ramp_slope_in_k_per_h: Union[int, float],
    phase_change_temp: Union[int, float, None] = None,
) -> pd.Series:
    """
    Create temperature schedule that follows emission factor pattern.
    
    Lower temperatures when emissions are low, higher when high.
    This minimizes CO₂ emissions by cooling more when grid is cleaner.
    Optionally considers phase-change temperature for optimal operation.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Input DataFrame
    emission_factor_col : str
        Column name for CO₂ emission factors (g CO₂/kWh or kg CO₂/kWh)
    min_temp_allowed_col : str
        Column name for minimum allowed temperature
    max_temp_allowed_col : str
        Column name for maximum allowed temperature
    ramp_slope_in_k_per_h : float
        Maximum temperature change rate in K/h (negative for cooling)
    phase_change_temp : float, optional
        Phase change temperature to consider for optimization
    
    Returns:
    --------
    pd.Series
        Temperature schedule optimized for emissions
    """
    emission_factors = df[emission_factor_col]
    min_temp = df[min_temp_allowed_col].iloc[0]
    max_temp = df[max_temp_allowed_col].iloc[0]
    
    # Normalize emission factors to 0-1 range
    # Low emissions = 0, High emissions = 1
    emission_min = emission_factors.min()
    emission_max = emission_factors.max()
    emission_range = emission_max - emission_min
    
    if emission_range == 0:
        normalized_emissions = pd.Series(0.5, index=emission_factors.index)
    else:
        normalized_emissions = (emission_factors - emission_min) / emission_range
    
    # Invert: low emissions -> low temps (more cooling), high emissions -> high temps (less cooling)
    # Formula: min_temp (coldest) + normalized_emissions * range
    # When normalized_emissions=0 (low emissions): target = min_temp (coldest, more cooling)
    # When normalized_emissions=1 (high emissions): target = max_temp (warmest, less cooling)
    target_temps = min_temp + normalized_emissions * (max_temp - min_temp)
    
    # Apply phase-change temperature preference if provided
    if phase_change_temp is not None:
        # Prefer operating near phase change temperature when possible
        phase_change_range = 1.0  # ±1°C around phase change temp
        preferred_range = (target_temps >= phase_change_temp - phase_change_range) & \
                         (target_temps <= phase_change_temp + phase_change_range)
        # Adjust slightly towards phase change temp when in preferred range
        target_temps = pd.Series(
            np.where(
                preferred_range,
                np.clip(target_temps, phase_change_temp - phase_change_range, 
                       phase_change_temp + phase_change_range),
                target_temps
            ),
            index=target_temps.index
        )
    
    # Apply ramp rate constraints
    # IMPORTANT: When emissions increase, we should warm up faster (or at least stop cooling)
    # Use asymmetric ramp rates: faster warming when emissions increase
    schedule = pd.Series(index=df.index, dtype=float)
    schedule.iloc[0] = target_temps.iloc[0]
    
    dt_hours = (df.index[1] - df.index[0]).total_seconds() / 3600
    cooling_ramp_rate = abs(ramp_slope_in_k_per_h)  # Normal cooling rate
    warming_ramp_rate = abs(ramp_slope_in_k_per_h) * 2.0  # Faster warming rate (2x)
    
    max_cooling_change = cooling_ramp_rate * dt_hours
    max_warming_change = warming_ramp_rate * dt_hours
    
    for i in range(1, len(target_temps)):
        target = target_temps.iloc[i]
        previous = schedule.iloc[i-1]
        change = target - previous
        
        # Use faster warming when emissions increase (target > previous)
        if change > 0:  # Warming
            if abs(change) > max_warming_change:
                change = max_warming_change
        else:  # Cooling
            if abs(change) > max_cooling_change:
                change = -max_cooling_change
        
        schedule.iloc[i] = previous + change
    
    return schedule.clip(lower=min_temp, upper=max_temp)


def create_smoothed_emission_schedule(
    df: pd.DataFrame,
    emission_factor_col: str,
    min_temp_allowed_col: str,
    max_temp_allowed_col: str,
    ramp_slope_in_k_per_h: Union[int, float],
    smoothing_window_hours: float = 4.0,
    phase_change_temp: Union[int, float, None] = None,
) -> pd.Series:
    """
    Create temperature schedule that follows emission factor pattern with smoothing.
    
    This is similar to create_emission_like_schedule but uses smoothed emission factors
    to create a less dynamic schedule that responds more gradually to emission changes.
    
    Lower temperatures when emissions are low, higher when high.
    Uses smoothed emission signal to reduce rapid temperature changes.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Input DataFrame
    emission_factor_col : str
        Column name for CO₂ emission factors
    min_temp_allowed_col : str
        Column name for minimum allowed temperature
    max_temp_allowed_col : str
        Column name for maximum allowed temperature
    ramp_slope_in_k_per_h : float
        Maximum temperature change rate in K/h (negative for cooling)
    smoothing_window_hours : float, optional
        Hours to use for emission smoothing (default: 4.0)
        Larger values = smoother, less dynamic schedule
    phase_change_temp : float, optional
        Phase change temperature to consider for optimization
    
    Returns:
    --------
    pd.Series
        Smoothed temperature schedule optimized for emissions
    """
    emission_factors = df[emission_factor_col]
    min_temp = df[min_temp_allowed_col].iloc[0]
    max_temp = df[max_temp_allowed_col].iloc[0]
    
    # Smooth emission factors using rolling average
    # Convert time step to number of periods for smoothing window
    if len(df) > 1:
        time_step_hours = (df.index[1] - df.index[0]).total_seconds() / 3600
        smoothing_periods = int(smoothing_window_hours / time_step_hours)
        smoothing_periods = max(1, smoothing_periods)  # At least 1 period
    else:
        smoothing_periods = 1
    
    # Apply rolling average (centered)
    smoothed_emissions = emission_factors.rolling(window=smoothing_periods, min_periods=1, center=True).mean()
    
    # Fill any NaN values at the beginning with forward fill, then backward fill
    smoothed_emissions = smoothed_emissions.ffill().bfill()
    
    # Normalize smoothed emission factors to 0-1 range
    emission_min = smoothed_emissions.min()
    emission_max = smoothed_emissions.max()
    emission_range = emission_max - emission_min
    
    if emission_range == 0:
        normalized_emissions = pd.Series(0.5, index=emission_factors.index)
    else:
        normalized_emissions = (smoothed_emissions - emission_min) / emission_range
    
    # Create schedule: low emissions -> low temps (more cooling), high emissions -> high temps (less cooling)
    # Formula: min_temp (coldest) + normalized_emissions * range
    target_temps = min_temp + normalized_emissions * (max_temp - min_temp)
    
    # Apply phase-change temperature preference if provided
    if phase_change_temp is not None:
        # Prefer operating near phase change temperature when possible
        phase_change_range = 1.0  # ±1°C around phase change temp
        preferred_range = (target_temps >= phase_change_temp - phase_change_range) & \
                         (target_temps <= phase_change_temp + phase_change_range)
        # Adjust slightly towards phase change temp when in preferred range
        target_temps = pd.Series(
            np.where(
                preferred_range,
                np.clip(target_temps, phase_change_temp - phase_change_range, 
                       phase_change_temp + phase_change_range),
                target_temps
            ),
            index=target_temps.index
        )
    
    # Apply ramp rate constraints
    # Use symmetric ramp rates for smoother transitions
    schedule = pd.Series(index=df.index, dtype=float)
    schedule.iloc[0] = target_temps.iloc[0]
    
    dt_hours = (df.index[1] - df.index[0]).total_seconds() / 3600
    max_change_per_step = abs(ramp_slope_in_k_per_h) * dt_hours
    
    for i in range(1, len(target_temps)):
        target = target_temps.iloc[i]
        previous = schedule.iloc[i-1]
        change = target - previous
        
        if abs(change) > max_change_per_step:
            change = np.sign(change) * max_change_per_step
        
        schedule.iloc[i] = previous + change
    
    return schedule.clip(lower=min_temp, upper=max_temp)

