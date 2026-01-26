"""
Data processing utilities for phase-change cooling analysis.
"""

import pandas as pd
import numpy as np
from typing import Union, Optional


def convert_power_to_energy(
    power: pd.Series,
    index: Optional[pd.DatetimeIndex] = None,
) -> pd.Series:
    """
    Convert power (kW) to energy (kWh) by integration.
    
    Parameters:
    -----------
    power : pd.Series
        Power time series in kW
    index : pd.DatetimeIndex, optional
        Time index (uses power.index if not provided)
    
    Returns:
    --------
    pd.Series
        Energy time series in kWh
    """
    if index is None:
        index = power.index
    
    # Calculate time differences in hours
    time_diffs = index.to_series().diff().dt.total_seconds() / 3600
    # For first time step, use the time difference to next point (or default to time step)
    if len(time_diffs) > 1:
        time_diffs.iloc[0] = time_diffs.iloc[1]
    else:
        # Single data point - assume 15-minute interval
        time_diffs.iloc[0] = 0.25
    
    # Integrate: energy = power * time
    # Cumulative sum starting from 0 (first value = power[0] * time[0])
    energy = (power * time_diffs).cumsum()
    
    return energy


def calculate_hourly_means(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calculate hourly mean values.
    
    Parameters:
    -----------
    data : pd.DataFrame
        Input data with datetime index
    
    Returns:
    --------
    pd.DataFrame
        Hourly mean values
    """
    return data.groupby(data.index.hour).mean()


def determine_surplus_phases(
    df: pd.DataFrame,
    pv_power_col: str,
    site_consumption_col: str,
) -> list:
    """
    Determine time periods with PV surplus (PV > consumption).
    
    Parameters:
    -----------
    df : pd.DataFrame
        Input DataFrame
    pv_power_col : str
        Column name for PV power
    site_consumption_col : str
        Column name for site consumption
    
    Returns:
    --------
    list
        List of (start, end) index tuples for surplus phases
    """
    surplus = df[pv_power_col] > df[site_consumption_col]
    
    phases = []
    in_surplus = False
    start_idx = None
    
    for i, is_surplus in enumerate(surplus):
        if is_surplus and not in_surplus:
            start_idx = df.index[i]
            in_surplus = True
        elif not is_surplus and in_surplus:
            phases.append((start_idx, df.index[i-1]))
            in_surplus = False
    
    if in_surplus:
        phases.append((start_idx, df.index[-1]))
    
    return phases


def fix_index_and_interpolate(
    df: pd.DataFrame,
    desired_freq: str = "15min",
    method: str = "linear",
) -> pd.DataFrame:
    """
    Fix index frequency and interpolate missing values.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Input DataFrame
    desired_freq : str
        Desired frequency (e.g., "15min", "1h")
    method : str
        Interpolation method
    
    Returns:
    --------
    pd.DataFrame
        DataFrame with fixed index and interpolated values
    """
    # Create new index
    new_index = pd.date_range(
        start=df.index.min(),
        end=df.index.max(),
        freq=desired_freq
    )
    
    # Reindex and interpolate
    df_reindexed = df.reindex(new_index)
    df_interpolated = df_reindexed.interpolate(method=method)
    
    return df_interpolated


def read_cams_solar_radiation(
    csv_path: str,
    datetime_col: Optional[str] = None,
    ghi_col: Optional[str] = None,
    dni_col: Optional[str] = None,
    dhi_col: Optional[str] = None,
) -> pd.DataFrame:
    """
    Read CAMS solar radiation time-series data from CSV file.
    
    This function performs two important conversions:
    
    1. **Units Conversion (Wh/m² → W/m²)**:
       - CAMS CSV provides values in Wh/m² (energy accumulated over 15-minute period)
       - Function converts to W/m² (instantaneous power) by dividing by 0.25 hours
       - Example: 0.1200 Wh/m² → 0.48 W/m² (0.1200 ÷ 0.25 = 0.48)
       - The function correctly identifies the "Clear sky GHI" column (not TOA)
    
    2. **Timezone Conversion (UTC → Europe/Berlin)**:
       - CAMS data timestamps are in UTC (Universal Time)
       - Function converts to Europe/Berlin timezone (UTC+1 in winter, UTC+2 in summer)
       - This ensures proper alignment with local power usage data
       - Example: 2024-05-01 03:45 UTC → 2024-05-01 05:45 Berlin time (May = UTC+2)
    
    CAMS data typically includes:
    - Timestamp (datetime, converted to Europe/Berlin timezone)
    - GHI: Global Horizontal Irradiance (W/m², converted from Wh/m²)
    - DNI: Direct Normal Irradiance (W/m², converted from Wh/m²)
    - DHI: Diffuse Horizontal Irradiance (W/m², converted from Wh/m²)
    
    Parameters:
    -----------
    csv_path : str
        Path to CSV file containing CAMS solar radiation data
    datetime_col : str, optional
        Name of datetime column. If None, tries common names or uses first column
    ghi_col : str, optional
        Name of GHI column. If None, tries to auto-detect
    dni_col : str, optional
        Name of DNI column. If None, tries to auto-detect
    dhi_col : str, optional
        Name of DHI column. If None, tries to auto-detect
    
    Returns:
    --------
    pd.DataFrame
        DataFrame with datetime index (in Europe/Berlin timezone, timezone-naive)
        and solar radiation columns in W/m² (power, not energy)
    """
    # CAMS files use semicolon separator and have header comments
    # First, find the header row (line with "Observation period" and column names)
    with open(csv_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    header_row = None
    data_start_row = None
    for i, line in enumerate(lines):
        if 'Observation period' in line and ('GHI' in line or 'Clear sky' in line):
            header_row = i
            # Data starts on the next line after header
            data_start_row = i + 1
            break
    
    if header_row is None:
        raise ValueError("Could not find header row with 'Observation period' and 'GHI' or 'Clear sky' in CAMS file")
    
    # Try reading with semicolon separator first (CAMS format)
    try:
        # Read header line separately to handle the # prefix
        header_line = lines[header_row].strip()
        if header_line.startswith('#'):
            # Remove # and extract column names
            header_line = header_line[1:].strip()
            column_names = [col.strip() for col in header_line.split(';')]
        else:
            column_names = None
        
        # Read data starting from data_start_row
        df = pd.read_csv(
            csv_path,
            sep=';',
            skiprows=data_start_row,
            encoding='utf-8',
            decimal=',',  # German decimal format
            on_bad_lines='skip',
            low_memory=False,
            names=column_names if column_names else None,  # Use extracted column names
            header=None if column_names else 0  # No header if we provided names
        )
        
        # Clean column names
        df.columns = df.columns.str.strip()
        
        # Extract datetime from first column (observation period)
        first_col = df.columns[0]
        if '/' in str(df[first_col].iloc[0] if len(df) > 0 else ''):
            # Format: "2025-10-08T00:00:00.0/2025-10-08T00:15:00.0"
            df['datetime'] = df[first_col].astype(str).str.split('/').str[0]
            # CAMS data is typically in UTC - parse as UTC if no timezone info
            df['datetime'] = pd.to_datetime(df['datetime'], errors='coerce', format='ISO8601', utc=True)
        else:
            # Try parsing as datetime directly
            # CAMS data is typically in UTC - parse as UTC if no timezone info
            df['datetime'] = pd.to_datetime(df[first_col], errors='coerce', utc=True)
        
        df = df.dropna(subset=['datetime'])
        
        # Remove duplicate datetimes (keep first occurrence)
        duplicates = df['datetime'].duplicated()
        if duplicates.sum() > 0:
            print(f"   [INFO] Removing {duplicates.sum()} duplicate datetime entries from CAMS data...")
            df = df[~duplicates]
        
        df.set_index('datetime', inplace=True)
        
        # Convert UTC to Europe/Berlin timezone to match power data and pvlib location
        # This ensures proper alignment with local power usage data
        if df.index.tz is not None:
            # Already timezone-aware (UTC), convert to Europe/Berlin
            df.index = df.index.tz_convert('Europe/Berlin')
        else:
            # If no timezone info, assume UTC (CAMS standard) and convert to local time
            df.index = df.index.tz_localize('UTC').tz_convert('Europe/Berlin')
        
        # Remove timezone info for alignment with timezone-naive power data
        df.index = df.index.tz_localize(None)
        
        # Drop the original first column
        if first_col in df.columns:
            df = df.drop(columns=[first_col])
        
        # Identify GHI column
        ghi_found = None
        for col in df.columns:
            col_upper = col.upper()
            if 'GHI' in col_upper or ('CLEAR' in col_upper and 'SKY' in col_upper and 'GHI' in col_upper):
                ghi_found = col
                break
        
        if ghi_found:
            df = df.rename(columns={ghi_found: 'GHI'})
            df['GHI'] = pd.to_numeric(df['GHI'], errors='coerce')
        else:
            # Try to find numeric column with reasonable values
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) > 0:
                for col in numeric_cols:
                    if df[col].max() > 0 and df[col].max() < 2000:
                        df['GHI'] = pd.to_numeric(df[col], errors='coerce')
                        break
        
        # Create DNI/DHI if not available (rough estimates)
        if 'DNI' not in df.columns:
            df['DNI'] = df['GHI'] * 0.8 if 'GHI' in df.columns else 0
        if 'DHI' not in df.columns:
            df['DHI'] = df['GHI'] * 0.2 if 'GHI' in df.columns else 0
        
        # Convert Wh/m² to W/m² (CAMS provides energy over 15-minute period)
        # Always convert: Wh/m² / 0.25h = W/m² (power)
        time_step_hours = 0.25  # 15 minutes
        if 'GHI' in df.columns:
            # Check if values are in Wh/m² (typical range: 0-500 Wh/m² for 15 min)
            # vs W/m² (typical range: 0-2000 W/m²)
            if df['GHI'].max() < 2000:  # Likely in Wh/m², convert to W/m²
                df['GHI'] = df['GHI'] / time_step_hours
        if 'DNI' in df.columns and df['DNI'].max() < 2000:
            df['DNI'] = df['DNI'] / time_step_hours
        if 'DHI' in df.columns and df['DHI'].max() < 2000:
            df['DHI'] = df['DHI'] / time_step_hours
        
        # Keep only needed columns
        result_cols = []
        if 'GHI' in df.columns:
            result_cols.append('GHI')
        if 'DNI' in df.columns:
            result_cols.append('DNI')
        if 'DHI' in df.columns:
            result_cols.append('DHI')
        
        if result_cols:
            df = df[result_cols].copy()
        else:
            raise ValueError("Could not find GHI, DNI, or DHI columns in CAMS data")
        
        return df
        
    except Exception as e:
        # Fallback: try reading as standard CSV (comma-separated)
        try:
            df = pd.read_csv(csv_path)
            
            # Try to detect datetime column
            if datetime_col is None:
                datetime_candidates = ['time', 'timestamp', 'datetime', 'date', 'Date', 'Time', 'Timestamp', 'DateTime']
                datetime_col = None
                for col in datetime_candidates:
                    if col in df.columns:
                        datetime_col = col
                        break
                
                # If still not found, try first column
                if datetime_col is None:
                    datetime_col = df.columns[0]
            
            # Convert datetime column to datetime index
            df[datetime_col] = pd.to_datetime(df[datetime_col])
            df = df.set_index(datetime_col)
            
            # Try to auto-detect irradiance columns if not specified
            if ghi_col is None:
                ghi_candidates = ['GHI', 'ghi', 'global_horizontal', 'Global Horizontal Irradiance', 'Irradiance']
                for col in ghi_candidates:
                    if col in df.columns:
                        ghi_col = col
                        break
            
            if dni_col is None:
                dni_candidates = ['DNI', 'dni', 'direct_normal', 'Direct Normal Irradiance']
                for col in dni_candidates:
                    if col in df.columns:
                        dni_col = col
                        break
            
            if dhi_col is None:
                dhi_candidates = ['DHI', 'dhi', 'diffuse_horizontal', 'Diffuse Horizontal Irradiance']
                for col in dhi_candidates:
                    if col in df.columns:
                        dhi_col = col
                        break
            
            # Select relevant columns
            selected_cols = []
            if ghi_col and ghi_col in df.columns:
                selected_cols.append(ghi_col)
            if dni_col and dni_col in df.columns:
                selected_cols.append(dni_col)
            if dhi_col and dhi_col in df.columns:
                selected_cols.append(dhi_col)
            
            if not selected_cols:
                raise ValueError(
                    f"Could not find solar irradiance columns in CSV. "
                    f"Available columns: {df.columns.tolist()}"
                )
            
            result_df = df[selected_cols].copy()
            
            # Rename columns to standard names
            if ghi_col:
                result_df.rename(columns={ghi_col: 'GHI'}, inplace=True)
            if dni_col:
                result_df.rename(columns={dni_col: 'DNI'}, inplace=True)
            if dhi_col:
                result_df.rename(columns={dhi_col: 'DHI'}, inplace=True)
            
            # Ensure values are numeric
            for col in result_df.columns:
                result_df[col] = pd.to_numeric(result_df[col], errors='coerce')
            
            return result_df
            
        except Exception as e2:
            raise ValueError(
                f"Failed to read CAMS data file. "
                f"Tried both semicolon and comma separators. "
                f"Original error: {e}, Fallback error: {e2}"
            )


def load_spot_market_prices(
    csv_path: str,
    datetime_col: Optional[str] = None,
    price_col: Optional[str] = None,
    target_freq: str = "15min",
) -> pd.Series:
    """
    Load and format spot market electricity prices from CSV file.
    
    Handles various CSV formats from different data sources (EPEX SPOT, ENTSO-E, etc.)
    and converts to standard format for analysis.
    
    Parameters:
    -----------
    csv_path : str
        Path to CSV file containing spot market prices
    datetime_col : str, optional
        Name of datetime column. If None, tries to auto-detect
    price_col : str, optional
        Name of price column. If None, tries to auto-detect
    target_freq : str
        Target frequency for resampling (default: "15min")
    
    Returns:
    --------
    pd.Series
        Spot market prices in €/MWh with datetime index
    """
    # Read CSV
    df = pd.read_csv(csv_path)
    
    # Try to detect datetime column
    if datetime_col is None:
        datetime_candidates = [
            'datetime', 'timestamp', 'date', 'Date', 'Time', 'Timestamp', 
            'DateTime', 'time', 'start_time', 'Start Time'
        ]
        datetime_col = None
        for col in datetime_candidates:
            if col in df.columns:
                datetime_col = col
                break
        
        # If still not found, try first column
        if datetime_col is None:
            datetime_col = df.columns[0]
    
    # Handle EPEX SPOT format (Date + Hour columns)
    if 'Date' in df.columns and 'Hour' in df.columns:
        df['datetime'] = pd.to_datetime(
            df['Date'].astype(str) + ' ' + df['Hour'].astype(str).str.zfill(2) + ':00:00'
        )
        datetime_col = 'datetime'
    
    # Convert datetime column
    df[datetime_col] = pd.to_datetime(df[datetime_col])
    df = df.set_index(datetime_col)
    
    # Try to detect price column
    if price_col is None:
        price_candidates = [
            'Price', 'price', 'Spot Market Price (€/MWh)', 'Price (€/MWh)',
            'Day-ahead Price', 'DAP', 'DAP (€/MWh)', 'Market Price'
        ]
        for col in price_candidates:
            if col in df.columns:
                price_col = col
                break
        
        # If still not found, try numeric columns
        if price_col is None:
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) > 0:
                price_col = numeric_cols[0]
            else:
                raise ValueError(
                    f"Could not find price column. Available columns: {df.columns.tolist()}"
                )
    
    # Extract price series
    prices = df[price_col].copy()
    
    # Convert to numeric, handling any text
    prices = pd.to_numeric(prices, errors='coerce')
    
    # Check units - if prices seem too high (>1000), might be in ct/kWh
    if prices.max() > 1000:
        print(f"⚠ Warning: Prices seem high (max: {prices.max():.2f}). "
              f"Converting from ct/kWh to €/MWh...")
        prices = prices / 10  # Convert ct/kWh to €/MWh
    
    # Ensure €/MWh units (typical range: 0-200 €/MWh)
    if prices.max() > 200:
        print(f"⚠ Warning: Prices seem unusually high (max: {prices.max():.2f} €/MWh). "
              f"Please verify units are in €/MWh.")
    
    # Resample to target frequency if needed
    if target_freq:
        current_freq = pd.infer_freq(prices.index)
        if current_freq != target_freq:
            # Upsample (e.g., hourly to 15-min)
            if pd.Timedelta(current_freq) > pd.Timedelta(target_freq):
                prices = prices.resample(target_freq).interpolate(method='linear')
            # Downsample (e.g., 15-min to hourly) - take mean
            else:
                prices = prices.resample(target_freq).mean()
    
    # Rename series
    prices.name = "Spot Market Price (€/MWh)"
    
    # Remove any NaN values
    prices = prices.dropna()
    
    return prices


def calculate_pv_power_from_irradiance_multiple_arrays(
    solar_data: pd.DataFrame,
    pv_arrays: list,
    location_lat: float,
    location_lon: float = 10.53,
    use_pvlib: bool = True,
) -> pd.Series:
    """
    Calculate PV power output from multiple arrays with different orientations.
    
    This function supports multiple PV arrays (e.g., east/west, different tilts)
    and combines their power output. Based on the existing pv_data_generator.py script.
    
    Parameters:
    -----------
    solar_data : pd.DataFrame
        DataFrame with solar irradiance data (GHI, DNI, DHI from CAMS)
    pv_arrays : list of dict
        List of PV array configurations. Each dict should contain:
        - 'power_kw': float - Installed power in kW for this array
        - 'orientation_deg': float - Azimuth in degrees (0°=North, 90°=East, 180°=South, 270°=West)
        - 'tilt_deg': float - Tilt angle from horizontal in degrees
        - 'base_efficiency': float (optional, default 0.93) - Panel efficiency at STC
        - 'shading_loss': float (optional, default 0.012) - Shading losses factor
        - 'inverter_efficiency': float (optional, default 0.96) - Inverter efficiency
    location_lat : float
        Location latitude in degrees
    location_lon : float
        Location longitude in degrees
    use_pvlib : bool
        If True, use pvlib (requires pvlib package). If False, use simplified model.
    
    Returns:
    --------
    pd.Series
        Combined PV power output time series in kW (AC) from all arrays
    
    Example:
    --------
    pv_arrays = [
        {
            'power_kw': 5.0,
            'orientation_deg': 90,   # East
            'tilt_deg': 20,
            'base_efficiency': 0.93,
            'shading_loss': 0.012,
        },
        {
            'power_kw': 5.0,
            'orientation_deg': 270,  # West
            'tilt_deg': 20,
            'base_efficiency': 0.93,
            'shading_loss': 0.012,
        },
    ]
    """
    try:
        import pvlib
    except ImportError:
        print("⚠ Warning: pvlib not installed. Install with: pip install pvlib")
        print("  Falling back to simplified PV model...")
        use_pvlib = False
    
    # Calculate power for each array and sum them
    total_power = pd.Series(0.0, index=solar_data.index, name='PV Power')
    
    for i, array_config in enumerate(pv_arrays):
        # Get array-specific parameters with defaults
        power_kw = array_config['power_kw']
        orientation_deg = array_config['orientation_deg']
        tilt_deg = array_config['tilt_deg']
        base_efficiency = array_config.get('base_efficiency', 0.93)
        shading_loss = array_config.get('shading_loss', 0.012)
        inverter_efficiency = array_config.get('inverter_efficiency', 0.96)
        
        # Calculate power for this array
        if use_pvlib:
            array_power = _calculate_single_array_power_pvlib(
                solar_data=solar_data,
                installed_power_kw=power_kw,
                orientation_deg=orientation_deg,
                tilt_angle_deg=tilt_deg,
                location_lat=location_lat,
                location_lon=location_lon,
                base_efficiency=base_efficiency,
                shading_loss=shading_loss,
                inverter_efficiency=inverter_efficiency,
            )
        else:
            # Use simplified model
            array_power = calculate_pv_power_from_irradiance(
                solar_data=solar_data,
                installed_power_kw=power_kw,
                orientation_deg=orientation_deg,
                tilt_angle_deg=tilt_deg,
                location_lat=location_lat,
                panel_efficiency=base_efficiency * (1 - shading_loss),
                inverter_efficiency=inverter_efficiency,
            )
        
        # Add to total
        total_power = total_power + array_power
    
    return total_power


def _calculate_single_array_power_pvlib(
    solar_data: pd.DataFrame,
    installed_power_kw: float,
    orientation_deg: float,
    tilt_angle_deg: float,
    location_lat: float,
    location_lon: float,
    base_efficiency: float,
    shading_loss: float,
    inverter_efficiency: float,
) -> pd.Series:
    """
    Internal helper function to calculate power for a single PV array using pvlib.
    """
    import pvlib
    
    # Create location object
    location = pvlib.location.Location(
        latitude=location_lat,
        longitude=location_lon,
        tz='Europe/Berlin'  # Adjust timezone as needed
    )
    
    # Calculate solar position
    solar_position = location.get_solarposition(solar_data.index)
    
    # Get irradiance components
    ghi = solar_data.get('GHI', solar_data.get('ghi', 0))
    dni = solar_data.get('DNI', solar_data.get('dni', 0))
    dhi = solar_data.get('DHI', solar_data.get('dhi', None))
    
    # If DHI not provided, estimate from GHI (typical ratio)
    if dhi is None or (isinstance(dhi, pd.Series) and dhi.isna().all()):
        dhi = ghi * 0.2  # Rough estimate: 20% of GHI is diffuse
    
    # Calculate Plane of Array (POA) irradiance
    poa_irradiance = pvlib.irradiance.get_total_irradiance(
        surface_tilt=tilt_angle_deg,
        surface_azimuth=orientation_deg,
        dni=dni,
        ghi=ghi,
        dhi=dhi,
        solar_zenith=solar_position['zenith'],
        solar_azimuth=solar_position['azimuth'],
        model='isotropic',  # Can use 'perez' for more accuracy if needed
    )
    
    # Get POA global irradiance
    poa_global = poa_irradiance['poa_global']
    
    # Calculate effective efficiency (accounting for shading)
    effective_efficiency = base_efficiency * (1 - shading_loss)
    
    # Calculate DC power
    dc_power_kw = (poa_global / 1000.0) * installed_power_kw * effective_efficiency
    
    # Convert to AC power through inverter
    ac_power_kw = dc_power_kw * inverter_efficiency
    
    # Ensure non-negative
    ac_power_kw = np.maximum(0, ac_power_kw)
    
    return pd.Series(ac_power_kw, index=solar_data.index)


def calculate_pv_power_from_irradiance_pvlib(
    solar_data: pd.DataFrame,
    installed_power_kw: float,
    orientation_deg: float,
    tilt_angle_deg: float,
    location_lat: float,
    location_lon: float = 10.53,  # Default longitude (can be adjusted)
    base_efficiency: float = 0.93,  # Panel efficiency at STC
    shading_loss: float = 0.012,  # Shading losses (1.2%)
    inverter_efficiency: float = 0.96,
    use_pvlib: bool = True,
) -> pd.Series:
    """
    Calculate PV power output using pvlib (industry-standard library).
    
    This is an improved version using pvlib for accurate solar position and
    Plane of Array (POA) irradiance calculations. Based on the existing
    pv_data_generator.py script.
    
    Parameters:
    -----------
    solar_data : pd.DataFrame
        DataFrame with solar irradiance data (GHI, DNI, DHI from CAMS)
    installed_power_kw : float
        Installed PV power in kW (peak power)
    orientation_deg : float
        Panel orientation/azimuth in degrees (0°=North, 90°=East, 180°=South, 270°=West)
    tilt_angle_deg : float
        Panel tilt angle from horizontal in degrees
    location_lat : float
        Location latitude in degrees
    location_lon : float
        Location longitude in degrees (default: 10.53 for Braunschweig)
    base_efficiency : float
        Base panel efficiency at STC (default: 0.93 = 93%)
    shading_loss : float
        Shading losses factor (default: 0.012 = 1.2%)
    inverter_efficiency : float
        Inverter efficiency (default: 0.96 = 96%)
    use_pvlib : bool
        If True, use pvlib (requires pvlib package). If False, use simplified model.
    
    Returns:
    --------
    pd.Series
        PV power output time series in kW (AC)
    """
    try:
        import pvlib
    except ImportError:
        print("⚠ Warning: pvlib not installed. Install with: pip install pvlib")
        print("  Falling back to simplified PV model...")
        use_pvlib = False
    
    if not use_pvlib:
        # Fall back to simplified model
        return calculate_pv_power_from_irradiance(
            solar_data=solar_data,
            installed_power_kw=installed_power_kw,
            orientation_deg=orientation_deg,
            tilt_angle_deg=tilt_angle_deg,
            location_lat=location_lat,
            panel_efficiency=base_efficiency * (1 - shading_loss),
            inverter_efficiency=inverter_efficiency,
        )
    
    # Use the internal helper function
    return _calculate_single_array_power_pvlib(
        solar_data=solar_data,
        installed_power_kw=installed_power_kw,
        orientation_deg=orientation_deg,
        tilt_angle_deg=tilt_angle_deg,
        location_lat=location_lat,
        location_lon=location_lon,
        base_efficiency=base_efficiency,
        shading_loss=shading_loss,
        inverter_efficiency=inverter_efficiency,
    )


def calculate_pv_power_from_irradiance(
    solar_data: pd.DataFrame,
    installed_power_kw: float,
    orientation_deg: float,
    tilt_angle_deg: float,
    location_lat: float,
    panel_efficiency: float = 0.20,
    inverter_efficiency: float = 0.96,
    temperature_coefficient: float = -0.004,  # per °C
    reference_temp: float = 25.0,  # °C
    temp_data: Optional[pd.Series] = None,
) -> pd.Series:
    """
    Calculate PV power output from solar irradiance data.
    
    This function converts solar irradiance (from CAMS or other sources) to PV power output
    based on PV system parameters.
    
    Parameters:
    -----------
    solar_data : pd.DataFrame
        DataFrame with solar irradiance data. Should contain at least 'GHI' column.
        Can also include 'DNI' and 'DHI' for more accurate calculations.
    installed_power_kw : float
        Installed PV power in kW (peak power)
    orientation_deg : float
        Panel orientation in degrees (0°=North, 90°=East, 180°=South, 270°=West)
    tilt_angle_deg : float
        Panel tilt angle from horizontal in degrees (0°=horizontal, 90°=vertical)
    location_lat : float
        Location latitude in degrees
    panel_efficiency : float
        PV panel efficiency (default: 0.20 = 20%)
    inverter_efficiency : float
        Inverter efficiency (default: 0.96 = 96%)
    temperature_coefficient : float
        Temperature coefficient in 1/°C (default: -0.004 = -0.4% per °C)
    reference_temp : float
        Reference temperature for efficiency in °C (default: 25°C)
    temp_data : pd.Series, optional
        Ambient temperature data. If provided, accounts for temperature effects.
    
    Returns:
    --------
    pd.Series
        PV power output time series in kW
    """
    result = solar_data.copy()
    
    # Get GHI (required)
    if 'GHI' not in result.columns:
        raise ValueError("Solar data must contain 'GHI' (Global Horizontal Irradiance) column")
    
    # For simplified calculation, use GHI directly adjusted for tilt and orientation
    # More sophisticated models would use DNI and DHI separately
    if 'DNI' in result.columns and 'DHI' in result.columns:
        # Use Perez model approximation for tilted surface
        # Simplified: assume optimal orientation approximation
        tilt_factor = np.cos(np.radians(tilt_angle_deg)) * 0.9 + 0.1  # Simplified tilt adjustment
        orientation_factor = np.cos(np.radians(orientation_deg - 180)) * 0.2 + 0.8  # South-facing optimal
        effective_irradiance = result['GHI'] * tilt_factor * orientation_factor
    else:
        # Simplified: use GHI with basic adjustments
        # For south-facing (180°) panels in northern hemisphere
        tilt_rad = np.radians(tilt_angle_deg)
        orientation_rad = np.radians(orientation_deg - 180)  # Relative to south
        
        # Simple tilt and orientation factors
        tilt_factor = np.maximum(0, np.cos(tilt_rad - np.radians(90))) * 0.7 + 0.3
        orientation_factor = np.maximum(0, np.cos(orientation_rad)) * 0.3 + 0.7
        
        effective_irradiance = result['GHI'] * tilt_factor * orientation_factor
    
    # Standard test conditions: 1000 W/m² at 25°C
    stc_irradiance = 1000.0  # W/m²
    
    # Calculate DC power (before inverter)
    dc_power_w = effective_irradiance * (installed_power_kw * 1000) / stc_irradiance * panel_efficiency
    
    # Account for temperature effects if temperature data is provided
    if temp_data is not None:
        temp_diff = temp_data - reference_temp
        temp_correction = 1 + (temperature_coefficient * temp_diff)
        dc_power_w = dc_power_w * temp_correction
    
    # Convert to AC power through inverter (and convert to kW)
    ac_power_kw = (dc_power_w * inverter_efficiency) / 1000.0
    
    # Ensure non-negative
    ac_power_kw = np.maximum(0, ac_power_kw)
    
    return pd.Series(ac_power_kw, index=solar_data.index, name='PV Power')