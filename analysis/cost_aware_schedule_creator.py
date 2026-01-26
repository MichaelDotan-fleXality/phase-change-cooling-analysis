"""
Cost-aware temperature schedule creator.

This module creates temperature schedules that consider both energy price timing
and total energy consumption costs, preventing excessive cooling that increases costs.
"""

import pandas as pd
import numpy as np
from typing import Union, Optional


def create_cost_aware_schedule(
    df: pd.DataFrame,
    spotmarket_energy_price_col: str,
    min_temp_allowed_col: str,
    max_temp_allowed_col: str,
    dflt_indoor_temp_col: str,
    ramp_slope_in_k_per_h: Union[int, float],
    overall_heat_transfer_coef_in_w_per_k: Union[int, float],
    cop: Union[int, float],
    max_temp_deviation_from_default: Optional[Union[int, float]] = None,
    phase_change_temp: Optional[Union[int, float]] = None,
) -> pd.Series:
    """
    Create cost-aware temperature schedule that balances price timing with energy consumption.
    
    This function considers:
    1. Energy price timing (cool when prices are low)
    2. Energy consumption cost (deeper cooling costs more)
    3. Maximum deviation from default temperature
    
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
    dflt_indoor_temp_col : str
        Column name for default indoor temperature
    ramp_slope_in_k_per_h : float
        Maximum temperature change rate in K/h (negative for cooling)
    overall_heat_transfer_coef_in_w_per_k : float
        Overall heat transfer coefficient in W/K
    cop : float
        Coefficient of Performance
    max_temp_deviation_from_default : float, optional
        Maximum allowed deviation from default temperature (°C)
        If None, uses full range (min_temp to max_temp)
    phase_change_temp : float, optional
        Phase change temperature to consider for optimization
    
    Returns:
    --------
    pd.Series
        Cost-aware temperature schedule
    """
    prices = df[spotmarket_energy_price_col]
    min_temp = df[min_temp_allowed_col].iloc[0]
    max_temp = df[max_temp_allowed_col].iloc[0]
    dflt_temp = df[dflt_indoor_temp_col].iloc[0]
    
    # Calculate effective temperature range considering deviation limit
    if max_temp_deviation_from_default is not None:
        effective_min_temp = max(min_temp, dflt_temp - max_temp_deviation_from_default)
        effective_max_temp = min(max_temp, dflt_temp + max_temp_deviation_from_default)
    else:
        effective_min_temp = min_temp
        effective_max_temp = max_temp
    
    # Normalize prices to 0-1 range
    price_min = prices.min()
    price_max = prices.max()
    price_range = price_max - price_min
    
    if price_range == 0:
        normalized_prices = pd.Series(0.5, index=prices.index)
    else:
        normalized_prices = (prices - price_min) / price_range
    
    # Calculate cost-benefit for different temperature deviations
    # For each time step, find optimal temperature considering:
    # 1. Price benefit (cooling when prices are low)
    # 2. Energy cost (deeper cooling costs more)
    
    target_temps = pd.Series(index=df.index, dtype=float)
    
    # Get time step in hours
    dt_hours = (df.index[1] - df.index[0]).total_seconds() / 3600 if len(df) > 1 else 0.25
    
    for i, (idx, price) in enumerate(prices.items()):
        # Calculate cost-benefit for different temperatures
        temp_options = np.linspace(effective_min_temp, effective_max_temp, 20)
        best_temp = dflt_temp
        best_score = -np.inf
        
        for temp in temp_options:
            deviation = dflt_temp - temp  # Positive when cooling
            
            # Score = price benefit - energy cost
            # Price benefit: higher when price is low and we're cooling
            if deviation > 0:  # Cooling
                price_benefit = (1.0 - normalized_prices.iloc[i]) * abs(deviation)
            else:  # Warming (or staying at default)
                price_benefit = normalized_prices.iloc[i] * abs(deviation)
            
            # Energy cost: deeper cooling costs more
            # Additional cooling load = U × ΔT
            if deviation > 0:  # Cooling below default
                additional_cooling_kw = overall_heat_transfer_coef_in_w_per_k * deviation / 1000
                additional_energy_kwh = additional_cooling_kw * dt_hours / cop
                energy_cost = additional_energy_kwh * price / 100  # Convert €/MWh to €
            else:  # At or above default
                energy_cost = 0  # No additional cost
            
            # Score: benefit - cost
            # Higher score = better
            score = price_benefit - energy_cost * 10  # Scale energy cost
            
            # Prefer staying near default if scores are similar
            if abs(score - best_score) < 0.1:
                if abs(temp - dflt_temp) < abs(best_temp - dflt_temp):
                    best_temp = temp
                    best_score = score
            elif score > best_score:
                best_temp = temp
                best_score = score
        
        # Apply phase change temperature preference if provided
        if phase_change_temp is not None:
            phase_change_range = 1.0
            if abs(best_temp - phase_change_temp) < phase_change_range:
                # Prefer phase change temp if close
                best_temp = phase_change_temp
        
        target_temps.iloc[i] = best_temp
    
    # Apply ramp rate constraints
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


def create_constrained_price_schedule(
    df: pd.DataFrame,
    spotmarket_energy_price_col: str,
    min_temp_allowed_col: str,
    max_temp_allowed_col: str,
    dflt_indoor_temp_col: str,
    ramp_slope_in_k_per_h: Union[int, float],
    max_deviation_from_default: Union[int, float] = 2.0,
    phase_change_temp: Optional[Union[int, float]] = None,
) -> pd.Series:
    """
    Create price-based schedule with maximum deviation constraint.
    
    This is a simpler version that limits how far from default we can go.
    
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
    dflt_indoor_temp_col : str
        Column name for default indoor temperature
    ramp_slope_in_k_per_h : float
        Maximum temperature change rate in K/h
    max_deviation_from_default : float
        Maximum allowed deviation from default temperature (°C)
    phase_change_temp : float, optional
        Phase change temperature
    
    Returns:
    --------
    pd.Series
        Constrained temperature schedule
    """
    prices = df[spotmarket_energy_price_col]
    min_temp = df[min_temp_allowed_col].iloc[0]
    max_temp = df[max_temp_allowed_col].iloc[0]
    dflt_temp = df[dflt_indoor_temp_col].iloc[0]
    
    # Calculate constrained range
    constrained_min = max(min_temp, dflt_temp - max_deviation_from_default)
    constrained_max = min(max_temp, dflt_temp + max_deviation_from_default)
    
    # Normalize prices
    price_min = prices.min()
    price_max = prices.max()
    price_range = price_max - price_min
    
    if price_range == 0:
        normalized_prices = pd.Series(0.5, index=prices.index)
    else:
        normalized_prices = (prices - price_min) / price_range
    
    # Create schedule: low prices -> cooler (within constraint), high prices -> warmer
    # Formula: constrained_min (coldest) + normalized_prices * range
    # When normalized_prices=0 (low price): target = constrained_min (coldest, more cooling)
    # When normalized_prices=1 (high price): target = constrained_max (warmest, less cooling)
    target_temps = constrained_min + normalized_prices * (constrained_max - constrained_min)
    
    # Apply phase change preference if provided
    if phase_change_temp is not None:
        phase_change_range = 1.0
        preferred_range = (target_temps >= phase_change_temp - phase_change_range) & \
                         (target_temps <= phase_change_temp + phase_change_range)
        target_temps = pd.Series(
            np.where(
                preferred_range,
                np.clip(target_temps, phase_change_temp - phase_change_range,
                       phase_change_temp + phase_change_range),
                target_temps
            ),
            index=target_temps.index
        )
    
    # Apply ramp constraints
    # IMPORTANT: When prices increase, we should warm up faster (or at least stop cooling)
    # Use different ramp rates for cooling vs warming to prioritize price response
    schedule = pd.Series(index=df.index, dtype=float)
    schedule.iloc[0] = target_temps.iloc[0]
    
    dt_hours = (df.index[1] - df.index[0]).total_seconds() / 3600 if len(df) > 1 else 0.25
    
    # Use faster warming rate when prices increase (to avoid cooling during high prices)
    # Default warming rate is typically 2x cooling rate
    warming_ramp_rate = abs(ramp_slope_in_k_per_h) * 2.0  # Faster warming
    cooling_ramp_rate = abs(ramp_slope_in_k_per_h)  # Normal cooling
    
    max_cooling_change = cooling_ramp_rate * dt_hours
    max_warming_change = warming_ramp_rate * dt_hours
    
    for i in range(1, len(target_temps)):
        target = target_temps.iloc[i]
        previous = schedule.iloc[i-1]
        change = target - previous
        
        # Determine if we're warming or cooling
        if change > 0:  # Warming (target > previous)
            # When warming (prices increased), use faster ramp rate
            if abs(change) > max_warming_change:
                change = max_warming_change
        else:  # Cooling (target < previous)
            # When cooling (prices decreased), use normal ramp rate
            if abs(change) > max_cooling_change:
                change = -max_cooling_change
        
        schedule.iloc[i] = previous + change
    
    return schedule.clip(lower=min_temp, upper=max_temp)

