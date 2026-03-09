# Unit Verification Summary - BÄKO PCM Analysis

## Verification Date
March 9, 2026

---

## 1. Spot Price Data Units

### **Input Source**
- **Source:** EPEX Day-Ahead Spot Market
- **API:** `utils.api_data_fetcher.fetch_spotmarket_prices()`
- **Units:** **€/MWh** (Euros per Megawatt-hour)
- **Frequency:** Hourly data (resampled to 15-minute)

### **Resampling Method**
```python
SPOT_PRICE_RESAMPLE_METHOD = 'ffill'  # Forward-fill
```
- Hourly prices → 15-minute intervals
- Each hour's price fills all 4×15-min intervals
- Alternative: 'interpolate' for linear interpolation

### **Typical Range**
- **Expected:** 0-200 €/MWh
- **Warning trigger:** > 200 €/MWh (may indicate unit error)
- **Actual (BÄKO 2025):** Varies by season/hour

---

## 2. Cost Calculation Units

### **2.1 Energy Cost Calculation**

**Function:**
```python
def calc_energy_cost(P_el_kW, prices_EUR_MWh, dt_h=0.25):
    """Total energy cost = spot cost + fixed surcharge cost."""
    spot = float(np.sum(P_el_kW * dt_h * prices_EUR_MWh / 1000.0))
    surcharge = float(np.sum(P_el_kW * dt_h)) * FIXED_SURCHARGE_EUR_KWH
    return spot + surcharge
```

**Unit Analysis:**

#### **Spot Cost Component:**
```
P_el_kW × dt_h × prices_EUR_MWh / 1000.0
```

**Step-by-step:**
1. `P_el_kW` → **kW** (electrical power)
2. `dt_h = 0.25` → **hours** (15 minutes = 0.25 h)
3. `P_el_kW × dt_h` → **kWh** (energy consumed)
4. `prices_EUR_MWh` → **€/MWh** (spot price)
5. `kWh × (€/MWh)` → **kWh·€/MWh**
6. Conversion: `/ 1000.0` → **kWh·€/MWh × (1 MWh/1000 kWh)** = **€** ✅

**Result:** spot cost in **€** (euros)

#### **Surcharge Component:**
```
np.sum(P_el_kW × dt_h) × FIXED_SURCHARGE_EUR_KWH
```

**Step-by-step:**
1. `np.sum(P_el_kW × dt_h)` → **kWh** (total energy)
2. `FIXED_SURCHARGE_EUR_KWH = 0.07836` → **€/kWh** (7.836 ct/kWh)
3. `kWh × (€/kWh)` → **€** ✅

**Result:** surcharge in **€** (euros)

#### **Total Energy Cost:**
```
total_energy_cost = spot_cost + surcharge
```
**Unit:** **€** (euros) ✅

---

### **2.2 Demand Cost Calculation**

**Function:**
```python
demand_cost = max(P_site_total) * DEMAND_EUR_KW_MONTH
```

**Unit Analysis:**
1. `max(P_site_total)` → **kW** (peak power)
2. `DEMAND_EUR_KW_MONTH = 11.03` → **€/(kW·month)**
3. `kW × €/(kW·month)` → **€/month** ✅

**Result:** demand cost in **€ per month** ✅

---

### **2.3 Total Monthly Cost**

**Calculation:**
```python
total_cost = energy_cost + demand_cost
```

**Units:**
- `energy_cost` → **€** (for the month)
- `demand_cost` → **€/month** (monthly charge)
- `total_cost` → **€** (total monthly cost) ✅

---

## 3. Configuration Parameters

### **Tariff Structure (Derived from June+July 2025 Invoices)**

| Parameter | Value | Unit | Notes |
|-----------|-------|------|-------|
| **Fixed Surcharge** | 7.836 | ct/kWh | Grid fees + levies + margin |
| **Fixed Surcharge** | 0.07836 | €/kWh | Same value in euros |
| **Demand Charge (Monthly)** | 11.03 | €/kW/month | Peak power billing |
| **Demand Charge (Annual)** | 132.32 | €/kW/year | 11.03 × 12 months |

**Validation:**
- 11.03 €/(kW·month) × 12 months = **132.36 €/(kW·year)** 
- Configured: **132.32 €/(kW·year)**
- **Discrepancy:** 0.04 € (negligible rounding)

---

## 4. Power and Energy Units

### **Power Variables**
| Variable | Unit | Description |
|----------|------|-------------|
| `P_el_kW` | kW | Electrical power consumed by cooling system |
| `P_grid` | kW | Grid power (utility purchases) |
| `P_site_total` | kW | Total site consumption (grid + PV) |
| `P_cooling` | kW | Cooling power for specific system |
| `P_pv_self_consumed` | kW | PV generation used on-site |

### **Energy Variables**
| Variable | Unit | Calculation |
|----------|------|-------------|
| `energy_kwh` | kWh | `np.sum(P_cooling) * 0.25` |
| `grid_energy_kwh` | kWh | `np.sum(P_grid) * 0.25` |
| `dt_h` | hours | 0.25 (15 minutes) |

---

## 5. Cost Component Breakdown

### **Example Calculation**

**Input:**
- Power: `P_grid = [10, 12, 11, 13]` kW (4 timesteps)
- Spot price: `price = [50, 60, 55, 65]` €/MWh
- Time step: `dt_h = 0.25` hours (15 min)

**Step 1: Energy**
```
Energy = sum([10, 12, 11, 13]) × 0.25 = 46 × 0.25 = 11.5 kWh
```

**Step 2: Spot Cost**
```
Spot = (10×0.25×50 + 12×0.25×60 + 11×0.25×55 + 13×0.25×65) / 1000
     = (125 + 180 + 151.25 + 211.25) / 1000
     = 667.5 / 1000
     = 0.6675 €
```

**Step 3: Surcharge**
```
Surcharge = 11.5 kWh × 0.07836 €/kWh = 0.90114 €
```

**Step 4: Total Energy Cost**
```
Energy Cost = 0.6675 + 0.90114 = 1.56864 €
```

**Step 5: Demand Cost**
```
Peak = max([10, 12, 11, 13]) = 13 kW
Demand Cost = 13 kW × 11.03 €/kW = 143.39 €
```

**Step 6: Total Cost**
```
Total = 1.56864 + 143.39 = 144.96 € for this period
```

---

## 6. Critical Power Basis

### **Energy Cost vs Demand Cost**

| Cost Component | Power Basis | Reasoning |
|----------------|-------------|-----------|
| **Energy Cost** (spot + surcharge) | `P_grid_only` | Only grid purchases are billed for energy |
| **Demand Cost** (peak charge) | `P_site_total` | Includes PV self-consumption in peak calculation |

### **Why This Matters**

**Energy Cost:**
- Utility only bills for **grid power** (what they deliver)
- PV self-consumption is **free energy** (no spot price cost, no surcharge)
- Formula: `Energy Cost = f(P_grid)`

**Demand Cost:**
- Based on **total site consumption** (grid + PV)
- Utility infrastructure must handle **peak load** regardless of PV contribution
- Formula: `Demand Cost = f(max(P_site_total))`

### **Example Impact**

**Scenario:**
- Grid power: 50 kW
- PV self-consumption: 20 kW
- Total site: 70 kW

**Energy cost calculation:**
- Uses `P_grid = 50 kW` → Lower energy cost ✅

**Demand cost calculation:**
- Uses `P_site_total = 70 kW` → Higher demand charge ✅

This reflects real tariff structure where PV reduces energy costs but not demand charges.

---

## 7. Validation Checks

### **✅ Unit Consistency Checks**

| Check | Status | Notes |
|-------|--------|-------|
| Spot price in €/MWh | ✅ Pass | Correctly converts to €/kWh internally |
| Energy cost in € | ✅ Pass | Division by 1000 correctly converts MWh→kWh |
| Surcharge in € | ✅ Pass | 0.07836 €/kWh applied correctly |
| Demand cost in €/month | ✅ Pass | 11.03 €/kW/month multiplied by peak kW |
| Total cost in € | ✅ Pass | Sum of energy + demand costs |
| Time step (dt_h) | ✅ Pass | 0.25 hours = 15 minutes |
| Power in kW | ✅ Pass | All power variables consistently in kW |
| Energy in kWh | ✅ Pass | Power × 0.25 hours correctly yields kWh |

### **✅ Calculation Verification**

**Energy Cost Formula:**
```
spot_cost = Σ(P_grid_kW × 0.25h × price_EUR_MWh) / 1000  → €
surcharge = Σ(P_grid_kW × 0.25h) × 0.07836 €/kWh         → €
energy_cost = spot_cost + surcharge                       → €
```
**Status:** ✅ **CORRECT**

**Demand Cost Formula:**
```
demand_cost = max(P_site_total_kW) × 11.03 €/kW/month    → €/month
```
**Status:** ✅ **CORRECT**

---

## 8. Potential Issues to Monitor

### **⚠️ Warning Triggers**

1. **Spot Price Out of Range**
   - If `price > 200 €/MWh` → Check for unit conversion errors
   - If `price > 1000` → Likely in **ct/kWh** instead of **€/MWh**

2. **Negative Costs**
   - Negative spot prices are **valid** (surplus renewable energy)
   - Can occur during high wind/solar periods
   - System should handle correctly (reduces total cost)

3. **Extremely High Energy Costs**
   - If energy cost >> demand cost → Check for double-counting
   - Verify `P_grid` used (not `P_site_total`) for energy cost

4. **Demand Cost Dominates**
   - Expected for BÄKO (industrial tariff)
   - Demand ~90% of total cost is normal
   - Validates focus on peak shaving strategies

---

## 9. Summary of Key Formulas

### **Complete Cost Calculation Chain**

```python
# Input data
P_grid_kW           # Grid power [kW] - array
P_site_total_kW     # Total site power [kW] - array
prices_EUR_MWh      # Spot prices [€/MWh] - array
dt_h = 0.25         # Time step [hours]

# Constants
FIXED_SURCHARGE = 0.07836      # [€/kWh]
DEMAND_CHARGE = 11.03          # [€/kW/month]

# Calculate energy (kWh)
energy_kWh = np.sum(P_grid_kW) * dt_h

# Calculate spot cost (€)
spot_cost_EUR = np.sum(P_grid_kW * dt_h * prices_EUR_MWh) / 1000.0

# Calculate surcharge (€)
surcharge_EUR = energy_kWh * FIXED_SURCHARGE

# Total energy cost (€)
energy_cost_EUR = spot_cost_EUR + surcharge_EUR

# Demand cost (€/month)
peak_kW = np.max(P_site_total_kW)
demand_cost_EUR_month = peak_kW * DEMAND_CHARGE

# Total monthly cost (€)
total_cost_EUR = energy_cost_EUR + demand_cost_EUR_month
```

---

## 10. Conclusions

### **✅ All Units Are Correct**

1. **Spot prices** in **€/MWh** → correctly converted in calculations
2. **Energy costs** properly calculated in **€**
3. **Demand costs** properly calculated in **€/month**
4. **Power-to-energy conversion** using correct time step (0.25 h)
5. **Grid vs site power** correctly applied for different cost components

### **✅ No Unit Conversion Errors Found**

The cost calculation functions implement proper unit conversions:
- `/ 1000.0` correctly converts MWh to kWh in spot cost
- Time step `dt_h = 0.25` correctly represents 15 minutes
- All costs output in euros (€)

### **✅ Implementation Matches Documentation**

The [PCM_POTENTIAL_ANALYSIS_DOCUMENTATION.md](PCM_POTENTIAL_ANALYSIS_DOCUMENTATION.md) accurately describes the cost calculation methodology.

---

## 11. Recommendations

### **✅ Current Implementation**
**No changes needed** - all units and calculations are correct.

### **📝 Optional Enhancements**

1. **Add unit assertions** in code for safety:
   ```python
   assert 0 < np.max(prices_EUR_MWh) < 500, "Spot prices out of expected range"
   assert dt_h == 0.25, "Time step should be 0.25 hours (15 min)"
   ```

2. **Add unit documentation** in function docstrings:
   ```python
   def calc_energy_cost(P_el_kW, prices_EUR_MWh, dt_h=0.25):
       """
       Calculate total energy cost.
       
       Parameters:
       - P_el_kW: Power [kW]
       - prices_EUR_MWh: Spot prices [€/MWh]
       - dt_h: Time step [hours], default 0.25 (15 min)
       
       Returns:
       - Total energy cost [€]
       """
   ```

3. **Create unit test** for cost calculations:
   ```python
   # Test case: 1 kW for 1 hour at 100 €/MWh
   P = np.array([1.0, 1.0, 1.0, 1.0])  # 4×15min = 1 hour
   price = np.array([100, 100, 100, 100])  # €/MWh
   cost = calc_energy_cost(P, price, dt_h=0.25)
   expected = 1.0 * 100 / 1000 + 1.0 * 0.07836  # = 0.1 + 0.07836 = 0.17836 €
   assert abs(cost - expected) < 1e-6
   ```

---

**Document Status:** ✅ VERIFIED - All cost calculations use correct units
**Last Updated:** March 9, 2026
**Next Review:** After any tariff structure changes
