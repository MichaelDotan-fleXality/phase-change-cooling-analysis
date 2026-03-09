# UA_pcm Determination Guide

## What is UA_pcm?

UA_pcm is the **heat transfer coefficient** for the PCM heat exchanger, measured in W/K (Watts per Kelvin).

It determines how quickly heat can be transferred between the cooling system and the PCM storage.

## Physical Formula

```
UA_pcm = h × A
```

Where:
- **h** = convective heat transfer coefficient (W/m²·K)
- **A** = heat exchanger surface area (m²)

##Physical Basis

### Heat Transfer Coefficient (h)

Typical values for different configurations:

| Configuration | h (W/m²·K) | Notes |
|---------------|------------|-------|
| Natural convection (tank) | 5-25 | Poor, slow charging |
| Forced convection (coils) | 50-200 | Standard design |
| Plate heat exchanger | 200-500 | Good design |
| Enhanced fins/plates | 500-1000 | High-performance |

### Heat Exchanger Area (A)

For PCM thermal storage **specific area** (area per kg of PCM):

| PCM Type | Specific Area (m²/100kg) | Notes |
|----------|--------------------------|-------|
| Bulk tank with coils | 0.3-0.5 | Low |
| Panel/plate encapsulation | 0.8-1.5 | Medium |
| Enhanced (fins/microchannels) | 2.0-4.0 | High |

## Calculation Examples

### Example 1: Tiefkühlung 1 (1185 kg, Standard Design)

```python
# System: Tiefkühlung 1
m_pcm = 1185  # kg
P_chg_max = 3000  # W

# Assumption: Plate encapsulation with forced convection
h = 200  # W/m²·K (moderate forced convection)
specific_area = 1.2  # m²/100kg (plate design)
A = (m_pcm / 100) × specific_area = 11.85 × 1.2 = 14.2 m²

# UA value:
UA_pcm = h × A = 200 × 14.2 = 2840 W/K
```

**For conservative estimate (safer):** UA_pcm = 1000-1500 W/K  
**For typical estimate:** UA_pcm = 2000-3000 W/K  
**For optimistic estimate:** UA_pcm = 3000-5000 W/K

### Example 2: Pluskühlung 1 (500 kg Water/Ice)

```python
m_pcm = 500  # kg  
P_chg_max = 3000  # W

# Water/ice allows better heat transfer (higher thermal conductivity)
h = 300  # W/m²·K (better than organics)
specific_area = 1.5  # m²/100kg
A = (500 / 100) × 1.5 = 7.5 m²

UA_pcm = 300 × 7.5 = 2250 W/K
```

## Cross-Check with Maximum Power

The UA_pcm should be compatible with the maximum charging power:

```python
# Maximum temperature difference during charging:
dT_max = |T_melt - T_set_min|

# For Tiefkühlung: T_melt = -21°C, T_set_min = -25°C
dT_max = |-21 - (-25)| = 4 K

# Maximum heat transfer rate:
Q_max = UA_pcm × dT_max

# This should be >= P_chg_max for the rating to make sense
# If Q_max < P_chg_max, then UA_pcm limits you before power limit
```

### Example Check:
```python
# Tiefkühlung 1:
UA_pcm = 2000  # W/K (moderate design)
dT_max = 4  # K
Q_max = 2000 × 4 = 8000 W

# P_chg_max = 3000 W
# Since Q_max (8000 W) > P_chg_max (3000 W), the power limit is active
# This is correct - power electronics limit before heat transfer
```

If UA_pcm is too low:
```python
UA_pcm = 500  # W/K (poor design)
Q_max = 500 × 4 = 2000 W

# P_chg_max = 3000 W  
# But heat exchanger can only deliver Q_max = 2000 W
# Effective limit = min(2000, 3000) = 2000 W
```

## Current Problem Diagnosis

**Your current model uses UA_pcm = 500 W/K**

For Tiefkühlung 1 with 1185 kg PCM:
- This gives specific UA = 500 / 11.85 = **42 W/K per 100kg**
- This implies: h × A/100kg = 42
- With h = 200: A = 0.21 m²/100kg (very poor design)
- With h = 50: A = 0.84 m²/100kg (below average)

**This is possible but represents a LOW-PERFORMANCE heat exchanger.**

## Why You're Seeing 148 kW Peaks

The extreme peaks are NOT from UA_pcm being too high.The problem is in the **electrical power calculation**.

Check your code in `power_from_setpoint_with_realistic_pcm`:

```python
# WRONG (causes extreme peaks):
P_el = Q_cool / COP  # Only cooling load
P_el += Q_pcm_charge  # ADD PCM charging on top (not through COP)

# CORRECT (physically realistic):
P_el = (Q_cool + Q_pcm_charge) / COP  # Total thermal load divided by COP
```

##Recommended UA_pcm Values

Based on realistic heat exchanger design:

| System | Mass (kg) | Conservative UA | Typical UA | Optimistic UA |
|--------|-----------|-----------------|------------|---------------|
| Pluskühlung 1 | 500 | 750 W/K | 1500 W/K | 2500 W/K |
| Pluskühlung 2 | 1000 | 1500 W/K | 2500 W/K | 4000 W/K |
| Tiefkühlung 1 | 1185 | 1200 W/K | 2000 W/K | 3500 W/K |
| Tiefkühlung 2 | 800 | 1000 W/K | 1800 W/K | 3000 W/K |

**For your current analysis, I recommend:**
- Use **UA_pcm = 2000-2500 W/K** for Tiefkühlung systems
- Use **UA_pcm = 1500-2000 W/K** for Pluskühlung systems

This represents **typical commercial PCM heat exchanger performance**.

## How to Validate

1. **Run simulation with different UA values**
2. **Check that Q_pcm ≤ min(UA_pcm × dT, P_chg_max)**  
3. **Verify peak power is reasonable** (<15 kW for 8 kW system)
4. **Compare to vendor data** if available

## References

- Heat Transfer Handbook (Bejan & Kraus, 2003)
- PCM heat exchangers: Typical designs achieve h = 100-400 W/m²·K
- Commercial PCM vendors (Sunamp, PCM Products Ltd): Specify achievable charge/discharge rates
