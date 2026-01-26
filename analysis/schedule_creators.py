"""
Temperature schedule creators for phase-change cooling optimization.

These functions create temperature schedules optimized for energy cost savings
while considering phase-change cooling system characteristics.
"""

import pandas as pd
import numpy as np
from typing import Union


def create_price_like_schedule(
    df: pd.DataFrame,
    spotmarket_energy_price_col: str,
    min_temp_allowed_col: str,
    max_temp_allowed_col: str,
    ramp_slope_in_k_per_h: Union[int, float],
    phase_change_temp: Union[int, float, None] = None,
) -> pd.Series:
    """
    Create temperature schedule that follows energy price pattern.
    
    Lower temperatures when energy is cheap, higher when expensive.
    Optionally considers phase-change temperature for optimal operation.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Input DataFrame
    spotmarket_energy_price_col : str
        Column name for spot market energy prices
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
        Temperature schedule
    """
    prices = df[spotmarket_energy_price_col]
    min_temp = df[min_temp_allowed_col].iloc[0]
    max_temp = df[max_temp_allowed_col].iloc[0]
    
    # Normalize prices to 0-1 range
    price_min = prices.min()
    price_max = prices.max()
    price_range = price_max - price_min
    
    if price_range == 0:
        normalized_prices = pd.Series(0.5, index=prices.index)
    else:
        normalized_prices = (prices - price_min) / price_range
    
    # Invert: low prices -> low temps (more cooling), high prices -> high temps (less cooling)
    # Formula: min_temp (coldest) + normalized_prices * range
    # When normalized_prices=0 (low price): target = min_temp (coldest, more cooling)
    # When normalized_prices=1 (high price): target = max_temp (warmest, less cooling)
    target_temps = min_temp + normalized_prices * (max_temp - min_temp)
    
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
    # IMPORTANT: When prices increase, we should warm up faster (or at least stop cooling)
    # Use asymmetric ramp rates: faster warming when prices increase
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
        
        # Use faster warming when prices increase (target > previous)
        if change > 0:  # Warming
            if abs(change) > max_warming_change:
                change = max_warming_change
        else:  # Cooling
            if abs(change) > max_cooling_change:
                change = -max_cooling_change
        
        schedule.iloc[i] = previous + change
    
    return schedule.clip(lower=min_temp, upper=max_temp)


def create_smoothed_price_schedule(
    df: pd.DataFrame,
    spotmarket_energy_price_col: str,
    min_temp_allowed_col: str,
    max_temp_allowed_col: str,
    ramp_slope_in_k_per_h: Union[int, float],
    smoothing_window_hours: float = 4.0,
    phase_change_temp: Union[int, float, None] = None,
) -> pd.Series:
    """
    Create temperature schedule that follows energy price pattern with smoothing.
    
    This is similar to create_price_like_schedule but uses smoothed prices to create
    a less dynamic schedule that responds more gradually to price changes.
    
    Lower temperatures when energy is cheap, higher when expensive.
    Uses smoothed price signal to reduce rapid temperature changes.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Input DataFrame
    spotmarket_energy_price_col : str
        Column name for spot market energy prices
    min_temp_allowed_col : str
        Column name for minimum allowed temperature
    max_temp_allowed_col : str
        Column name for maximum allowed temperature
    ramp_slope_in_k_per_h : float
        Maximum temperature change rate in K/h (negative for cooling)
    smoothing_window_hours : float, optional
        Hours to use for price smoothing (default: 4.0)
        Larger values = smoother, less dynamic schedule
    phase_change_temp : float, optional
        Phase change temperature to consider for optimization
    
    Returns:
    --------
    pd.Series
        Smoothed temperature schedule
    """
    prices = df[spotmarket_energy_price_col]
    min_temp = df[min_temp_allowed_col].iloc[0]
    max_temp = df[max_temp_allowed_col].iloc[0]
    
    # Calculate time step in hours
    dt_hours = (df.index[1] - df.index[0]).total_seconds() / 3600 if len(df) > 1 else 0.25
    
    # Smooth prices using rolling average
    # Convert smoothing_window_hours to number of periods
    smoothing_periods = int(smoothing_window_hours / dt_hours)
    smoothing_periods = max(1, smoothing_periods)  # At least 1 period
    
    smoothed_prices = prices.rolling(window=smoothing_periods, min_periods=1, center=False).mean()
    # Fill any NaN values at the beginning with forward fill, then backward fill
    smoothed_prices = smoothed_prices.ffill().bfill()
    
    # Normalize smoothed prices to 0-1 range
    price_min = smoothed_prices.min()
    price_max = smoothed_prices.max()
    price_range = price_max - price_min
    
    if price_range == 0:
        normalized_prices = pd.Series(0.5, index=prices.index)
    else:
        normalized_prices = (smoothed_prices - price_min) / price_range
    
    # Create schedule: low prices -> low temps (more cooling), high prices -> high temps (less cooling)
    # Formula: min_temp (coldest) + normalized_prices * range
    # When normalized_prices=0 (low price): target = min_temp (coldest, more cooling)
    # When normalized_prices=1 (high price): target = max_temp (warmest, less cooling)
    target_temps = min_temp + normalized_prices * (max_temp - min_temp)
    
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
    
    dt_hours = (df.index[1] - df.index[0]).total_seconds() / 3600 if len(df) > 1 else 0.25
    max_change_per_step = abs(ramp_slope_in_k_per_h) * dt_hours
    
    for i in range(1, len(target_temps)):
        target = target_temps.iloc[i]
        previous = schedule.iloc[i-1]
        change = target - previous
        
        if abs(change) > max_change_per_step:
            change = np.sign(change) * max_change_per_step
        
        schedule.iloc[i] = previous + change
    
    return schedule.clip(lower=min_temp, upper=max_temp)


def create_constant_schedule(
    df: pd.DataFrame,
    constant_temp: Union[int, float],
) -> pd.Series:
    """
    Create constant temperature schedule.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Input DataFrame
    constant_temp : float
        Constant temperature value
    
    Returns:
    --------
    pd.Series
        Constant temperature schedule
    """
    return pd.Series(constant_temp, index=df.index)


def create_altering_step_schedule(
    df: pd.DataFrame,
    spotmarket_energy_price_col: str,
    dflt_temp_allowed_col: str,
    min_temp_allowed_col: str,
    max_temp_allowed_col: str,
    cooling_ramp_slope_in_k_per_h: Union[int, float],
    warming_ramp_slope_in_k_per_h: Union[int, float],
    phase_change_temp: Union[int, float, None] = None,
) -> pd.Series:
    """
    Create alternating step schedule that switches between min and max temperatures.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Input DataFrame
    spotmarket_energy_price_col : str
        Column name for spot market energy prices
    dflt_temp_allowed_col : str
        Column name for default temperature
    min_temp_allowed_col : str
        Column name for minimum allowed temperature
    max_temp_allowed_col : str
        Column name for maximum allowed temperature
    cooling_ramp_slope_in_k_per_h : float
        Cooling ramp slope (negative value)
    warming_ramp_slope_in_k_per_h : float
        Warming ramp slope (positive value)
    phase_change_temp : float, optional
        Phase change temperature to consider
    
    Returns:
    --------
    pd.Series
        Alternating step temperature schedule
    """
    prices = df[spotmarket_energy_price_col]
    min_temp = df[min_temp_allowed_col].iloc[0]
    max_temp = df[max_temp_allowed_col].iloc[0]
    dflt_temp = df[dflt_temp_allowed_col].iloc[0]
    
    # Calculate price threshold (median)
    price_threshold = prices.median()
    
    # Determine target temperature based on price
    target_temps = np.where(prices < price_threshold, min_temp, max_temp)
    
    # Apply phase-change temperature preference
    if phase_change_temp is not None:
        # If phase change temp is between min and max, prefer it
        if min_temp <= phase_change_temp <= max_temp:
            # Use phase change temp as intermediate step
            mid_price_threshold = prices.quantile(0.33)
            high_price_threshold = prices.quantile(0.67)
            target_temps = np.where(
                prices < mid_price_threshold, min_temp,
                np.where(prices > high_price_threshold, max_temp, phase_change_temp)
            )
    
    # Apply ramp constraints
    schedule = pd.Series(index=df.index, dtype=float)
    schedule.iloc[0] = dflt_temp
    
    dt_hours = (df.index[1] - df.index[0]).total_seconds() / 3600
    
    for i in range(1, len(target_temps)):
        target = target_temps[i]
        previous = schedule.iloc[i-1]
        change = target - previous
        
        if change < 0:  # Cooling
            max_change = abs(cooling_ramp_slope_in_k_per_h) * dt_hours
        else:  # Warming
            max_change = warming_ramp_slope_in_k_per_h * dt_hours
        
        if abs(change) > max_change:
            change = np.sign(change) * max_change
        
        schedule.iloc[i] = previous + change
    
    return schedule.clip(lower=min_temp, upper=max_temp)

