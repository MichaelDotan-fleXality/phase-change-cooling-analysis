"""
PV Self-Consumption Optimizer for Phase-Change Cooling Systems.

This module optimizes temperature schedules to maximize PV self-consumption
by shifting cooling operations to periods with PV surplus.
"""

import pandas as pd
import numpy as np
from typing import Union, Optional, List


def optimize_pv_self_consumption(
    schedule_temp: pd.Series,
    expected_surplus_phases: List,
    shortest_surplus_phase_allowed: str = "1h",
    cooling_ramp_slope_in_k_per_h: Union[int, float] = -1.0,
    warming_ramp_slope_in_k_per_h: Union[int, float] = 1.0,
    min_temp_allowed: Union[int, float] = 0.0,
    max_temp_allowed: Union[int, float] = 4.0,
    phase_change_temp: Optional[Union[int, float]] = None,
) -> pd.Series:
    """
    Optimize temperature schedule to maximize PV self-consumption.
    
    During PV surplus phases, the schedule is modified to:
    1. Create a cooling ramp (cool down using free PV energy)
    2. Maintain constant phase at minimum temperature (store cold energy)
    3. Create a warming ramp (warm up after surplus ends)
    
    This is particularly beneficial for phase-change cooling systems as
    the PCM can store thermal energy during surplus periods.
    
    Parameters:
    -----------
    schedule_temp : pd.Series
        Initial temperature schedule (from price-based optimization)
    expected_surplus_phases : list
        List of surplus phases. Each phase can be:
        - A tuple (start_index, end_index) from determine_surplus_phases
        - A pd.DatetimeIndex
        - An empty list (no surplus for that day)
    shortest_surplus_phase_allowed : str
        Minimum duration for a surplus phase to be optimized (e.g., "1h", "30min")
    cooling_ramp_slope_in_k_per_h : float
        Maximum cooling rate in K/h (negative value)
    warming_ramp_slope_in_k_per_h : float
        Maximum warming rate in K/h (positive value)
    min_temp_allowed : float
        Minimum allowed temperature
    max_temp_allowed : float
        Maximum allowed temperature
    phase_change_temp : float, optional
        Phase change temperature. If provided, the optimization may prefer
        operating near this temperature when beneficial.
    
    Returns:
    --------
    pd.Series
        Optimized temperature schedule with PV self-consumption optimization
    """
    # Validate inputs
    if not isinstance(schedule_temp, pd.Series):
        raise TypeError(f"schedule_temp must be a pandas Series, got {type(schedule_temp)}")
    
    if len(expected_surplus_phases) == 0:
        return schedule_temp
    
    # Check if all phases are empty
    all_empty = all(
        (isinstance(phase, list) and len(phase) == 0) or
        (isinstance(phase, tuple) and len(phase) == 0) or
        (hasattr(phase, '__len__') and len(phase) == 0)
        for phase in expected_surplus_phases
    )
    if all_empty:
        return schedule_temp
    
    # Validate parameters
    if cooling_ramp_slope_in_k_per_h >= 0:
        raise ValueError("cooling_ramp_slope_in_k_per_h must be negative")
    if warming_ramp_slope_in_k_per_h <= 0:
        raise ValueError("warming_ramp_slope_in_k_per_h must be positive")
    if min_temp_allowed >= max_temp_allowed:
        raise ValueError("min_temp_allowed must be less than max_temp_allowed")
    
    # Get time step
    index_step = _find_index_step(schedule_temp.index)
    index_step_as_str = _get_index_step_in_sec_as_str(index_step)
    dt_hours = pd.to_timedelta(index_step_as_str).total_seconds() / 3600.0
    
    # Group schedule by day
    schedule_temp = schedule_temp.copy()
    optimized_days = []
    daily_slices = schedule_temp.groupby(schedule_temp.index.date)
    
    # Process each day
    for day_idx, (date, day_schedule) in enumerate(daily_slices):
        # Get surplus phase for this day (if available)
        if day_idx < len(expected_surplus_phases):
            surplus_phase = expected_surplus_phases[day_idx]
        else:
            surplus_phase = []
        
        # Convert surplus phase to DatetimeIndex if it's a tuple
        if isinstance(surplus_phase, tuple) and len(surplus_phase) == 2:
            start_idx, end_idx = surplus_phase
            surplus_phase = pd.date_range(start=start_idx, end=end_idx, freq=index_step_as_str)
        elif not isinstance(surplus_phase, pd.DatetimeIndex) and not isinstance(surplus_phase, list):
            surplus_phase = []
        
        # Skip if no surplus phase or too short
        if len(surplus_phase) == 0:
            optimized_days.append(day_schedule)
            continue
        
        # Check if surplus phase is long enough
        if isinstance(surplus_phase, pd.DatetimeIndex):
            phase_duration = (surplus_phase.max() - surplus_phase.min()).total_seconds() / 3600.0
            min_duration = pd.Timedelta(shortest_surplus_phase_allowed).total_seconds() / 3600.0
            if phase_duration < min_duration:
                optimized_days.append(day_schedule)
                continue
            
            # Extract the part of schedule that matches surplus phase
            phase_schedule = day_schedule.loc[day_schedule.index.intersection(surplus_phase)]
            
            if len(phase_schedule) == 0:
                optimized_days.append(day_schedule)
                continue
            
            # Get temperature at start of surplus phase
            temp_at_start = day_schedule.loc[surplus_phase.min()]
            
            # Calculate cooling ramp duration
            temp_diff = temp_at_start - min_temp_allowed
            cooling_ramp_duration_h = abs(temp_diff / cooling_ramp_slope_in_k_per_h) if cooling_ramp_slope_in_k_per_h != 0 else 0
            surplus_duration_h = phase_duration
            
            # Number of time steps
            n_steps_surplus = len(surplus_phase)
            n_steps_cooling = min(int(cooling_ramp_duration_h / dt_hours) if dt_hours > 0 else 0, n_steps_surplus - 1)
            n_steps_constant = max(0, n_steps_surplus - n_steps_cooling - 1)
            
            # Create optimized schedule for surplus phase
            optimized_phase = pd.Series(index=surplus_phase, dtype=float)
            
            # Cooling ramp
            if n_steps_cooling > 0 and n_steps_cooling + 1 <= n_steps_surplus:
                cooling_ramp_temps = np.linspace(
                    temp_at_start,
                    min_temp_allowed,
                    n_steps_cooling + 1
                )
                optimized_phase.iloc[:n_steps_cooling+1] = cooling_ramp_temps
            elif n_steps_surplus > 0:
                # If surplus phase is too short for cooling ramp, just set to min temp
                optimized_phase.iloc[:] = min_temp_allowed
            
            # Constant phase at minimum temperature
            if n_steps_constant > 0 and n_steps_cooling + 1 + n_steps_constant <= n_steps_surplus:
                optimized_phase.iloc[n_steps_cooling+1:n_steps_cooling+1+n_steps_constant] = min_temp_allowed
            
            # Set end temperature (start of warming ramp)
            if len(optimized_phase) > 0:
                optimized_phase.iloc[-1] = min_temp_allowed
            
            # Interpolate any remaining NaN values
            optimized_phase = optimized_phase.interpolate(method='time')
            optimized_phase = optimized_phase.fillna(min_temp_allowed)
            
            # Insert optimized phase into day schedule
            day_schedule.loc[optimized_phase.index] = optimized_phase
            
            # Create warming ramp after surplus phase
            if surplus_phase.max() < day_schedule.index.max():
                # Get the part after surplus phase
                after_surplus = day_schedule.loc[day_schedule.index > surplus_phase.max()]
                
                if len(after_surplus) > 0:
                    # Get original temperature at first point after surplus
                    original_temp_after = day_schedule.loc[after_surplus.index[0]]
                    
                    # Calculate what temperature we can reach with warming ramp
                    time_to_next = dt_hours
                    max_warming = warming_ramp_slope_in_k_per_h * time_to_next
                    target_temp = min(min_temp_allowed + max_warming, original_temp_after, max_temp_allowed)
                    
                    # Apply warming ramp
                    current_temp = min_temp_allowed
                    for i, idx in enumerate(after_surplus.index):
                        # Calculate target based on original schedule and ramp constraint
                        original = day_schedule.loc[idx]
                        max_change = warming_ramp_slope_in_k_per_h * dt_hours
                        
                        # Can we reach original temperature?
                        if original <= current_temp + max_change:
                            target = original
                        else:
                            target = current_temp + max_change
                        
                        target = min(target, max_temp_allowed)
                        day_schedule.loc[idx] = target
                        current_temp = target
        
        optimized_days.append(day_schedule)
    
    # Concatenate all days
    if len(optimized_days) == 0:
        return schedule_temp
    
    optimized_schedule = pd.concat(optimized_days)
    optimized_schedule = optimized_schedule.sort_index()
    
    # Ensure temperature bounds
    optimized_schedule = optimized_schedule.clip(lower=min_temp_allowed, upper=max_temp_allowed)
    
    # Ensure we have all original indices
    optimized_schedule = optimized_schedule.reindex(schedule_temp.index, method='nearest')
    
    return optimized_schedule.squeeze()


def _find_index_step(index: pd.DatetimeIndex) -> pd.Timedelta:
    """Find the time step of a DatetimeIndex."""
    if len(index) < 2:
        return pd.Timedelta("15min")  # Default
    return index[1] - index[0]


def _get_index_step_in_sec_as_str(index_step: pd.Timedelta) -> str:
    """Convert time step to string format."""
    total_seconds = int(index_step.total_seconds())
    
    if total_seconds < 60:
        return f"{total_seconds}s"
    elif total_seconds < 3600:
        minutes = total_seconds // 60
        return f"{minutes}min"
    else:
        hours = total_seconds // 3600
        return f"{hours}h"

