"""
Main analysis tool for phase-change cooling systems.

This tool performs potential analysis for phase-change cooling systems,
calculating energy savings, cost optimization, and generating reports.
"""

import logging
import os
from typing import Final, Union, Optional
import numpy as np
import pandas as pd

from analysis.phase_change_models import (
    estimate_electric_power_phase_change_cooling,
    calculate_phase_change_cooling_power,
)
from analysis.schedule_creators import (
    create_price_like_schedule,
    create_smoothed_price_schedule,
    create_constant_schedule,
    create_altering_step_schedule,
)
from analysis.cost_aware_schedule_creator import (
    create_cost_aware_schedule,
    create_constrained_price_schedule,
)
from analysis.emission_schedule_creators import (
    create_emission_like_schedule,
    create_smoothed_emission_schedule,
)
from analysis.pv_self_consumption_optimizer import optimize_pv_self_consumption
from utils.data_processing import (
    convert_power_to_energy,
    determine_surplus_phases,
    fix_index_and_interpolate,
)
from utils.plotting import PhaseChangePlotter


def _convert_surplus_phases_to_daily_format(
    df: pd.DataFrame,
    surplus_phases: list,
) -> list:
    """
    Convert surplus phases from list of (start, end) tuples to daily format.
    
    Groups surplus phases by day to match the optimizer's expected format.
    
    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame with datetime index
    surplus_phases : list
        List of (start_index, end_index) tuples from determine_surplus_phases
    
    Returns:
    --------
    list
        List of surplus phases grouped by day
    """
    if len(surplus_phases) == 0:
        return []
    
    # Group by date
    daily_phases = {}
    for start_idx, end_idx in surplus_phases:
        # Get all dates in this phase
        phase_dates = pd.date_range(start=start_idx, end=end_idx, freq=df.index.freq or "15min")
        unique_dates = set(phase_dates.date)
        
        for date in unique_dates:
            if date not in daily_phases:
                daily_phases[date] = []
            
            # Get the part of this phase that falls on this date
            day_start = max(start_idx, pd.Timestamp(date))
            day_end = min(end_idx, pd.Timestamp(date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))
            
            if day_start <= day_end:
                daily_phases[date].append((day_start, day_end))
    
    # Convert to list ordered by date, merging phases on same day
    dates = sorted(daily_phases.keys())
    result = []
    
    for date in dates:
        phases_for_day = daily_phases[date]
        if len(phases_for_day) > 0:
            # Merge overlapping phases on the same day
            merged = _merge_overlapping_phases(phases_for_day)
            result.append(merged)
        else:
            result.append([])
    
    return result


def _merge_overlapping_phases(phases: list) -> pd.DatetimeIndex:
    """
    Merge overlapping phases into a single DatetimeIndex.
    
    Parameters:
    -----------
    phases : list
        List of (start, end) tuples
    
    Returns:
    --------
    pd.DatetimeIndex
        Merged DatetimeIndex covering all phases
    """
    if len(phases) == 0:
        return pd.DatetimeIndex([])
    
    # Sort by start time
    sorted_phases = sorted(phases, key=lambda x: x[0])
    
    # Merge overlapping intervals
    merged = []
    current_start, current_end = sorted_phases[0]
    
    for start, end in sorted_phases[1:]:
        if start <= current_end:
            # Overlapping, extend current
            current_end = max(current_end, end)
        else:
            # Not overlapping, save current and start new
            merged.append((current_start, current_end))
            current_start, current_end = start, end
    
    merged.append((current_start, current_end))
    
    # Convert to DatetimeIndex
    all_timestamps = []
    for start, end in merged:
        # Create range with 15-minute frequency (or use original frequency)
        timestamps = pd.date_range(start=start, end=end, freq="15min")
        all_timestamps.extend(timestamps)
    
    return pd.DatetimeIndex(all_timestamps).drop_duplicates().sort_values()


# Column name constants
COOLING_POWER_AFTER_OPTIMIZATION_COL: Final = "Cooling Power After Optimization"
SPOTMARKET_ENERGY_PRICE_IN_CT_PER_KWH: Final = "Spot Market Price (ct/kWh)"
ENERGY_PRICE_BEFORE_OPTIMIZATION_IN_CT_PER_KWH: Final = "Energy Price Before (ct/kWh)"
EVU_AFTER_OPTIMIZATION_COL: Final = "EVU Meter After Optimization"
SITE_CONSUMPTION_BEFORE_OPTIMIZATION_COL: Final = "Site Consumption Before"
SITE_CONSUMPTION_AFTER_OPTIMIZATION_COL: Final = "Site Consumption After"
GRID_POWER_BEFORE_OPTIMIZATION_COL: Final = "Grid Power Before"
GRID_POWER_AFTER_OPTIMIZATION_COL: Final = "Grid Power After"
SCHEDULE_TEMP_COL: Final = "Temperature Schedule"
MIN_TEMP_ALLOWED_COL: Final = "Min Temp Allowed"
MAX_TEMP_ALLOWED_COL: Final = "Max Temp Allowed"
DFLT_INDOOR_TEMP_COL: Final = "Default Indoor Temp"


def run_phase_change_analysis(
    data: Union[str, pd.DataFrame],
    evu_col: str,
    cooling_power_col: str,
    spotmarket_energy_price_in_euro_per_mwh_col: Optional[str] = None,
    const_energy_price_in_euro_per_mwh_col: Optional[str] = None,
    power_price_in_euro_per_kw: Union[int, float] = 0.0,
    cop: Union[int, float] = 2.8,
    schedule_temp_type: str = "price_like_schedule",
    dflt_indoor_temp: Union[int, float] = -20.0,
    min_temp_allowed: Union[int, float] = -25.0,
    max_temp_allowed: Union[int, float] = -15.0,
    mapping_of_walls_properties: Optional[dict] = None,
    mapping_of_content_properties: Optional[dict] = None,
    cooling_ramp_slope_in_k_per_h: Union[int, float] = -1.0,
    warming_ramp_slope_in_k_per_h: Union[int, float] = 2.0,
    report_directory: str = "reports",
    # Phase-change specific parameters
    latent_heat_capacity_in_j_per_kg: Union[int, float] = 200000,  # Typical for water/ice
    pcm_mass_in_kg: Union[int, float] = 0,  # Set to 0 if no PCM
    phase_change_temp_in_c: Union[int, float] = 0,  # Phase change temperature
    latent_heat_factor: Union[int, float] = 1.0,  # Latent heat efficiency factor
    # Optional parameters
    nominal_cooling_power: Optional[Union[int, float]] = None,
    pv_power_col: Optional[str] = None,
    show_plots: bool = False,
    alpha: float = 0.55,
    system_group_name: Optional[str] = None,  # Name of system group for plot titles
    # Emission optimization parameters
    emission_factor_col: Optional[str] = None,  # Column name for emission factors
    optimization_mode: str = "cost",  # "cost" or "emission"
    smoothing_window_hours: Optional[float] = None,  # For smoothed schedules
) -> None:
    """
    Execute phase-change cooling potential analysis.
    
    Parameters:
    -----------
    data : str or pd.DataFrame
        Input data as file path or DataFrame
    evu_col : str
        Column name for EVU meter readings
    cooling_power_col : str
        Column name for cooling power data
    spotmarket_energy_price_in_euro_per_mwh_col : str
        Column name for spot market energy prices
    const_energy_price_in_euro_per_mwh_col : str or None
        Column name for constant energy prices (if applicable)
    power_price_in_euro_per_kw : float
        Power price in euros per kilowatt
    cop : float
        Coefficient of Performance - dimensionless ratio (cooling capacity in kW / electrical power in kW)
        Typical range: 2.0 - 6.0 for commercial cooling systems
    schedule_temp_type : str
        Type of temperature schedule ("price_like_schedule", "constant at X", "altering_step_schedule")
    dflt_indoor_temp : float
        Default indoor temperature in degrees Celsius
    min_temp_allowed : float
        Minimum allowed temperature in degrees Celsius
    min_temp_allowed : float
        Maximum allowed temperature in degrees Celsius
    mapping_of_walls_properties : dict
        Properties of walls: {"walls": {"area": value, "heat_transfer_coef": value}}
    mapping_of_content_properties : dict
        Properties of room contents: {"content": {"mass": value, "specific_heat_capacity": value}}
    cooling_ramp_slope_in_k_per_h : float
        Cooling ramp slope in K/h (negative value)
    warming_ramp_slope_in_k_per_h : float
        Warming ramp slope in K/h (positive value)
    report_directory : str
        Directory path for saving reports and plots
    latent_heat_capacity_in_j_per_kg : float
        Latent heat capacity of PCM in J/kg
    pcm_mass_in_kg : float
        Mass of phase-change material in kg
    phase_change_temp_in_c : float
        Temperature at which phase change occurs
    latent_heat_factor : float
        Factor accounting for latent heat benefits
    nominal_cooling_power : float, optional
        Nominal cooling power of the system
    pv_power_col : str, optional
        Column name for PV power data
    show_plots : bool
        Whether to display plots
    alpha : float
        Transparency factor for plots
    """
    # Parse data
    if isinstance(data, str):
        df = pd.read_csv(data, index_col=0, parse_dates=True)
    else:
        df = data.copy()
    
    # Ensure datetime index
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    
    # Create report directory
    os.makedirs(report_directory, exist_ok=True)
    
    # Convert energy prices (only if provided)
    if spotmarket_energy_price_in_euro_per_mwh_col:
        df[SPOTMARKET_ENERGY_PRICE_IN_CT_PER_KWH] = (
            df[spotmarket_energy_price_in_euro_per_mwh_col] * 0.1  # €/MWh to ct/kWh
        )
        
        energy_price_before_col = (
            const_energy_price_in_euro_per_mwh_col 
            if const_energy_price_in_euro_per_mwh_col 
            else spotmarket_energy_price_in_euro_per_mwh_col
        )
        df[ENERGY_PRICE_BEFORE_OPTIMIZATION_IN_CT_PER_KWH] = df[energy_price_before_col] * 0.1
    else:
        # For emission optimization, we may not have prices
        df[SPOTMARKET_ENERGY_PRICE_IN_CT_PER_KWH] = 0.0
        df[ENERGY_PRICE_BEFORE_OPTIMIZATION_IN_CT_PER_KWH] = 0.0
    
    # Set temperature constraints
    df[MIN_TEMP_ALLOWED_COL] = min_temp_allowed
    df[MAX_TEMP_ALLOWED_COL] = max_temp_allowed
    df[DFLT_INDOOR_TEMP_COL] = dflt_indoor_temp
    
    # Calculate overall heat transfer coefficient and heat capacity
    overall_heat_transfer_coef = sum(
        props["area"] * props["heat_transfer_coef"]
        for props in mapping_of_walls_properties.values()
    )
    
    overall_heat_capacity = sum(
        props["mass"] * props["specific_heat_capacity"]
        for props in mapping_of_content_properties.values()
    )
    
    # Calculate site consumption and grid power
    # IMPORTANT: The evu_col parameter contains GROSS consumption (Standortverbrauch)
    # We rename it to Standortverbrauch for clarity, then calculate EVU Meter as net
    
    # Rename raw data column to Standortverbrauch (gross consumption)
    df["Standortverbrauch"] = df[evu_col]
    
    if pv_power_col and pv_power_col in df.columns:
        # Site consumption is the gross consumption (Standortverbrauch)
        df[SITE_CONSUMPTION_BEFORE_OPTIMIZATION_COL] = df["Standortverbrauch"]
        
        # Calculate EVU Meter as NET (grid exchange after PV offset)
        # This is what "EVU Meter" means - net grid exchange
        df["EVU Meter"] = df["Standortverbrauch"] - df[pv_power_col]
        
        # Grid power is the positive part of EVU Meter (only when drawing from grid)
        df[GRID_POWER_BEFORE_OPTIMIZATION_COL] = df["EVU Meter"].clip(lower=0)
    else:
        # No PV data, EVU Meter equals Standortverbrauch (no offset)
        df[SITE_CONSUMPTION_BEFORE_OPTIMIZATION_COL] = df["Standortverbrauch"]
        df["EVU Meter"] = df["Standortverbrauch"]
        df[GRID_POWER_BEFORE_OPTIMIZATION_COL] = df["EVU Meter"].clip(lower=0)
    
    # Determine surplus phases if PV available
    surplus_phases = []
    if pv_power_col:
        surplus_phases = determine_surplus_phases(
            df, pv_power_col, SITE_CONSUMPTION_BEFORE_OPTIMIZATION_COL
        )
    
    # Get system-specific max deviation if available
    max_deviation = None
    if system_group_name:
        try:
            from config import (
                MAX_TEMP_DEVIATION_FROM_DEFAULT_PLUSKUEHLUNG,
                MAX_TEMP_DEVIATION_FROM_DEFAULT_TIEFKUEHLUNG,
                MAX_TEMP_DEVIATION_FROM_DEFAULT_DEFAULT,
            )
            if "Pluskühlung" in system_group_name or "pluskühlung" in system_group_name.lower():
                max_deviation = MAX_TEMP_DEVIATION_FROM_DEFAULT_PLUSKUEHLUNG
            elif "Tiefkühlung" in system_group_name or "tiefkühlung" in system_group_name.lower():
                max_deviation = MAX_TEMP_DEVIATION_FROM_DEFAULT_TIEFKUEHLUNG
            else:
                max_deviation = MAX_TEMP_DEVIATION_FROM_DEFAULT_DEFAULT
        except ImportError:
            pass
    
    # Create temperature schedule
    if schedule_temp_type == "price_like_schedule":
        if spotmarket_energy_price_in_euro_per_mwh_col is None:
            raise ValueError("spotmarket_energy_price_in_euro_per_mwh_col is required for price_like_schedule")
        # Use constrained schedule if max deviation is set
        if max_deviation is not None:
            df[SCHEDULE_TEMP_COL] = create_constrained_price_schedule(
                df=df,
                spotmarket_energy_price_col=spotmarket_energy_price_in_euro_per_mwh_col,
                min_temp_allowed_col=MIN_TEMP_ALLOWED_COL,
                max_temp_allowed_col=MAX_TEMP_ALLOWED_COL,
                dflt_indoor_temp_col=DFLT_INDOOR_TEMP_COL,
                ramp_slope_in_k_per_h=abs(cooling_ramp_slope_in_k_per_h),
                max_deviation_from_default=max_deviation,
                phase_change_temp=phase_change_temp_in_c if pcm_mass_in_kg > 0 else None,
            )
        else:
            df[SCHEDULE_TEMP_COL] = create_price_like_schedule(
                df=df,
                spotmarket_energy_price_col=spotmarket_energy_price_in_euro_per_mwh_col,
                min_temp_allowed_col=MIN_TEMP_ALLOWED_COL,
                max_temp_allowed_col=MAX_TEMP_ALLOWED_COL,
                ramp_slope_in_k_per_h=abs(cooling_ramp_slope_in_k_per_h),
                phase_change_temp=phase_change_temp_in_c if pcm_mass_in_kg > 0 else None,
            )
    elif schedule_temp_type == "cost_aware_schedule":
        if spotmarket_energy_price_in_euro_per_mwh_col is None:
            raise ValueError("spotmarket_energy_price_in_euro_per_mwh_col is required for cost_aware_schedule")
        df[SCHEDULE_TEMP_COL] = create_cost_aware_schedule(
            df=df,
            spotmarket_energy_price_col=spotmarket_energy_price_in_euro_per_mwh_col,
            min_temp_allowed_col=MIN_TEMP_ALLOWED_COL,
            max_temp_allowed_col=MAX_TEMP_ALLOWED_COL,
            dflt_indoor_temp_col=DFLT_INDOOR_TEMP_COL,
            ramp_slope_in_k_per_h=abs(cooling_ramp_slope_in_k_per_h),
            overall_heat_transfer_coef_in_w_per_k=overall_heat_transfer_coef,
            cop=cop,
            max_temp_deviation_from_default=max_deviation,
            phase_change_temp=phase_change_temp_in_c if pcm_mass_in_kg > 0 else None,
        )
    elif schedule_temp_type == "constrained_price_schedule":
        if spotmarket_energy_price_in_euro_per_mwh_col is None:
            raise ValueError("spotmarket_energy_price_in_euro_per_mwh_col is required for constrained_price_schedule")
        df[SCHEDULE_TEMP_COL] = create_constrained_price_schedule(
            df=df,
            spotmarket_energy_price_col=spotmarket_energy_price_in_euro_per_mwh_col,
            min_temp_allowed_col=MIN_TEMP_ALLOWED_COL,
            max_temp_allowed_col=MAX_TEMP_ALLOWED_COL,
            dflt_indoor_temp_col=DFLT_INDOOR_TEMP_COL,
            ramp_slope_in_k_per_h=abs(cooling_ramp_slope_in_k_per_h),
            max_deviation_from_default=max_deviation if max_deviation is not None else 2.0,
            phase_change_temp=phase_change_temp_in_c if pcm_mass_in_kg > 0 else None,
        )
    elif schedule_temp_type.startswith("constant at"):
        constant_temp = float(schedule_temp_type.replace("constant at", "").strip())
        df[SCHEDULE_TEMP_COL] = create_constant_schedule(df, constant_temp)
    elif schedule_temp_type == "smoothed_price_schedule":
        df[SCHEDULE_TEMP_COL] = create_smoothed_price_schedule(
            df=df,
            spotmarket_energy_price_col=spotmarket_energy_price_in_euro_per_mwh_col,
            min_temp_allowed_col=MIN_TEMP_ALLOWED_COL,
            max_temp_allowed_col=MAX_TEMP_ALLOWED_COL,
            ramp_slope_in_k_per_h=abs(cooling_ramp_slope_in_k_per_h),
            smoothing_window_hours=smoothing_window_hours if smoothing_window_hours is not None else 4.0,
            phase_change_temp=phase_change_temp_in_c if pcm_mass_in_kg > 0 else None,
        )
    elif schedule_temp_type == "emission_like_schedule":
        if emission_factor_col is None:
            raise ValueError("emission_factor_col is required for emission_like_schedule")
        df[SCHEDULE_TEMP_COL] = create_emission_like_schedule(
            df=df,
            emission_factor_col=emission_factor_col,
            min_temp_allowed_col=MIN_TEMP_ALLOWED_COL,
            max_temp_allowed_col=MAX_TEMP_ALLOWED_COL,
            ramp_slope_in_k_per_h=abs(cooling_ramp_slope_in_k_per_h),
            phase_change_temp=phase_change_temp_in_c if pcm_mass_in_kg > 0 else None,
        )
    elif schedule_temp_type == "smoothed_emission_schedule":
        if emission_factor_col is None:
            raise ValueError("emission_factor_col is required for smoothed_emission_schedule")
        df[SCHEDULE_TEMP_COL] = create_smoothed_emission_schedule(
            df=df,
            emission_factor_col=emission_factor_col,
            min_temp_allowed_col=MIN_TEMP_ALLOWED_COL,
            max_temp_allowed_col=MAX_TEMP_ALLOWED_COL,
            ramp_slope_in_k_per_h=abs(cooling_ramp_slope_in_k_per_h),
            smoothing_window_hours=smoothing_window_hours if smoothing_window_hours is not None else 4.0,
            phase_change_temp=phase_change_temp_in_c if pcm_mass_in_kg > 0 else None,
        )
    elif schedule_temp_type == "altering_step_schedule":
        if spotmarket_energy_price_in_euro_per_mwh_col is None:
            raise ValueError("spotmarket_energy_price_in_euro_per_mwh_col is required for altering_step_schedule")
        df[SCHEDULE_TEMP_COL] = create_altering_step_schedule(
            df=df,
            spotmarket_energy_price_col=spotmarket_energy_price_in_euro_per_mwh_col,
            dflt_temp_allowed_col=DFLT_INDOOR_TEMP_COL,
            min_temp_allowed_col=MIN_TEMP_ALLOWED_COL,
            max_temp_allowed_col=MAX_TEMP_ALLOWED_COL,
            cooling_ramp_slope_in_k_per_h=cooling_ramp_slope_in_k_per_h,
            warming_ramp_slope_in_k_per_h=warming_ramp_slope_in_k_per_h,
            phase_change_temp=phase_change_temp_in_c if pcm_mass_in_kg > 0 else None,
        )
    else:
        raise ValueError(f"Unknown schedule type: {schedule_temp_type}")
    
    # Optimize for PV self-consumption if PV available and surplus phases exist
    if pv_power_col and len(surplus_phases) > 0:
        # Convert surplus phases to format expected by optimizer (grouped by day)
        surplus_phases_by_day = _convert_surplus_phases_to_daily_format(df, surplus_phases)
        
        # Apply PV self-consumption optimization
        df[SCHEDULE_TEMP_COL] = optimize_pv_self_consumption(
            schedule_temp=df[SCHEDULE_TEMP_COL],
            expected_surplus_phases=surplus_phases_by_day,
            shortest_surplus_phase_allowed="1h",
            cooling_ramp_slope_in_k_per_h=cooling_ramp_slope_in_k_per_h,
            warming_ramp_slope_in_k_per_h=warming_ramp_slope_in_k_per_h,
            min_temp_allowed=min_temp_allowed,
            max_temp_allowed=max_temp_allowed,
            phase_change_temp=phase_change_temp_in_c if pcm_mass_in_kg > 0 else None,
        )
    
    # Calculate modified cooling power
    df[COOLING_POWER_AFTER_OPTIMIZATION_COL] = calculate_phase_change_cooling_power(
        df=df,
        cooling_power_col=cooling_power_col,
        schedule_temp_col=SCHEDULE_TEMP_COL,
        dflt_indoor_temp_col=DFLT_INDOOR_TEMP_COL,
        overall_heat_transfer_coef_in_w_per_k=overall_heat_transfer_coef,
        overall_heat_capacity_in_j_per_k=overall_heat_capacity,
        latent_heat_capacity_in_j_per_kg=latent_heat_capacity_in_j_per_kg,
        pcm_mass_in_kg=pcm_mass_in_kg,
        phase_change_temp_in_c=phase_change_temp_in_c,
        cop=cop,
        latent_heat_factor=latent_heat_factor,
    )
    
    # Calculate EVU after optimization (gross consumption)
    df[EVU_AFTER_OPTIMIZATION_COL] = (
        df[evu_col] 
        - df[cooling_power_col] 
        + df[COOLING_POWER_AFTER_OPTIMIZATION_COL]
    )
    
    # Calculate site consumption and grid power after optimization
    # Site consumption = gross EVU (total consumption)
    df[SITE_CONSUMPTION_AFTER_OPTIMIZATION_COL] = df[EVU_AFTER_OPTIMIZATION_COL]
    
    # Calculate EVU Meter After Optimization (net grid exchange)
    # EVU_AFTER_OPTIMIZATION_COL is gross consumption after optimization
    if pv_power_col and pv_power_col in df.columns:
        df["EVU Meter After Optimization"] = (
            df[EVU_AFTER_OPTIMIZATION_COL] - df[pv_power_col]
        )
        df[GRID_POWER_AFTER_OPTIMIZATION_COL] = df["EVU Meter After Optimization"].clip(lower=0)
    else:
        df["EVU Meter After Optimization"] = df[EVU_AFTER_OPTIMIZATION_COL]
        df[GRID_POWER_AFTER_OPTIMIZATION_COL] = df["EVU Meter After Optimization"].clip(lower=0)
    
    # Calculate hourly costs and cumulative energy consumption for plotting
    time_step_hours = (df.index[1] - df.index[0]).total_seconds() / 3600
    df["Cost Before (€/h)"] = (
        df[GRID_POWER_BEFORE_OPTIMIZATION_COL] * time_step_hours 
        * df[ENERGY_PRICE_BEFORE_OPTIMIZATION_IN_CT_PER_KWH] / 100
    )
    df["Cost After (€/h)"] = (
        df[GRID_POWER_AFTER_OPTIMIZATION_COL] * time_step_hours 
        * df[SPOTMARKET_ENERGY_PRICE_IN_CT_PER_KWH] / 100
    )
    df["Energy Consumption Before (kWh)"] = (
        convert_power_to_energy(df[GRID_POWER_BEFORE_OPTIMIZATION_COL])
    )
    df["Energy Consumption After (kWh)"] = (
        convert_power_to_energy(df[GRID_POWER_AFTER_OPTIMIZATION_COL])
    )
    
    # Calculate emissions if emission factors are available
    if emission_factor_col and emission_factor_col in df.columns:
        # Emissions = power (kW) * time (h) * emission_factor (g CO2/kWh) / 1000 = kg CO2
        # For hourly emissions: power * time_step_hours * emission_factor / 1000
        df["Emissions Before (kg CO2/h)"] = (
            df[GRID_POWER_BEFORE_OPTIMIZATION_COL] * time_step_hours 
            * df[emission_factor_col] / 1000.0  # Convert g CO2/kWh to kg CO2
        )
        df["Emissions After (kg CO2/h)"] = (
            df[GRID_POWER_AFTER_OPTIMIZATION_COL] * time_step_hours 
            * df[emission_factor_col] / 1000.0  # Convert g CO2/kWh to kg CO2
        )
        # Cumulative emissions
        df["Cumulative Emissions Before (kg CO2)"] = (
            convert_power_to_energy(df[GRID_POWER_BEFORE_OPTIMIZATION_COL] * df[emission_factor_col] / 1000.0)
        )
        df["Cumulative Emissions After (kg CO2)"] = (
            convert_power_to_energy(df[GRID_POWER_AFTER_OPTIMIZATION_COL] * df[emission_factor_col] / 1000.0)
        )
    
    # Validate temperature schedule by simulating resulting temperatures
    from analysis.temperature_validation import validate_temperature_schedule, save_validation_report
    
    # Get system-specific validation tolerance
    validation_tolerance = 1.0  # Default
    if system_group_name:
        try:
            from config import (
                VALIDATION_TOLERANCE_PLUSKUEHLUNG_C,
                VALIDATION_TOLERANCE_TIEFKUEHLUNG_C,
                VALIDATION_TOLERANCE_DEFAULT_C,
            )
            if "Pluskühlung" in system_group_name or "pluskühlung" in system_group_name.lower():
                validation_tolerance = VALIDATION_TOLERANCE_PLUSKUEHLUNG_C
            elif "Tiefkühlung" in system_group_name or "tiefkühlung" in system_group_name.lower():
                validation_tolerance = VALIDATION_TOLERANCE_TIEFKUEHLUNG_C
            else:
                validation_tolerance = VALIDATION_TOLERANCE_DEFAULT_C
        except ImportError:
            # Fallback to default if config not available
            pass
    
    validation_results = validate_temperature_schedule(
        df=df,
        target_temp_col=SCHEDULE_TEMP_COL,
        cooling_power_col=COOLING_POWER_AFTER_OPTIMIZATION_COL,
        initial_temp=dflt_indoor_temp,
        overall_heat_transfer_coef_in_w_per_k=overall_heat_transfer_coef,
        overall_heat_capacity_in_j_per_k=overall_heat_capacity,
        cop=cop,
        latent_heat_factor=latent_heat_factor,
        baseline_cooling_power_col=cooling_power_col,
        dflt_indoor_temp=dflt_indoor_temp,
        tolerance=validation_tolerance,  # System-specific tolerance
    )
    
    # Add simulated temperature to DataFrame for plotting
    df["Simulated Temperature"] = validation_results['simulated_temperature']
    df["Temperature Error"] = validation_results['errors']
    
    # Save validation report
    save_validation_report(
        validation_results=validation_results,
        report_directory=report_directory,
        system_group_name=system_group_name,
    )
    
    # Print validation summary
    print(f"\n{'='*60}")
    print("TEMPERATURE VALIDATION RESULTS")
    print(f"{'='*60}")
    print(f"Mean Absolute Error: {validation_results['mean_abs_error']:.3f} C")
    print(f"Max Error: {validation_results['max_error']:.3f} C")
    print(f"RMSE: {validation_results['rmse']:.3f} C")
    print(f"Within Tolerance ({validation_tolerance}C): {validation_results['within_tolerance']:.1f}%")
    if validation_results['validation_passed']:
        print("[OK] Validation PASSED - Model is accurate")
    else:
        print("[WARNING] Validation FAILED - Model may need parameter adjustment")
        print("  Consider reviewing parameter values (see PARAMETER_VERIFICATION_GUIDE.md)")
    print(f"{'='*60}\n")
    
    # Calculate savings
    savings = _calculate_savings(
        df=df,
        grid_power_before_col=GRID_POWER_BEFORE_OPTIMIZATION_COL,
        grid_power_after_col=GRID_POWER_AFTER_OPTIMIZATION_COL,
        energy_price_before_col=ENERGY_PRICE_BEFORE_OPTIMIZATION_IN_CT_PER_KWH,
        energy_price_after_col=SPOTMARKET_ENERGY_PRICE_IN_CT_PER_KWH,
        power_price_in_euro_per_kw=power_price_in_euro_per_kw,
        report_directory=report_directory,
    )
    
    # Generate plots
    _generate_plots(
        df=df,
        evu_col=evu_col,
        cooling_power_before_col=cooling_power_col,
        cooling_power_after_col=COOLING_POWER_AFTER_OPTIMIZATION_COL,
        grid_power_before_col=GRID_POWER_BEFORE_OPTIMIZATION_COL,
        grid_power_after_col=GRID_POWER_AFTER_OPTIMIZATION_COL,
        energy_price_col=SPOTMARKET_ENERGY_PRICE_IN_CT_PER_KWH,
        schedule_temp_col=SCHEDULE_TEMP_COL,
        pv_power_col=pv_power_col,
        report_directory=report_directory,
        show_plots=show_plots,
        savings=savings,
        system_group_name=system_group_name,
        optimization_mode=optimization_mode,
        emission_factor_col=emission_factor_col,
    )
    
    # Save results
    results_path = os.path.join(report_directory, "results.xlsx")
    with pd.ExcelWriter(results_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Results")
    
    print(f"\nAnalysis complete! Results saved to: {report_directory}")
    print(f"Grid savings: {savings['relative_grid_savings']:.1f}%")
    print(f"Absolute savings: {savings['absolute_savings']:.2f} €")


def _calculate_savings(
    df: pd.DataFrame,
    grid_power_before_col: str,
    grid_power_after_col: str,
    energy_price_before_col: str,
    energy_price_after_col: str,
    power_price_in_euro_per_kw: float,
    report_directory: str,
) -> dict:
    """Calculate energy and cost savings."""
    # Convert power to energy
    time_step_hours = (df.index[1] - df.index[0]).total_seconds() / 3600
    
    grid_energy_before = convert_power_to_energy(df[grid_power_before_col])
    grid_energy_after = convert_power_to_energy(df[grid_power_after_col])
    
    # Calculate costs (simplified: using average price per hour)
    grid_costs_before = (
        grid_energy_before.diff().fillna(0) 
        * df[energy_price_before_col] 
        / 100  # ct to €
    ).sum()
    
    grid_costs_after = (
        grid_energy_after.diff().fillna(0) 
        * df[energy_price_after_col] 
        / 100  # ct to €
    ).sum()
    
    absolute_savings = grid_costs_before - grid_costs_after
    relative_savings = (absolute_savings / grid_costs_before * 100) if grid_costs_before > 0 else 0
    
    savings = {
        "grid_costs_before": grid_costs_before,
        "grid_costs_after": grid_costs_after,
        "absolute_savings": absolute_savings,
        "relative_grid_savings": relative_savings,
    }
    
    # Save to Excel
    savings_df = pd.DataFrame([savings])
    savings_path = os.path.join(report_directory, "savings.xlsx")
    savings_df.to_excel(savings_path, index=False)
    
    return savings


def _generate_plots(
    df: pd.DataFrame,
    evu_col: str,
    cooling_power_before_col: str,
    cooling_power_after_col: str,
    grid_power_before_col: str,
    grid_power_after_col: str,
    energy_price_col: str,
    schedule_temp_col: str,
    pv_power_col: Optional[str],
    report_directory: str,
    show_plots: bool,
    savings: dict,
    system_group_name: Optional[str] = None,
    optimization_mode: str = "cost",
    emission_factor_col: Optional[str] = None,
):
    """Generate visualization plots."""
    plotter = PhaseChangePlotter(df)
    
    # 0. Before optimization plot (German labels) - similar to reference plot
    # Note: The "before" state is the same for all system groups (same input data)
    # The title indicates which system group this analysis is for
    plot_title = "Datenlage vor Optimierung: Phase-Change Kühlsystem mit PV"
    if system_group_name:
        plot_title += f" ({system_group_name})"
    plotter.plot_before_optimization(
        evu_col=evu_col,
        site_consumption_col=SITE_CONSUMPTION_BEFORE_OPTIMIZATION_COL,
        cooling_power_col=cooling_power_before_col,  # Not displayed, kept for compatibility
        pv_power_col=pv_power_col,
        title=plot_title,
        save_path=os.path.join(report_directory, "before_optimization.html"),
    )
    
    # 0b. Before optimization plot with price (German labels) - with electricity price
    price_plot_title = "Effekt 1: Optimierung des Netzbezugs zum Ausnutzen günstiger Marktpreise: Ausgangslage"
    if system_group_name:
        price_plot_title += f" ({system_group_name})"
    plotter.plot_before_optimization_with_price(
        evu_col=evu_col,
        grid_power_col=grid_power_before_col,
        site_consumption_col=SITE_CONSUMPTION_BEFORE_OPTIMIZATION_COL,
        price_col=ENERGY_PRICE_BEFORE_OPTIMIZATION_IN_CT_PER_KWH,
        cooling_power_col=cooling_power_before_col,  # Not displayed, kept for compatibility
        pv_power_col=pv_power_col,
        title=price_plot_title,
        save_path=os.path.join(report_directory, "before_optimization_with_price.html"),
    )
    
    # Note: Cooling Power comparison plot removed - only showing site consumption
    
    # 2. Grid Power comparison plot
    plotter.plot_comparison(
        before_col=grid_power_before_col,
        after_col=grid_power_after_col,
        title=f"Grid Power Comparison (Savings: {savings['relative_grid_savings']:.1f}%)",
        save_path=os.path.join(report_directory, "grid_power_comparison.html"),
    )
    
    # 3. Cost comparison plot
    if "Cost Before (€/h)" in df.columns and "Cost After (€/h)" in df.columns:
        plotter.plot_comparison(
            before_col="Cost Before (€/h)",
            after_col="Cost After (€/h)",
            title=f"Hourly Cost Comparison (Total Savings: {savings['absolute_savings']:.2f} €)",
            save_path=os.path.join(report_directory, "cost_comparison.html"),
        )
    
    # 4. Energy Consumption comparison plot
    if "Energy Consumption Before (kWh)" in df.columns and "Energy Consumption After (kWh)" in df.columns:
        plotter.plot_comparison(
            before_col="Energy Consumption Before (kWh)",
            after_col="Energy Consumption After (kWh)",
            title="Cumulative Energy Consumption Comparison",
            save_path=os.path.join(report_directory, "energy_consumption_comparison.html"),
        )
    
    # 5. Comprehensive power curves (without cooling power - showing PV, price, and temperature)
    power_cols = []
    if pv_power_col:
        power_cols.append(pv_power_col)
    
    # Only create comprehensive plot if we have at least PV power or other data to show
    if power_cols or energy_price_col or schedule_temp_col:
        plotter.plot_power_curves(
            power_cols=power_cols,
            energy_price_col=energy_price_col if optimization_mode == "cost" else None,
            temp_col=schedule_temp_col,
            title="Phase-Change Cooling Analysis",
            save_path=os.path.join(report_directory, "comprehensive_analysis.html"),
        )
    
    # Emission-specific plots
    if optimization_mode == "emission" and emission_factor_col and emission_factor_col in df.columns:
        # 6. Emission factor curve
        plotter.plot_emission_factor_curve(
            emission_factor_col=emission_factor_col,
            schedule_temp_col=schedule_temp_col,
            title="Emission Factor and Temperature Schedule",
            save_path=os.path.join(report_directory, "emission_factor_curve.html"),
        )
        
        # 7. Emission comparison plot
        if "Cumulative Emissions Before (kg CO2)" in df.columns and "Cumulative Emissions After (kg CO2)" in df.columns:
            total_emissions_before = df["Cumulative Emissions Before (kg CO2)"].iloc[-1]
            total_emissions_after = df["Cumulative Emissions After (kg CO2)"].iloc[-1]
            emission_savings = total_emissions_before - total_emissions_after
            emission_savings_pct = (emission_savings / total_emissions_before * 100) if total_emissions_before > 0 else 0
            
            plotter.plot_comparison(
                before_col="Cumulative Emissions Before (kg CO2)",
                after_col="Cumulative Emissions After (kg CO2)",
                title=f"Cumulative CO₂ Emissions Comparison (Savings: {emission_savings:.1f} kg CO₂, {emission_savings_pct:.1f}%)",
                save_path=os.path.join(report_directory, "emission_comparison.html"),
            )
        
        # 8. Power consumption before/after for emission optimization
        plotter.plot_comparison(
            before_col=grid_power_before_col,
            after_col=grid_power_after_col,
            title="Power Consumption Before and After Emission-Based Optimization",
            save_path=os.path.join(report_directory, "power_consumption_emission_optimization.html"),
        )
    
    if show_plots:
        print("Plots generated. Open HTML files in browser to view.")


if __name__ == "__main__":
    # Example usage
    import numpy as np
    
    # Create sample data
    dates = pd.date_range(start="2024-01-01", end="2024-01-08", freq="15min")
    df = pd.DataFrame(index=dates)
    
    # Sample data
    df["EVU Meter"] = 100 + 20 * np.sin(np.arange(len(df)) * 2 * np.pi / 96)
    df["Cooling Power"] = 50 + 10 * np.sin(np.arange(len(df)) * 2 * np.pi / 96)
    df["Spot Market Price (€/MWh)"] = 50 + 30 * np.sin(np.arange(len(df)) * 2 * np.pi / 96)
    
    # Run analysis
    run_phase_change_analysis(
        data=df,
        evu_col="EVU Meter",
        cooling_power_col="Cooling Power",
        spotmarket_energy_price_in_euro_per_mwh_col="Spot Market Price (€/MWh)",
        const_energy_price_in_euro_per_mwh_col=None,
        power_price_in_euro_per_kw=100,
        cop=3.5,
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
        report_directory="reports/example_analysis",
        latent_heat_capacity_in_j_per_kg=334000,  # Water/ice
        pcm_mass_in_kg=1000,  # 1 ton of PCM
        phase_change_temp_in_c=0.0,
        latent_heat_factor=1.1,
        show_plots=True,
    )

