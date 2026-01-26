"""
Multi-system optimization for phase-change cooling.

This module handles separate optimization of different cooling system types
(e.g., Pluskühlung and Tiefkühlung) to maximize savings potential.
"""

import os
import logging
from typing import Dict, List, Union, Optional
import pandas as pd
import numpy as np

from analysis.phase_change_analysis_tool import (
    run_phase_change_analysis,
    SITE_CONSUMPTION_BEFORE_OPTIMIZATION_COL,
    GRID_POWER_BEFORE_OPTIMIZATION_COL,
    SPOTMARKET_ENERGY_PRICE_IN_CT_PER_KWH,
)
from utils.insulation_calculator import calculate_heat_transfer_coefficient
from utils.plotting import PhaseChangePlotter
from utils.data_processing import convert_power_to_energy

logger = logging.getLogger(__name__)


def optimize_separate_systems(
    data: pd.DataFrame,
    evu_col: str,
    cooling_power_col: str,
    spotmarket_energy_price_in_euro_per_mwh_col: str,
    const_energy_price_in_euro_per_mwh_col: Optional[str],
    power_price_in_euro_per_kw: Union[int, float],
    cop: Union[int, float],
    schedule_temp_type: str,
    cooling_systems: List[Dict],
    cooling_ramp_slope_in_k_per_h: Union[int, float],
    warming_ramp_slope_in_k_per_h: Union[int, float],
    report_directory: str,
    # Phase-change specific parameters
    latent_heat_capacity_in_j_per_kg: Union[int, float] = 200000,
    pcm_mass_in_kg: Union[int, float] = 0,
    phase_change_temp_in_c: Union[int, float] = 0,
    latent_heat_factor: Union[int, float] = 1.0,
    # Optional parameters
    pv_power_col: Optional[str] = None,
    cooling_power_distribution: Optional[Dict[str, float]] = None,
    show_plots: bool = False,
) -> Dict[str, pd.DataFrame]:
    """
    Optimize multiple cooling systems separately.
    
    Groups systems by type (e.g., Pluskühlung vs. Tiefkühlung) and optimizes
    each group separately to maximize savings potential.
    
    Parameters:
    -----------
    data : pd.DataFrame
        Input data with power consumption and prices
    evu_col : str
        Column name for EVU meter readings
    cooling_power_col : str
        Column name for total cooling power
    spotmarket_energy_price_in_euro_per_mwh_col : str
        Column name for spot market energy prices
    const_energy_price_in_euro_per_mwh_col : str or None
        Column name for constant energy prices
    power_price_in_euro_per_kw : float
        Power price in euros per kilowatt
    cop : float
        Coefficient of Performance - dimensionless ratio (cooling capacity in kW / electrical power in kW)
    schedule_temp_type : str
        Type of temperature schedule
    cooling_systems : List[Dict]
        List of cooling system configurations
    cooling_ramp_slope_in_k_per_h : float
        Cooling ramp slope (negative value)
    warming_ramp_slope_in_k_per_h : float
        Warming ramp slope (positive value)
    report_directory : str
        Base directory for reports
    latent_heat_capacity_in_j_per_kg : float
        Latent heat capacity of PCM
    pcm_mass_in_kg : float
        Mass of phase-change material
    phase_change_temp_in_c : float
        Phase change temperature
    latent_heat_factor : float
        Latent heat efficiency factor
    pv_power_col : str, optional
        Column name for PV power data
    cooling_power_distribution : Dict[str, float], optional
        Distribution of cooling power between system groups
        e.g., {"Pluskühlung": 0.5, "Tiefkühlung": 0.5}
    show_plots : bool
        Whether to display plots
    
    Returns:
    --------
    Dict[str, pd.DataFrame]
        Dictionary with results for each system group
    """
    # Group systems by type
    system_groups = _group_systems_by_type(cooling_systems)
    
    # Distribute cooling power if not provided
    if cooling_power_distribution is None:
        cooling_power_distribution = _calculate_cooling_power_distribution(
            system_groups, cooling_systems
        )
    
    results = {}
    combined_df = data.copy()
    
    # Initialize combined results columns
    combined_df["EVU Meter After Optimization"] = combined_df[evu_col].copy()
    combined_df["Cooling Power After Optimization"] = 0.0
    combined_df["Grid Power After"] = 0.0
    
    total_savings = {
        "grid_costs_before": 0.0,
        "grid_costs_after": 0.0,
        "absolute_savings": 0.0,
        "relative_grid_savings": 0.0,
    }
    
    # Optimize each system group separately
    for group_name, systems in system_groups.items():
        logger.info(f"Optimizing {group_name} systems...")
        
        # Calculate properties for this group
        group_properties = _calculate_group_properties(systems)
        
        # Select PCM parameters based on system group type
        # Try to import system-specific PCM parameters from config
        try:
            from config import (
                LATENT_HEAT_CAPACITY_PLUSKUEHLUNG_J_PER_KG,
                PCM_MASS_PLUSKUEHLUNG_KG,
                PHASE_CHANGE_TEMP_PLUSKUEHLUNG_C,
                LATENT_HEAT_FACTOR_PLUSKUEHLUNG,
                LATENT_HEAT_CAPACITY_TIEFKUEHLUNG_J_PER_KG,
                PCM_MASS_TIEFKUEHLUNG_KG,
                PHASE_CHANGE_TEMP_TIEFKUEHLUNG_C,
                LATENT_HEAT_FACTOR_TIEFKUEHLUNG,
            )
            
            # Select PCM parameters based on group name
            if "Pluskühlung" in group_name or "pluskühlung" in group_name.lower():
                group_latent_heat = LATENT_HEAT_CAPACITY_PLUSKUEHLUNG_J_PER_KG
                group_pcm_mass = PCM_MASS_PLUSKUEHLUNG_KG
                group_phase_change_temp = PHASE_CHANGE_TEMP_PLUSKUEHLUNG_C
                group_latent_factor = LATENT_HEAT_FACTOR_PLUSKUEHLUNG
            elif "Tiefkühlung" in group_name or "tiefkühlung" in group_name.lower():
                group_latent_heat = LATENT_HEAT_CAPACITY_TIEFKUEHLUNG_J_PER_KG
                group_pcm_mass = PCM_MASS_TIEFKUEHLUNG_KG
                group_phase_change_temp = PHASE_CHANGE_TEMP_TIEFKUEHLUNG_C
                group_latent_factor = LATENT_HEAT_FACTOR_TIEFKUEHLUNG
            else:
                # Fallback to default values
                group_latent_heat = latent_heat_capacity_in_j_per_kg
                group_pcm_mass = pcm_mass_in_kg
                group_phase_change_temp = phase_change_temp_in_c
                group_latent_factor = latent_heat_factor
        except ImportError:
            # Fallback to function parameters if config values not available
            group_latent_heat = latent_heat_capacity_in_j_per_kg
            group_pcm_mass = pcm_mass_in_kg
            group_phase_change_temp = phase_change_temp_in_c
            group_latent_factor = latent_heat_factor
        
        # Allocate cooling power to this group
        cooling_power_fraction = cooling_power_distribution.get(group_name, 0.5)
        group_data = data.copy()
        group_data["Cooling Power"] = data[cooling_power_col] * cooling_power_fraction
        
        # Create report subdirectory
        group_report_dir = os.path.join(report_directory, group_name.lower().replace(" ", "_"))
        
        # Run optimization for this group
        run_phase_change_analysis(
            data=group_data,
            evu_col=evu_col,  # Still use total EVU for grid calculation
            cooling_power_col="Cooling Power",
            spotmarket_energy_price_in_euro_per_mwh_col=spotmarket_energy_price_in_euro_per_mwh_col,
            const_energy_price_in_euro_per_mwh_col=const_energy_price_in_euro_per_mwh_col,
            power_price_in_euro_per_kw=power_price_in_euro_per_kw,
            cop=cop,
            schedule_temp_type=schedule_temp_type,
            dflt_indoor_temp=group_properties["dflt_indoor_temp"],
            min_temp_allowed=group_properties["min_temp_allowed"],
            max_temp_allowed=group_properties["max_temp_allowed"],
            mapping_of_walls_properties=group_properties["walls_properties"],
            mapping_of_content_properties=group_properties["content_properties"],
            cooling_ramp_slope_in_k_per_h=cooling_ramp_slope_in_k_per_h,
            warming_ramp_slope_in_k_per_h=warming_ramp_slope_in_k_per_h,
            report_directory=group_report_dir,
            latent_heat_capacity_in_j_per_kg=group_latent_heat,
            pcm_mass_in_kg=group_pcm_mass / len(system_groups),  # Distribute PCM mass
            phase_change_temp_in_c=group_phase_change_temp,
            latent_heat_factor=group_latent_factor,
            pv_power_col=pv_power_col,
            show_plots=show_plots,
            system_group_name=group_name,  # Pass group name for plot titles
        )
        
        # Load results from this group
        group_results_path = os.path.join(group_report_dir, "results.xlsx")
        if os.path.exists(group_results_path):
            group_results = pd.read_excel(group_results_path, index_col=0, parse_dates=True)
            results[group_name] = group_results
            
            # Combine cooling power (add optimized cooling power for this group)
            if "Cooling Power After Optimization" in group_results.columns:
                combined_df["Cooling Power After Optimization"] += (
                    group_results["Cooling Power After Optimization"]
                )
            
            # Load savings
            savings_path = os.path.join(group_report_dir, "savings.xlsx")
            if os.path.exists(savings_path):
                group_savings = pd.read_excel(savings_path)
                if len(group_savings) > 0:
                    total_savings["grid_costs_before"] += group_savings["grid_costs_before"].iloc[0]
                    total_savings["grid_costs_after"] += group_savings["grid_costs_after"].iloc[0]
    
    # Calculate combined EVU after optimization
    combined_df["EVU Meter After Optimization"] = (
        combined_df[evu_col]
        - combined_df[cooling_power_col]
        + combined_df["Cooling Power After Optimization"]
    )
    
    # Calculate combined grid power
    combined_df["Grid Power After"] = combined_df["EVU Meter After Optimization"].clip(lower=0)
    
    # Calculate combined "before" columns for comparison plots
    if pv_power_col and pv_power_col in combined_df.columns:
        combined_df["EVU Meter (Net)"] = combined_df[evu_col] - combined_df[pv_power_col]
        combined_df["Grid Power Before"] = combined_df["EVU Meter (Net)"].clip(lower=0)
        combined_df["Site Consumption Before"] = combined_df[evu_col]
    else:
        combined_df["Grid Power Before"] = combined_df[evu_col].clip(lower=0)
        combined_df["Site Consumption Before"] = combined_df[evu_col]
    
    # Calculate cost and energy columns for combined analysis
    time_step_hours = (combined_df.index[1] - combined_df.index[0]).total_seconds() / 3600 if len(combined_df) > 1 else 0.25
    
    # Energy price column (convert from €/MWh to ct/kWh if needed)
    if spotmarket_energy_price_in_euro_per_mwh_col in combined_df.columns:
        price_col = spotmarket_energy_price_in_euro_per_mwh_col
        # Convert €/MWh to ct/kWh: (€/MWh) * (100 ct/€) / (1000 kWh/MWh) = ct/kWh
        combined_df["Spot Market Price (ct/kWh)"] = combined_df[price_col] / 10.0
    else:
        combined_df["Spot Market Price (ct/kWh)"] = 0.0
    
    # Calculate costs
    combined_df["Cost Before (€/h)"] = (
        combined_df["Grid Power Before"] * time_step_hours
        * combined_df["Spot Market Price (ct/kWh)"] / 100
    )
    combined_df["Cost After (€/h)"] = (
        combined_df["Grid Power After"] * time_step_hours
        * combined_df["Spot Market Price (ct/kWh)"] / 100
    )
    
    # Calculate cumulative energy consumption
    combined_df["Energy Consumption Before (kWh)"] = (
        convert_power_to_energy(combined_df["Grid Power Before"])
    )
    combined_df["Energy Consumption After (kWh)"] = (
        convert_power_to_energy(combined_df["Grid Power After"])
    )
    
    # Calculate total savings
    if total_savings["grid_costs_before"] > 0:
        total_savings["absolute_savings"] = (
            total_savings["grid_costs_before"] - total_savings["grid_costs_after"]
        )
        total_savings["relative_grid_savings"] = (
            total_savings["absolute_savings"] / total_savings["grid_costs_before"] * 100
        )
    
    # Save combined results
    try:
        combined_results_path = os.path.join(report_directory, "results_combined.xlsx")
        combined_df.to_excel(combined_results_path)
        logger.info(f"Saved combined results to {combined_results_path}")
    except PermissionError:
        logger.warning(f"Could not save combined results - file may be open. Skipping...")
    except Exception as e:
        logger.warning(f"Error saving combined results: {e}")
    
    # Save combined savings
    try:
        combined_savings_path = os.path.join(report_directory, "savings_combined.xlsx")
        pd.DataFrame([total_savings]).to_excel(combined_savings_path, index=False)
        logger.info(f"Saved combined savings to {combined_savings_path}")
    except PermissionError:
        logger.warning(f"Could not save combined savings - file may be open. Skipping...")
    except Exception as e:
        logger.warning(f"Error saving combined savings: {e}")
    
    logger.info(f"Combined savings: {total_savings['relative_grid_savings']:.1f}%")
    logger.info(f"Absolute savings: {total_savings['absolute_savings']:.2f} €")
    
    # Generate combined HTML reports
    try:
        _generate_combined_plots(
            df=combined_df,
            evu_col=evu_col,
            grid_power_before_col="Grid Power Before",
            grid_power_after_col="Grid Power After",
            site_consumption_col="Site Consumption Before",
            pv_power_col=pv_power_col,
            energy_price_col="Spot Market Price (ct/kWh)",
            report_directory=report_directory,
            savings=total_savings,
        )
        logger.info("Successfully generated combined HTML reports")
    except Exception as e:
        logger.warning(f"Failed to generate combined HTML reports: {e}")
        import traceback
        logger.debug(traceback.format_exc())
    
    return results


def _group_systems_by_type(cooling_systems: List[Dict]) -> Dict[str, List[Dict]]:
    """Group cooling systems by type (Pluskühlung vs. Tiefkühlung)."""
    groups = {}
    
    for system in cooling_systems:
        # Determine system type based on default temperature
        default_temp = system.get('default_temp_c', 0)
        
        if default_temp > -10:  # Pluskühlung (typically 0-4°C)
            group_name = "Pluskühlung"
        else:  # Tiefkühlung (typically -18 to -20°C)
            group_name = "Tiefkühlung"
        
        if group_name not in groups:
            groups[group_name] = []
        groups[group_name].append(system)
    
    return groups


def _calculate_cooling_power_distribution(
    system_groups: Dict[str, List[Dict]],
    all_systems: List[Dict],
) -> Dict[str, float]:
    """Calculate cooling power distribution based on system areas."""
    distribution = {}
    total_area = sum(sys.get('room_area_sqm', 0) for sys in all_systems)
    
    for group_name, systems in system_groups.items():
        group_area = sum(sys.get('room_area_sqm', 0) for sys in systems)
        distribution[group_name] = group_area / total_area if total_area > 0 else 0.5
    
    return distribution


def _calculate_group_properties(systems: List[Dict]) -> Dict:
    """Calculate aggregated properties for a group of systems."""
    total_wall_area = sum(sys.get('room_area_sqm', 0) for sys in systems)
    total_content_mass = sum(sys.get('room_content_mass_kg', 0) for sys in systems)
    
    # Calculate weighted average U-value
    total_heat_transfer_area_coef = 0.0
    for sys in systems:
        u_value = calculate_heat_transfer_coefficient(
            sys.get('insulation_thickness_m', 0.15),
            sys.get('insulation_type', 'mineral_wool')
        )
        total_heat_transfer_area_coef += sys.get('room_area_sqm', 0) * u_value
    
    avg_heat_transfer_coef = (
        total_heat_transfer_area_coef / total_wall_area 
        if total_wall_area > 0 else 0.1
    )
    
    # Apply U-value calibration factor if available
    try:
        from config import U_VALUE_CALIBRATION_FACTOR
        avg_heat_transfer_coef *= U_VALUE_CALIBRATION_FACTOR
        if U_VALUE_CALIBRATION_FACTOR != 1.0:
            logger.info(f"Applied U-value calibration factor: {U_VALUE_CALIBRATION_FACTOR:.2f}")
    except ImportError:
        pass  # Use calculated value if calibration factor not available
    
    # Temperature settings
    dflt_indoor_temp = np.mean([sys.get('default_temp_c', 0) for sys in systems])
    min_temp_allowed = min(sys.get('min_temp_allowed_c', 0) for sys in systems)
    max_temp_allowed = max(sys.get('max_temp_allowed_c', 4) for sys in systems)
    
    # Add air mass
    # Calculate volume from room areas and heights
    # Note: room_area_sqm is used as wall area in this context
    # For volume calculation, we need floor area: approximate as wall_area / (4 * height) for rectangular rooms
    # Or use a more direct approach: if room_area_sqm represents floor area
    estimated_height = np.mean([sys.get('room_height_m', 3.0) for sys in systems])
    
    # Calculate volume properly:
    # If room_area_sqm is floor area: volume = floor_area × height
    # If room_area_sqm is wall area: volume ≈ (wall_area / perimeter) × area_factor × height
    # Approximate: for rectangular room, wall_area ≈ 4 × side × height, floor_area ≈ side²
    # So: floor_area ≈ (wall_area / (4*height))² = wall_area² / (16*height²)
    # Simplified: use room_area_sqm as floor area proxy
    # Actually, we'll sum individual room volumes
    total_volume = sum(
        sys.get('room_area_sqm', 0) * sys.get('room_height_m', 3.0) 
        for sys in systems
    )
    air_mass = total_volume * 1.3  # Air density ~1.3 kg/m³
    total_content_mass += air_mass
    
    # Apply heat capacity calibration factor if available
    try:
        from config import HEAT_CAPACITY_CALIBRATION_FACTOR
        total_content_mass *= HEAT_CAPACITY_CALIBRATION_FACTOR
        if HEAT_CAPACITY_CALIBRATION_FACTOR != 1.0:
            logger.info(f"Applied heat capacity calibration factor: {HEAT_CAPACITY_CALIBRATION_FACTOR:.2f}")
    except ImportError:
        pass  # Use calculated value if calibration factor not available
    
    return {
        "dflt_indoor_temp": dflt_indoor_temp,
        "min_temp_allowed": min_temp_allowed,
        "max_temp_allowed": max_temp_allowed,
        "walls_properties": {
            "walls": {
                "area": total_wall_area,
                "heat_transfer_coef": avg_heat_transfer_coef
            }
        },
        "content_properties": {
            "air_and_contents": {
                "mass": total_content_mass,
                "specific_heat_capacity": 1005
            }
        },
    }


def _generate_combined_plots(
    df: pd.DataFrame,
    evu_col: str,
    grid_power_before_col: str,
    grid_power_after_col: str,
    site_consumption_col: str,
    pv_power_col: Optional[str],
    energy_price_col: str,
    report_directory: str,
    savings: dict,
):
    """
    Generate combined HTML plots for all cooling systems together.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Combined DataFrame with all results
    evu_col : str
        Column name for EVU Meter (gross consumption)
    grid_power_before_col : str
        Column name for grid power before optimization
    grid_power_after_col : str
        Column name for grid power after optimization
    site_consumption_col : str
        Column name for site consumption
    pv_power_col : str, optional
        Column name for PV power
    energy_price_col : str
        Column name for energy price
    report_directory : str
        Directory to save plots
    savings : dict
        Dictionary with savings information
    """
    plotter = PhaseChangePlotter(df)
    
    # 1. Before optimization plot (combined)
    plotter.plot_before_optimization(
        evu_col=evu_col,
        site_consumption_col=site_consumption_col,
        cooling_power_col=None,  # Not displayed
        pv_power_col=pv_power_col,
        title="Datenlage vor Optimierung: Gesamtes Kühlsystem (Pluskühlung + Tiefkühlung)",
        save_path=os.path.join(report_directory, "combined_before_optimization.html"),
    )
    
    # 2. Before optimization with price (combined)
    evu_display_col = "EVU Meter (Net)" if "EVU Meter (Net)" in df.columns else evu_col
    plotter.plot_before_optimization_with_price(
        evu_col=evu_display_col,
        grid_power_col=grid_power_before_col,
        site_consumption_col=site_consumption_col,
        price_col=energy_price_col,
        cooling_power_col=None,  # Not displayed
        pv_power_col=pv_power_col,
        title="Effekt 1: Optimierung des Netzbezugs - Gesamtsystem (Ausgangslage)",
        save_path=os.path.join(report_directory, "combined_before_optimization_with_price.html"),
    )
    
    # 3. Grid Power comparison (combined)
    plotter.plot_comparison(
        before_col=grid_power_before_col,
        after_col=grid_power_after_col,
        title=f"Grid Power Comparison - Gesamtsystem (Savings: {savings['relative_grid_savings']:.1f}%)",
        save_path=os.path.join(report_directory, "combined_grid_power_comparison.html"),
    )
    
    # 4. Cost comparison (combined)
    if "Cost Before (€/h)" in df.columns and "Cost After (€/h)" in df.columns:
        plotter.plot_comparison(
            before_col="Cost Before (€/h)",
            after_col="Cost After (€/h)",
            title=f"Hourly Cost Comparison - Gesamtsystem (Total Savings: {savings['absolute_savings']:.2f} €)",
            save_path=os.path.join(report_directory, "combined_cost_comparison.html"),
        )
    
    # 5. Energy Consumption comparison (combined)
    if "Energy Consumption Before (kWh)" in df.columns and "Energy Consumption After (kWh)" in df.columns:
        plotter.plot_comparison(
            before_col="Energy Consumption Before (kWh)",
            after_col="Energy Consumption After (kWh)",
            title="Cumulative Energy Consumption Comparison - Gesamtsystem",
            save_path=os.path.join(report_directory, "combined_energy_consumption_comparison.html"),
        )
    
    # 6. Comprehensive analysis (combined)
    power_cols = []
    if pv_power_col and pv_power_col in df.columns:
        power_cols.append(pv_power_col)
    
    if power_cols or energy_price_col:
        plotter.plot_power_curves(
            power_cols=power_cols,
            energy_price_col=energy_price_col,
            temp_col=None,  # No single temperature schedule for combined
            title="Phase-Change Cooling Analysis - Gesamtsystem",
            save_path=os.path.join(report_directory, "combined_comprehensive_analysis.html"),
        )
    
    logger.info(f"Generated combined HTML reports in {report_directory}")

