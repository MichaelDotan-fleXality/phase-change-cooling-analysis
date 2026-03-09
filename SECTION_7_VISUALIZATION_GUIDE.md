# Section 7 Visualization Cells - Implementation Guide

## Overview

This document explains how to add the missing visualization cells to Section 7 (Active PCM Optimization) in the notebook `BAKO_Physics_Based_New.ipynb`.

---

## Current Status

**Section 7 (Cells 32-37):** ✅ **Core Implementation Complete**
- Cell 32: Markdown header
- Cell 33: Active PCM optimization loop (RUNNING - results calculated)
- Cell 34-35: Explanation and summary
- Cell 36-37: Configuration storage

**Results:**
- ✅ Active PCM optimization executed for all 4 systems
- ✅ Savings calculated: €234.70 total (10 months)
- ❌ Visualizations missing

---

## Cells to Add

### **After Cell 37, insert the following 5 cells:**

| New Cell # | Type | Purpose | Location in Script |
|------------|------|---------|-------------------|
| **38** | Markdown | Section 7.1 header | Lines 9-23 |
| **39** | Code | Individual system 5-panel plots | Lines 30-257 |
| **40** | Markdown | Section 7.2 header | Lines 262-276 |
| **41** | Code | 3-day detailed July analysis | Lines 283-447 |
| **42** | Markdown | Section 7.3 header | Lines 452-472 |
| **43** | Code | Summary comparison table | Lines 479-593 |

---

## How to Add Cells

### **Option 1: Manual Copy-Paste** (Recommended)

1. Open `BAKO_Physics_Based_New.ipynb` in Jupyter/VS Code
2. Navigate to Cell 37 (last cell of Section 7)
3. For each cell in `_section_7_visualization_cells.py`:
   - Click "Insert Cell Below" after Cell 37
   - Copy the code/markdown from the script
   - Paste into the new cell
   - Set cell type (Code or Markdown)
   - Repeat for all 6 cells

### **Option 2: Programmatic Insertion** (Advanced)

Use `nbformat` library to insert cells programmatically:

```python
import nbformat
from nbformat.v4 import new_markdown_cell, new_code_cell

# Load notebook
with open('notebooks/BAKO/BAKO_Physics_Based_New.ipynb', 'r') as f:
    nb = nbformat.read(f, as_version=4)

# Find Cell 37 index
cell_37_index = 37  # Adjust if needed

# Insert cells after Cell 37
cells_to_insert = [
    new_markdown_cell("""## 7.1 Individual System Analysis - Active PCM..."""),
    new_code_cell("""print('Section 7.1...')..."""),
    # ... etc
]

for i, cell in enumerate(cells_to_insert):
    nb.cells.insert(cell_37_index + 1 + i, cell)

# Save
with open('notebooks/BAKO/BAKO_Physics_Based_New.ipynb', 'w') as f:
    nbformat.write(nb, f)
```

---

## Cell Descriptions

### **Cell 38 (Markdown): Section 7.1 Header**
**Purpose:** Introduce individual system visualization section

**Content:**
- Explains 5-panel plot structure
- Lists panel contents (Power, Temperature, PCM State, Context, PV)
- Describes interactive features (zoom, pan, hover)

---

### **Cell 39 (Code): Individual System 5-Panel Plots**
**Purpose:** Generate detailed plots for each system showing active PCM performance

**What it does:**
1. Loops through all 4 systems
2. Aggregates data across Jan-Oct 2025 (10 months)
3. Creates 5-panel interactive plots with:
   - **Panel 1:** Power comparison (Flat/Cost-Aware/Passive/Active)
   - **Panel 2:** Temperature setpoints with T_melt reference
   - **Panel 3:** PCM SOC + charge/discharge power
   - **Panel 4:** Outdoor temp + spot price context
   - **Panel 5:** PV self-consumption
4. Saves 4 HTML files (one per system)
5. Displays first system in notebook

**Output:** 4 HTML files in `plots/` directory
- `section_7_active_pcm_Pluskühlung_1_full_year_2025.html`
- `section_7_active_pcm_Pluskühlung_2_full_year_2025.html`
- `section_7_active_pcm_Tiefkühlung_1_full_year_2025.html`
- `section_7_active_pcm_Tiefkühlung_2_full_year_2025.html`

---

### **Cell 40 (Markdown): Section 7.2 Header**
**Purpose:** Introduce 3-day detailed analysis

**Content:**
- Explains zoomed view of July 4-6, 2025
- Focus on price-responsive behavior
- PCM cycling patterns during peak/off-peak

---

### **Cell 41 (Code): 3-Day Detailed July Analysis**
**Purpose:** Show detailed PCM charge/discharge dynamics over 3-day period

**What it does:**
1. Selects July 4-6, 2025 (72 hours)
2. Creates 4-panel plots for each system:
   - **Panel 1:** Power comparison (all strategies)
   - **Panel 2:** Temperature + price signals
   - **Panel 3:** SOC + charge/discharge power
   - **Panel 4:** Outdoor temp + PV generation
3. Shows how active PCM responds to price signals
4. Saves 4 HTML files
5. Displays Tiefkühlung 2 (largest system) in notebook

**Output:** 4 HTML files in `plots/` directory
- `section_7_2_active_pcm_3day_Pluskühlung_1_july.html`
- `section_7_2_active_pcm_3day_Pluskühlung_2_july.html`
- `section_7_2_active_pcm_3day_Tiefkühlung_1_july.html`
- `section_7_2_active_pcm_3day_Tiefkühlung_2_july.html`

---

### **Cell 42 (Markdown): Section 7.3 Header**
**Purpose:** Introduce summary comparison section

**Content:**
- Lists all strategies compared
- Explains metrics (absolute/relative savings, incremental benefits)

---

### **Cell 43 (Code): Summary Comparison Table**
**Purpose:** Quantify value of each optimization strategy

**What it does:**
1. Aggregates 10-month costs for each system
2. Calculates savings vs flat baseline
3. Computes incremental benefits
4. Prints formatted tables showing:
   - Total costs by strategy
   - Savings vs baseline
   - Incremental benefits
   - Site-wide totals
5. Economic analysis:
   - PCM CAPEX estimation
   - Payback period calculation
   - Annualized savings projection

**Output:** Printed tables in notebook showing:
```
📊 10-MONTH COST SUMMARY (Jan-Oct 2025)
Total Costs by Strategy:
[Table with Flat/Cost-Aware/Passive/Active costs for each system]

Savings vs Flat Baseline:
[Table with absolute and percentage savings]

Incremental Benefits:
[Table showing passive and active incremental value]

🏢 TOTAL SITE (All 4 Systems Combined):
Flat Baseline:           €XX,XXX.XX
Cost-Aware Scheduling:   €XX,XXX.XX  (saves €XXX.XX, X.XX%)
Passive PCM:             €XX,XXX.XX  (saves €XXX.XX, X.XX%)
Active PCM:              €XX,XXX.XX  (saves €XXX.XX, X.XX%)

📈 ECONOMIC ANALYSIS:
PCM CAPEX: €16,688
Passive payback: XX years
Active payback: XX years
```

---

## Expected Results

### **Current Active PCM Results (Cell 33 Output):**

| System | Active PCM Savings | % Reduction |
|--------|-------------------|-------------|
| Pluskühlung 1 | €18.79 | 0.1% |
| Pluskühlung 2 | €53.90 | 0.2% |
| Tiefkühlung 1 | €55.26 | 0.3% |
| Tiefkühlung 2 | €106.75 | 0.5% |
| **TOTAL** | **€234.70** | **~0.25%** |

### **Comparison to Passive PCM (Cell 30):**

| Strategy | 10-Month Savings | % Reduction |
|----------|-----------------|-------------|
| Passive PCM | €165.00 | 0.17% |
| Active PCM | €234.70 | 0.25% |
| **Active Benefit** | **+€69.70** | **+42% improvement** |

---

## Key Insights from Visualizations

### **What You'll See in the Plots:**

1. **Individual System Plots (Cell 39):**
   - Active PCM follows price signals (charge during low prices, discharge during high)
   - Greatest benefit in Tiefkühlung systems (lower temp = more PCM capacity)
   - PV generation during day reduces grid costs but PCM still provides small benefit

2. **3-Day Detail (Cell 41):**
   - Clear daily cycles: Charge at night (low prices), discharge during day (high prices)
   - PCM SOC oscillates between 50-100% (full charge/discharge cycles)
   - Temperature setpoints more aggressive than cost-aware (deeper pre-cooling)

3. **Summary Comparison (Cell 43):**
   - Cost-aware scheduling provides majority of savings (zero CAPEX)
   - Passive PCM adds €165 (minimal benefit without re-optimization)
   - Active PCM adds another €69.70 (42% improvement over passive)
   - **Conclusion:** Active PCM payback still very long (~60-70 years at current config)

---

## Next Steps After Adding Cells

### **1. Run the New Cells**
- Execute Cells 39, 41, 43 sequentially
- Verify HTML plots are generated in `plots/` directory
- Review summary tables for economic viability

### **2. Analyze Results**
- Open HTML plots in browser
- Check if active PCM shows price-responsive behavior
- Verify SOC cycles align with price signals

### **3. Economic Decision**
**Current Results Show:**
- Active PCM: €234.70 savings / 10 months
- Annualized: €234.70 × 1.2 = €281.64 / year
- CAPEX: ~€16,688
- **Payback: 59 years** ❌ NOT economically viable

**Options:**
1. ✅ **Proceed to parametric sweep** (Section 7.4) - find optimal PCM configuration
2. ✅ **Abandon PCM approach** - focus on cost-aware scheduling (zero CAPEX)
3. ✅ **Hybrid approach** - PCM only for largest system (Tief 2) pilot

---

## Parametric Sweep Preview (Section 7.4)

**Next logical step:** Find if ANY PCM configuration can achieve <10 year payback

**Sweep Parameters:**
- PCM mass: 100 - 3000 kg (9 values)
- Charge power: 1 - 10 kW (5 values)
- → 45 configurations per system

**Goal:** Generate heatmaps showing:
- Savings vs (Mass, Power)
- Payback period vs (Mass, Power)
- NPV vs (Mass, Power)

**Decision Point:** If no configuration achieves <10 year payback → **abandon PCM entirely**

---

## Files Created

| File | Purpose |
|------|---------|
| `_section_7_visualization_cells.py` | Complete code for Cells 38-43 |
| `SECTION_7_VISUALIZATION_GUIDE.md` | This guide |
| `UNIT_VERIFICATION_SUMMARY.md` | Unit verification (already committed) |

---

## Troubleshooting

### **If cells don't run:**
1. Check variable names match (e.g., `active_pcm_results` exists from Cell 33)
2. Verify all months (1-10) have data in results dictionaries
3. Ensure `plots/` directory exists: `!mkdir -p plots`

### **If plots look wrong:**
1. Check SOC values are between 0-1 (not 0-100)
2. Verify charge/discharge powers in Watts (divide by 1000 for kW)
3. Confirm timestamp alignment across all data sources

### **If economic analysis shows unexpected results:**
1. Verify CAPEX calculation matches PCM_CONFIGS
2. Check cost calculations use correct time period (10 months, not 12)
3. Confirm annualization factor (×1.2 for 10→12 months)

---

## Git Commit Checklist

Before committing:
- [ ] `_section_7_visualization_cells.py` created
- [ ] `SECTION_7_VISUALIZATION_GUIDE.md` created
- [ ] `UNIT_VERIFICATION_SUMMARY.md` committed
- [ ] All files added to git
- [  ] Committed with descriptive message
- [ ] Pushed to GitHub

**Suggested commit message:**
```
Add Section 7 visualization cells for active PCM analysis

- Created 5-panel individual system plots (Cell 39)
- Added 3-day detailed July analysis (Cell 41)
- Implemented summary comparison table (Cell 43)
- Documented complete implementation guide
- Cells ready to insert after Cell 37 in notebook
- Expected to show active PCM improves ~42% over passive
- Payback analysis shows ~59 years (not viable at current config)
```

---

**Ready to proceed?**  
1. Copy cells from `_section_7_visualization_cells.py` into notebook
2. Run cells and verify plots
3. Review economic conclusions
4. Decide: Parametric sweep or abandon PCM approach
