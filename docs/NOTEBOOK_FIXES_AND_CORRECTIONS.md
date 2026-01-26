# Notebook Fixes and Corrections

This document tracks all fixes and corrections made to the `bako_manual_analysis.ipynb` notebook during review and testing. These fixes should be reviewed and potentially applied to the main project script files.

**Date Created:** 2025-01-25  
**Notebook:** `notebooks/bako_manual_analysis.ipynb`

---

## 1. Jupyter Kernel Configuration with Pixi

### Issue
VS Code was trying to use a system Python (3.13.11) instead of the pixi environment, causing kernel startup failures.

### Fix Applied
- Added `ipykernel` and `jupyter` to main dependencies in `pixi.toml` (moved from dev dependencies)
- Created PowerShell wrapper script (`.pixi/kernel_wrapper.ps1`) to ensure pixi environment is properly activated
- Registered kernel with Jupyter: `pixi run python -m ipykernel install --user --name=phase-change-cooling-analysis --display-name="Python (pixi)"`
- Created `.vscode/settings.json` to point VS Code to pixi Python interpreter

### Files Modified
- `pixi.toml` - Added ipykernel and jupyter to main dependencies
- `.pixi/kernel_wrapper.ps1` - Created wrapper script
- `.vscode/settings.json` - Created VS Code settings
- Kernel registration in user's Jupyter config

### Action Required
- Verify main project scripts work with pixi environment
- Consider adding kernel wrapper to project if other notebooks are used

---

## 2. Missing Configuration Variables

### Issue
Notebook was trying to import `SCHEDULE_TEMP_TYPE_PLUSKUEHLUNG` and `SCHEDULE_TEMP_TYPE_TIEFKUEHLUNG` from `config.py`, but these variables didn't exist.

### Fix Applied
Added to `config.py`:
```python
# System-specific schedule types (can override the generic SCHEDULE_TEMP_TYPE)
SCHEDULE_TEMP_TYPE_PLUSKUEHLUNG = "price_like_schedule"  # Schedule type for Pluskühlung systems
SCHEDULE_TEMP_TYPE_TIEFKUEHLUNG = "constrained_price_schedule"  # Schedule type for Tiefkühlung systems (with max deviation)
```

### Files Modified
- `config.py` - Added system-specific schedule type variables

### Action Required
- ✅ Already fixed in `config.py`
- Verify all scripts that import from config have these variables available

---

## 3. Date Parsing - European Format (DD.MM.YYYY)

### Issue
Pandas was trying to parse dates in DD.MM.YYYY format (European) as MM.DD.YYYY (US format), causing `ValueError: time data "13.01.2024" doesn't match format "%m.%d.%Y"`.

### Fix Applied
Changed from:
```python
df_lastgang['Datum'] = pd.to_datetime(df_lastgang['Datum'])
```

To:
```python
# Handle European date format (DD.MM.YYYY)
# Convert to string first if it's already a datetime/date object
if df_lastgang['Datum'].dtype == 'object':
    # Already strings, parse with explicit format
    df_lastgang['Datum'] = pd.to_datetime(df_lastgang['Datum'], format='%d.%m.%Y', errors='coerce')
else:
    # Might be datetime already, convert to string first then parse
    df_lastgang['Datum'] = pd.to_datetime(df_lastgang['Datum'].astype(str), format='%d.%m.%Y', errors='coerce')
```

### Location in Notebook
Cell 6 (Step 1: Load Power Consumption Data)

### Action Required
- Check all scripts that read Excel files with dates in DD.MM.YYYY format
- Apply similar fix to:
  - `run_48h_may_2024_analysis.py`
  - `run_8d_may_2024_analysis.py`
  - `run_full_year_2024_analysis.py`
  - Any other scripts reading BÄKO data files
- Consider creating a utility function in `utils/data_processing.py` for consistent date parsing

---

## 4. Time Parsing - HH:MM Format

### Issue
Time column was in HH:MM format (e.g., "00:15"), but pandas `to_timedelta()` expects HH:MM:SS format, causing `ValueError: expected hh:mm:ss format`.

### Fix Applied
Changed from:
```python
df_lastgang['timestamp'] = df_lastgang['Datum'] + pd.to_timedelta(df_lastgang['Uhrzeit'])
```

To:
```python
# Parse time column (HH:MM format) and convert to timedelta
# Handle time in HH:MM format by adding :00 to make it HH:MM:SS
df_lastgang['Uhrzeit_parsed'] = pd.to_timedelta(df_lastgang['Uhrzeit'].astype(str) + ':00')
df_lastgang['timestamp'] = df_lastgang['Datum'] + df_lastgang['Uhrzeit_parsed']
df_lastgang = df_lastgang.drop('Uhrzeit_parsed', axis=1)
```

### Location in Notebook
Cell 6 (Step 1: Load Power Consumption Data)

### Action Required
- Check all scripts that combine date and time columns
- Apply similar fix to scripts listed in section 3
- Consider creating a utility function for time parsing

---

## 5. Duplicate Timestamp Handling

### Issue
After combining date and time, some rows had duplicate timestamps, causing `ValueError: cannot reindex on an axis with duplicate labels` when trying to reindex other dataframes. Duplicates can also be created during resampling operations.

### Fix Applied
Added duplicate removal at multiple points:

1. After setting index:
```python
# Remove duplicate timestamps (keep first occurrence)
df_lastgang = df_lastgang[~df_lastgang.index.duplicated(keep='first')]
```

2. After resampling:
```python
# Remove any duplicates created during resampling
if df_lastgang.index.duplicated().any():
    print(f"Warning: {df_lastgang.index.duplicated().sum()} duplicate timestamps after resampling, removing...")
    df_lastgang = df_lastgang[~df_lastgang.index.duplicated(keep='first')]
```

3. Before reindexing (check both dataframes):
```python
# Ensure both indexes are unique before reindexing
if df_lastgang.index.duplicated().any():
    print(f"Warning: {df_lastgang.index.duplicated().sum()} duplicate timestamps in df_lastgang, removing...")
    df_lastgang = df_lastgang[~df_lastgang.index.duplicated(keep='first')]
if df_solar.index.duplicated().any():
    print(f"Warning: {df_solar.index.duplicated().sum()} duplicate timestamps in df_solar, removing...")
    df_solar = df_solar[~df_solar.index.duplicated(keep='first')]
```

### Location in Notebook
- Cell 6 (Step 1: Load Power Consumption Data), after `set_index('timestamp')`
- Cell 6, after `resample('15min').mean()`
- Cell 10 (Step 2: Load Solar Radiation Data), before `reindex()`

### Action Required
- Check all scripts that create datetime indexes from date+time combinations
- Check all scripts that use `resample()` operations
- Check all scripts that use `reindex()` operations
- Consider if duplicates should be aggregated (mean) instead of dropped
- Apply to scripts listed in section 3

---

## 6. Date Range Filtering - Boolean Mask

### Issue
Using `.loc[start_date:end_date]` requires exact timestamps to exist in the index. If the exact start/end timestamps don't exist, it raises `KeyError`.

### Fix Applied
Changed from:
```python
df_lastgang = df_lastgang.loc[start_date:end_date]
```

To:
```python
# Filter for analysis period (use boolean mask for more flexibility)
df_lastgang = df_lastgang[(df_lastgang.index >= start_date) & (df_lastgang.index <= end_date)]
```

### Location in Notebook
Cell 6 (Step 1: Load Power Consumption Data)

### Action Required
- Review all scripts that filter data by date range
- Consider if `.loc[]` slicing is appropriate or if boolean masks are more robust
- Apply to scripts listed in section 3

---

## 7. Resample Operation - Non-Numeric Columns

### Issue
When resampling to 15-minute intervals, pandas tried to calculate mean of non-numeric columns ('Datum', 'Uhrzeit'), causing `TypeError: Could not convert string '00:00' to numeric`.

### Fix Applied
Added before resampling:
```python
# Drop non-numeric columns (Datum, Uhrzeit) before resampling
df_lastgang = df_lastgang.drop(columns=['Datum', 'Uhrzeit'], errors='ignore')
df_lastgang = df_lastgang.resample('15min').mean()
```

### Location in Notebook
Cell 6 (Step 1: Load Power Consumption Data)

### Action Required
- Check all scripts that use `resample().mean()` or similar aggregation
- Ensure non-numeric columns are dropped or handled appropriately
- Apply to scripts listed in section 3

---

## 8. API Function Call - Parameter Names

### Issue
`fetch_spotmarket_prices()` function expects `start_time` and `end_time` (strings), but notebook was calling it with `start_date` and `end_date` (Timestamp objects), causing `TypeError: got an unexpected keyword argument 'start_date'`.

### Fix Applied
Changed from:
```python
df_prices = fetch_spotmarket_prices(
    start_date=start_date,
    end_date=end_date
)
```

To:
```python
df_prices = fetch_spotmarket_prices(
    start_time=start_date.strftime("%Y-%m-%d %H:%M:%S"),
    end_time=end_date.strftime("%Y-%m-%d %H:%M:%S")
)
```

### Location in Notebook
Cell 12 (Step 3: Load Spot Market Prices)

### Action Required
- Check all scripts that call `fetch_spotmarket_prices()` or `fetch_spotmarket_prices_from_api()`
- Verify parameter names and types match function signatures
- Files to check:
  - `run_48h_may_2024_analysis.py`
  - `run_8d_may_2024_analysis.py`
  - `run_full_year_2024_analysis.py`
  - `run_ecocool_emission_analysis.py`

---

## 9. Ruff Configuration Warning

### Issue
Ruff language server was trying to load a configuration file that extended a missing file, causing warnings.

### Fix Applied
Created `.pixi/envs/default/.ruff.toml` with minimal configuration to satisfy the reference.

### Files Modified
- `.pixi/envs/default/.ruff.toml` - Created minimal config

### Action Required
- This is a development environment issue, not critical for production
- Can be ignored or cleaned up later

---

## 10. CAMS Solar Data Units and Timezone Conversion

### Issue
The CAMS CSV file provides solar radiation data in Wh/m² (energy over 15-minute period) and in UTC timezone. The data needs to be converted to W/m² (power) and to local time (Europe/Berlin) for alignment with power consumption data.

### Fix Applied
The `read_cams_solar_radiation()` function in `utils/data_processing.py` performs two important conversions:

1. **Units Conversion (Wh/m² → W/m²)**:
   - CAMS CSV provides values in Wh/m² (energy accumulated over 15-minute period)
   - Function converts to W/m² (instantaneous power) by dividing by 0.25 hours
   - Example: 0.1200 Wh/m² → 0.48 W/m² (0.1200 ÷ 0.25 = 0.48)
   - The function correctly identifies the "Clear sky GHI" column (not TOA)
   - Verification: If TOA were used, we'd see ~2.386 W/m² (0.5965 Wh/m² ÷ 0.25), but we see 0.48 W/m², confirming correct column

2. **Timezone Conversion (UTC → Europe/Berlin)**:
   - CAMS data timestamps are in UTC (Universal Time)
   - Function converts to Europe/Berlin timezone (UTC+1 in winter, UTC+2 in summer)
   - This ensures proper alignment with local power usage data
   - Example: 2024-05-01 03:45 UTC → 2024-05-01 05:45 Berlin time (May = UTC+2)
   - When checking timestamps in the loaded data, use Berlin time, not UTC

### Files Modified
- `utils/data_processing.py` - `read_cams_solar_radiation()` function
- `notebooks/bako_manual_analysis.ipynb` - Added explanatory comments

### Code Location
- Function: `utils/data_processing.py::read_cams_solar_radiation()`
- Lines: 287-298 (units conversion), 226-236 (timezone conversion)

### Action Required
- ✅ Function already handles conversions correctly
- ✅ Comments added to notebook for clarity
- When using CAMS data in other scripts, ensure timezone and units are understood

---

## Summary of Files That May Need Updates

### Scripts to Review:
1. `run_48h_may_2024_analysis.py`
2. `run_48h_may_2024_analysis_smoothed.py`
3. `run_8d_may_2024_analysis.py`
4. `run_8d_may_2024_analysis_smoothed.py`
5. `run_full_year_2024_analysis.py`
6. `run_full_year_2024_analysis_smoothed.py`
6. `run_ecocool_emission_analysis.py`

### Utility Functions to Consider Creating:
1. `parse_european_date()` - Handle DD.MM.YYYY format consistently
2. `parse_time_to_timedelta()` - Handle HH:MM format consistently
3. `remove_duplicate_timestamps()` - Handle duplicate timestamps in indexes
4. `filter_date_range()` - Robust date range filtering

### Configuration:
- ✅ `config.py` - Already updated with missing variables

---

## Testing Checklist

When applying these fixes to main scripts, verify:

- [ ] Date parsing works with DD.MM.YYYY format
- [ ] Time parsing works with HH:MM format
- [ ] No duplicate timestamps in indexes
- [ ] Date range filtering works even if exact timestamps don't exist
- [ ] Resample operations don't fail on non-numeric columns
- [ ] API calls use correct parameter names and types
- [ ] All imports from config.py succeed
- [ ] Scripts run successfully with pixi environment

---

## Notes

- Most fixes are related to data format handling (dates, times) which may vary by data source
- Consider creating utility functions to centralize these fixes
- Test with actual data files to ensure fixes work in practice
- Some fixes may need adjustment based on actual data characteristics

