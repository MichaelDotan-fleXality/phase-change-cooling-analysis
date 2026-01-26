"""
Enhanced PCM (Phase-Change Material) Model.

This module provides an improved PCM model that accounts for:
1. Continuous phase change (not just discrete transitions)
2. Thermal buffering effects
3. Gradual phase change over a temperature range
4. Effective heat capacity variation
"""

import numpy as np
import pandas as pd
from typing import Union, Optional, Tuple


def calculate_phase_fraction(
    temp: Union[float, pd.Series],
    phase_change_temp: float,
    phase_change_range: float = 2.0,
) -> Union[float, pd.Series]:
    """
    Calculate phase fraction (0 = solid, 1 = liquid) based on temperature.
    
    Uses a smooth transition function instead of discrete transitions.
    Phase change occurs over a temperature range, not instantaneously.
    
    Parameters:
    -----------
    temp : float or pd.Series
        Current temperature in °C
    phase_change_temp : float
        Nominal phase change temperature in °C
    phase_change_range : float, optional
        Temperature range over which phase change occurs (default: 2.0°C)
        Larger values = more gradual phase change
    
    Returns:
    --------
    float or pd.Series
        Phase fraction (0.0 = fully solid, 1.0 = fully liquid)
    """
    # Calculate distance from phase change temperature
    temp_diff = temp - phase_change_temp
    
    # Use sigmoid function for smooth transition
    # When temp << phase_change_temp: phase_fraction ≈ 0 (solid)
    # When temp >> phase_change_temp: phase_fraction ≈ 1 (liquid)
    # Transition occurs over phase_change_range
    phase_fraction = 1.0 / (1.0 + np.exp(-temp_diff / (phase_change_range / 4.0)))
    
    return phase_fraction


def calculate_effective_heat_capacity(
    temp: Union[float, pd.Series],
    phase_change_temp: float,
    sensible_heat_capacity: float,
    latent_heat_capacity: float,
    phase_change_range: float = 2.0,
) -> Union[float, pd.Series]:
    """
    Calculate effective heat capacity considering PCM phase change.
    
    Effective heat capacity increases during phase change due to latent heat.
    
    Parameters:
    -----------
    temp : float or pd.Series
        Current temperature in °C
    phase_change_temp : float
        Nominal phase change temperature in °C
    sensible_heat_capacity : float
        Sensible heat capacity (J/K) - constant component
    latent_heat_capacity : float
        Latent heat capacity (J/K) - phase change component
    phase_change_range : float, optional
        Temperature range over which phase change occurs (default: 2.0°C)
    
    Returns:
    --------
    float or pd.Series
        Effective heat capacity (J/K)
    """
    # Calculate phase fraction
    phase_fraction = calculate_phase_fraction(temp, phase_change_temp, phase_change_range)
    
    # Calculate rate of phase change (derivative of phase fraction)
    # This determines how much latent heat is being absorbed/released
    temp_diff = temp - phase_change_temp
    d_phase_dT = (
        np.exp(-temp_diff / (phase_change_range / 4.0)) /
        (phase_change_range / 4.0) /
        (1.0 + np.exp(-temp_diff / (phase_change_range / 4.0)))**2
    )
    
    # Effective heat capacity = sensible + latent contribution
    # Latent contribution is maximum when phase fraction is changing fastest
    effective_heat_capacity = (
        sensible_heat_capacity + 
        latent_heat_capacity * d_phase_dT * phase_change_range
    )
    
    return effective_heat_capacity


def calculate_pcm_thermal_buffering(
    temp: Union[float, pd.Series],
    temp_history: Optional[pd.Series],
    phase_change_temp: float,
    latent_heat_capacity: float,
    pcm_mass: float,
    time_step_sec: float = 900,
    phase_change_range: float = 2.0,
) -> Tuple[Union[float, pd.Series], Union[float, pd.Series]]:
    """
    Calculate PCM thermal buffering effect.
    
    PCM absorbs/releases heat during phase change, providing thermal buffering.
    This reduces the effective cooling load needed.
    
    Parameters:
    -----------
    temp : float or pd.Series
        Current temperature in °C
    temp_history : pd.Series, optional
        Temperature history for calculating rate of change
    phase_change_temp : float
        Nominal phase change temperature in °C
    latent_heat_capacity : float
        Latent heat capacity in J/kg
    pcm_mass : float
        Mass of PCM in kg
    time_step_sec : float, optional
        Time step in seconds (default: 900 = 15 minutes)
    phase_change_range : float, optional
        Temperature range over which phase change occurs (default: 2.0°C)
    
    Returns:
    --------
    Tuple[float or pd.Series, float or pd.Series]
        (buffering_effect_kW, phase_fraction)
        - buffering_effect_kW: Thermal buffering effect in kW (positive = cooling benefit)
        - phase_fraction: Current phase fraction (0-1)
    """
    # Calculate current phase fraction
    phase_fraction = calculate_phase_fraction(temp, phase_change_temp, phase_change_range)
    
    # Calculate buffering effect based on temperature change rate
    if temp_history is not None and len(temp_history) > 1:
        # Calculate temperature change rate
        temp_change = temp - temp_history.iloc[-1] if isinstance(temp_history, pd.Series) else 0
        temp_change_rate = temp_change / time_step_sec  # °C/s
        
        # Calculate phase fraction change
        if isinstance(temp_history, pd.Series) and len(temp_history) > 0:
            prev_temp = temp_history.iloc[-1]
            prev_phase_fraction = calculate_phase_fraction(prev_temp, phase_change_temp, phase_change_range)
            phase_fraction_change = phase_fraction - prev_phase_fraction
        else:
            phase_fraction_change = 0
    else:
        temp_change_rate = 0
        phase_fraction_change = 0
    
    # Buffering effect: PCM absorbs/releases heat during phase change
    # When cooling (temp decreasing): PCM releases heat (reduces cooling needed)
    # When heating (temp increasing): PCM absorbs heat (reduces heating needed)
    # For cooling systems: negative temp_change_rate → positive buffering (cooling benefit)
    
    # Calculate latent heat flux
    # Latent heat = mass × latent_heat_capacity × phase_fraction_change
    if isinstance(phase_fraction_change, pd.Series):
        latent_heat_flux_j = latent_heat_capacity * pcm_mass * phase_fraction_change.abs()
    else:
        latent_heat_flux_j = latent_heat_capacity * pcm_mass * abs(phase_fraction_change)
    
    # Convert to power (kW)
    # Power = energy / time
    buffering_effect_kW = latent_heat_flux_j / (time_step_sec * 1000)  # Convert J to kJ, then to kW
    
    # Sign: positive when PCM provides cooling benefit
    # Handle both scalar and Series cases
    if isinstance(temp_change_rate, pd.Series):
        # For Series: use vectorized operation
        buffering_effect_kW = np.where(
            temp_change_rate < 0,  # Cooling
            buffering_effect_kW,    # Positive = reduces cooling needed
            -buffering_effect_kW     # Negative = reduces heating needed
        )
    else:
        # For scalar
        if temp_change_rate < 0:  # Cooling
            buffering_effect_kW = buffering_effect_kW  # Positive = reduces cooling needed
        else:  # Heating
            buffering_effect_kW = -buffering_effect_kW  # Negative = reduces heating needed
    
    return buffering_effect_kW, phase_fraction


def calculate_enhanced_pcm_cooling_benefit(
    temp: Union[float, pd.Series],
    temp_history: Optional[pd.Series],
    phase_change_temp: float,
    latent_heat_capacity: float,
    pcm_mass: float,
    time_step_sec: float = 900,
    phase_change_range: float = 2.0,
    proximity_factor: float = 1.0,
    base_benefit_factor: float = 0.1,
) -> Union[float, pd.Series]:
    """
    Calculate enhanced PCM cooling benefit considering continuous phase change.
    
    This replaces the simple discrete phase transition model with a continuous model
    that accounts for:
    1. Gradual phase change over temperature range
    2. Thermal buffering effects
    3. Proximity to phase change temperature
    
    Parameters:
    -----------
    temp : float or pd.Series
        Current temperature in °C
    temp_history : pd.Series, optional
        Temperature history for calculating rate of change
    phase_change_temp : float
        Nominal phase change temperature in °C
    latent_heat_capacity : float
        Latent heat capacity in J/kg
    pcm_mass : float
        Mass of PCM in kg
    time_step_sec : float, optional
        Time step in seconds (default: 900 = 15 minutes)
    phase_change_range : float, optional
        Temperature range over which phase change occurs (default: 2.0°C)
    proximity_factor : float, optional
        Factor for proximity effect (default: 1.0)
        Higher values = more benefit when near phase change temp
    
    Returns:
    --------
    float or pd.Series
        PCM cooling benefit in kW (positive = reduces cooling needed)
    """
    # Calculate thermal buffering effect
    buffering_effect, phase_fraction = calculate_pcm_thermal_buffering(
        temp=temp,
        temp_history=temp_history,
        phase_change_temp=phase_change_temp,
        latent_heat_capacity=latent_heat_capacity,
        pcm_mass=pcm_mass,
        time_step_sec=time_step_sec,
        phase_change_range=phase_change_range,
    )
    
    # Calculate proximity effect
    # PCM is more effective when operating near phase change temperature
    temp_diff = np.abs(temp - phase_change_temp)
    proximity_effect = np.exp(-temp_diff / (phase_change_range * proximity_factor))
    
    # Total cooling benefit = buffering effect × proximity effect
    # Proximity effect scales the buffering benefit
    cooling_benefit = buffering_effect * (1.0 + proximity_effect)
    
    # Also add a base benefit when near phase change temperature
    # This accounts for improved COP near phase change temp
    base_benefit = (
        proximity_effect * 
        latent_heat_capacity * 
        pcm_mass / 
        (3600 * 1000)  # Convert J to kW (assuming 1 hour time constant)
    ) * base_benefit_factor  # Configurable base benefit factor
    
    total_benefit = cooling_benefit + base_benefit
    
    return total_benefit

