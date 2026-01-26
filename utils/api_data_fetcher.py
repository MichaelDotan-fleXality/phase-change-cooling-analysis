"""
API Data Fetcher for Spot Market Prices
Adapted from the original flexality-analyse-dachser-data project.

This module provides functionality to fetch spot market prices from the API
using the same method as the original project.
"""

import os
import logging
from datetime import datetime
from typing import Optional
import pandas as pd
import pytz
import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(override=True)


def fetch_spotmarket_prices_from_api(
    start_time: str,
    end_time: str,
    api_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> pd.DataFrame:
    """
    Fetch spot market prices from the API (same method as original project).
    
    This function uses the same API endpoint as the original flexality project:
    {api_url}/priceForecast?startTime={start_time}&endTime={end_time}
    
    Parameters:
    -----------
    start_time : str
        Start time in ISO 8601 format (e.g., "2025-10-08T00:00:00Z")
        or other formats: "2025-10-08 00:00:00", "2025-10-08T00:00Z"
    end_time : str
        End time in ISO 8601 format
    api_url : str, optional
        API base URL. If None, reads from environment variable API_URL
    api_key : str, optional
        API key. If None, reads from environment variable API_KEY
    
    Returns:
    --------
    pd.DataFrame
        DataFrame with datetime index and "powerPrice" column (in €/MWh)
    
    Raises:
    -------
    ValueError
        If API credentials are not available
    requests.RequestException
        If API request fails
    """
    # Get API credentials from environment or parameters
    if api_url is None:
        api_url = os.environ.get("API_URL")
    if api_key is None:
        api_key = os.environ.get("API_KEY")
    
    if not api_url or not api_key:
        raise ValueError(
            "API credentials not found. "
            "Please set API_URL and API_KEY environment variables, "
            "or provide them as function parameters. "
            "You can also create a .env file with these variables."
        )
    
    # Convert times to ISO 8601 format if needed
    start_time_iso = _convert_to_iso_format(start_time)
    end_time_iso = _convert_to_iso_format(end_time)
    
    # Extend end time by 1 hour (as in original code)
    end_time_extended = (pd.to_datetime(end_time_iso) + pd.Timedelta("1h")).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Build API URL
    url = f"{api_url}/priceForecast?startTime={start_time_iso}&endTime={end_time_extended}"
    
    # Set headers
    headers = {"fleXalityAppKey": api_key}
    
    # Make API request
    logger.info(f"Fetching spotmarket prices from API: {url}")
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        raise requests.RequestException(
            f"API request failed with status code {response.status_code}: {response.text}"
        )
    
    # Parse JSON response
    data = response.json()
    df = pd.DataFrame(data)
    
    if df.empty:
        logger.warning("API returned empty data. Creating empty DataFrame with NaN values.")
        # Create empty DataFrame with correct structure
        date_range = pd.date_range(
            start=start_time_iso,
            end=end_time_iso,
            freq="1h",
            tz="UTC"
        )
        df = pd.DataFrame({"dateTime": date_range, "price": pd.NA})
    
    # Rename column from "price" to "powerPrice" (as in original)
    if "price" in df.columns:
        df.rename(columns={"price": "powerPrice"}, inplace=True)
    elif "powerPrice" not in df.columns:
        raise ValueError(f"Unexpected API response format. Columns: {df.columns.tolist()}")
    
    # Set datetime index
    if "dateTime" in df.columns:
        df["dateTime"] = pd.to_datetime(df["dateTime"], utc=True)
        df.set_index("dateTime", inplace=True)
    else:
        raise ValueError("API response missing 'dateTime' column")
    
    # Ensure timezone-aware index (UTC)
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC')
    else:
        df.index = df.index.tz_convert('UTC')
    
    # Filter to requested time range (ensure both are timezone-aware)
    df = df.sort_index()
    start_dt = pd.to_datetime(start_time_iso, utc=True)
    end_dt = pd.to_datetime(end_time_iso, utc=True)
    mask = (df.index >= start_dt) & (df.index <= end_dt)
    df = df.loc[mask]
    
    # Remove timezone for compatibility with local data (if needed)
    # The calling code can handle timezone conversion
    df.index = df.index.tz_localize(None) if df.index.tz else df.index
    
    # Check for NaN values
    if df["powerPrice"].isnull().values.any():
        logger.warning(
            f"NaN values found in price column. "
            f"This might indicate the requested time range is too far in the future."
        )
    
    # Convert to €/MWh if needed (API might return in different units)
    # The original code uses "powerPrice" directly, so we assume it's already in €/MWh
    
    return df[["powerPrice"]]


def _convert_to_iso_format(time_str: str) -> str:
    """
    Convert various datetime formats to ISO 8601 format.
    
    Supports:
    - ISO 8601: "2025-10-08T00:00:00Z" (returns as-is)
    - Standard: "2025-10-08 00:00:00"
    - Without seconds: "2025-10-08T00:00Z"
    - Without time: "2025-10-08" (assumes 00:00:00)
    """
    # If already in ISO format with Z
    if "T" in time_str and "Z" in time_str:
        return time_str
    
    # Try parsing and converting
    try:
        dt = pd.to_datetime(time_str)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception as e:
        raise ValueError(f"Invalid datetime format: {time_str}. Error: {e}")


def fetch_spotmarket_prices(
    start_time: str,
    end_time: str,
    api_url: Optional[str] = None,
    api_key: Optional[str] = None,
    csv_path: Optional[str] = None,
) -> pd.DataFrame:
    """
    Fetch spot market prices from API or CSV file.
    
    Tries API first if credentials are available, otherwise falls back to CSV.
    
    Parameters:
    -----------
    start_time : str
        Start time (various formats supported)
    end_time : str
        End time (various formats supported)
    api_url : str, optional
        API base URL (or set API_URL environment variable)
    api_key : str, optional
        API key (or set API_KEY environment variable)
    csv_path : str, optional
        Path to CSV file with spot prices (fallback if API not available)
    
    Returns:
    --------
    pd.DataFrame
        DataFrame with datetime index and "powerPrice" column (in €/MWh)
    """
    # Try API first
    try:
        return fetch_spotmarket_prices_from_api(
            start_time=start_time,
            end_time=end_time,
            api_url=api_url,
            api_key=api_key,
        )
    except (ValueError, requests.RequestException) as e:
        logger.warning(f"Failed to fetch from API: {e}")
        
        # Fallback to CSV
        if csv_path:
            from utils.data_processing import load_spot_market_prices
            logger.info(f"Falling back to CSV file: {csv_path}")
            df = load_spot_market_prices(csv_path)
            
            # Filter to time range
            start_dt = pd.to_datetime(start_time)
            end_dt = pd.to_datetime(end_time)
            df = df[(df.index >= start_dt) & (df.index <= end_dt)]
            
            # Rename to match expected column name
            if "Spot Market Price (€/MWh)" in df.columns:
                df = df.rename(columns={"Spot Market Price (€/MWh)": "powerPrice"})
            elif len(df.columns) == 1:
                df.columns = ["powerPrice"]
            
            return df
        else:
            raise ValueError(
                "Neither API credentials nor CSV path provided. "
                "Please set API_URL and API_KEY environment variables, "
                "or provide csv_path parameter."
            )

