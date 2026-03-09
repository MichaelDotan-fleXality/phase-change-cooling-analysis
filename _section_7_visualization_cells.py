# Section 7: Active PCM Visualization Cells
# Insert these cells after Cell 37 in BAKO_Physics_Based_New.ipynb

# =============================================================================
# CELL 38 (Markdown): Visualization Header
# =============================================================================
"""
## 7.1 Individual System Analysis - Active PCM

Detailed 5-panel interactive plots showing active PCM performance for each system over the full Jan-Oct 2025 period.

**Panels:**
1. **Power Consumption**: Comparison of Flat baseline, Cost-aware, Passive PCM, and Active PCM
2. **Temperature**: Optimized schedules for active PCM charge/discharge  
3. **PCM State**: State of Charge (SOC) showing charge/discharge cycles
4. **Context**: Outdoor temperature and spot price signals
5. **PV Generation**: Solar contribution to site consumption

**Interactive Features:**
- Synchronized zoom/pan across all panels
- Shared x-axis for time alignment
- Hover for detailed values
- Legend toggle to focus on specific strategies
"""

# =============================================================================
# CELL 39 (Code): Individual System 5-Panel Plots
# =============================================================================
print('Section 7.1: Generating Active PCM Individual System Visualizations')
print('='*70)

import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Create individual system plots for active PCM
for sys_name in SYSTEM_NAMES:
    print(f'\nCreating plot for {sys_name}...')
    
    # Collect data across all months (Jan-Oct)
    timestamps_all = []
    
    # Flat baseline
    P_cooling_flat = []
    T_flat = []
    
    # Cost-aware (unconstrained)
    P_cooling_uncon = []
    T_uncon = []
    
    # Passive PCM
    P_cooling_passive = []
    SOC_passive = []
    
    # Active PCM
    P_cooling_active = []
    T_active = []
    SOC_active = []
    Q_chg_active = []
    Q_dis_active = []
    
    # Context
    T_out_all = []
    price_all = []
    pv_all = []
    
    for m in range(1, 11):  # Jan-Oct 2025
        mdata = monthly_data[m]
        idx = mdata['idx']
        
        # Extend timestamps
        timestamps_all.extend(idx)
        
        # Flat baseline
        flat = flat_baseline[sys_name][m]
        P_cooling_flat.extend(flat['P_cooling'])
        T_flat.extend(flat['T_set'])
        
        # Unconstrained cost-aware
        uncon = uncon_results[sys_name][m]
        P_cooling_uncon.extend(uncon['P_cooling'])
        T_uncon.extend(uncon['T_set'])
        
        # Passive PCM
        passive = passive_pcm_results[sys_name][m]
        P_cooling_passive.extend(passive['P_el_kW'])
        SOC_passive.extend(passive['SOC'])
        
        # Active PCM
        active = active_pcm_results[sys_name][m]
        P_cooling_active.extend(active['P_el_kW'])
        T_active.extend(active['T_set'])
        SOC_active.extend(active['SOC'])
        Q_chg_active.extend(active.get('Q_pcm_charge', np.zeros(len(idx))))
        Q_dis_active.extend(active.get('Q_pcm_discharge', np.zeros(len(idx))))
        
        # Context
        T_out_all.extend(mdata['T_out'])
        price_all.extend(mdata['prices_arr'])
        pv_all.extend(mdata['P_pv_self_consumed'])
    
    # Create 5-panel figure
    fig = make_subplots(
        rows=5, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        subplot_titles=(
            '1. Power Consumption Comparison',
            '2. Temperature Setpoints',
            '3. PCM State of Charge',
            '4. Context: Outdoor Temperature & Spot Price',
            '5. PV Self-Consumption'
        ),
        specs=[
            [{"secondary_y": False}],
            [{"secondary_y": False}],
            [{"secondary_y": True}],   # SOC + charge/discharge power
            [{"secondary_y": True}],   # T_out + price
            [{"secondary_y": False}]
        ]
    )
    
    # -------------------------------------------------------------------------
    # Panel 1: Power Consumption
    # -------------------------------------------------------------------------
    fig.add_trace(go.Scatter(
        x=timestamps_all, y=P_cooling_flat,
        name='Flat Baseline',
        line=dict(color='gray', width=1),
        opacity=0.6,
        legendgroup='power'
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(
        x=timestamps_all, y=P_cooling_uncon,
        name='Cost-Aware',
        line=dict(color='blue', width=1.5),
        legendgroup='power'
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(
        x=timestamps_all, y=P_cooling_passive,
        name='Passive PCM',
        line=dict(color='orange', width=1.5),
        legendgroup='power'
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(
        x=timestamps_all, y=P_cooling_active,
        name='Active PCM',
        line=dict(color='green', width=2),
        legendgroup='power'
    ), row=1, col=1)
    
    # -------------------------------------------------------------------------
    # Panel 2: Temperature Setpoints
    # -------------------------------------------------------------------------
    fig.add_trace(go.Scatter(
        x=timestamps_all, y=T_flat,
        name='Flat T',
        line=dict(color='gray', width=1, dash='dot'),
        opacity=0.6,
        showlegend=False
    ), row=2, col=1)
    
    fig.add_trace(go.Scatter(
        x=timestamps_all, y=T_uncon,
        name='Cost-Aware T',
        line=dict(color='blue', width=1),
        showlegend=False
    ), row=2, col=1)
    
    fig.add_trace(go.Scatter(
        x=timestamps_all, y=T_active,
        name='Active PCM T',
        line=dict(color='green', width=2),
        showlegend=False
    ), row=3, col=1)
    
    # Add T_melt reference line
    T_melt = PCM_CONFIGS[sys_name]['T_melt_C']
    fig.add_hline(
        y=T_melt, line_dash="dash", line_color="red",
        annotation_text=f"T_melt = {T_melt}°C",
        annotation_position="right",
        row=2, col=1
    )
    
    # -------------------------------------------------------------------------
    # Panel 3: PCM State of Charge + Charge/Discharge Power
    # -------------------------------------------------------------------------
    # SOC on primary y-axis
    fig.add_trace(go.Scatter(
        x=timestamps_all, y=[s*100 for s in SOC_passive],
        name='Passive SOC',
        line=dict(color='orange', width=1),
        showlegend=False
    ), row=3, col=1, secondary_y=False)
    
    fig.add_trace(go.Scatter(
        x=timestamps_all, y=[s*100 for s in SOC_active],
        name='Active SOC',
        line=dict(color='green', width=2),
        showlegend=False
    ), row=3, col=1, secondary_y=False)
    
    # Charge/discharge power on secondary y-axis
    fig.add_trace(go.Scatter(
        x=timestamps_all, y=[q/1000 for q in Q_chg_active],
        name='Charging',
        line=dict(color='cyan', width=1),
        fill='tozeroy',
        showlegend=False
    ), row=3, col=1, secondary_y=True)
    
    fig.add_trace(go.Scatter(
        x=timestamps_all, y=[-q/1000 for q in Q_dis_active],
        name='Discharging',
        line=dict(color='red', width=1),
        fill='tozeroy',
        showlegend=False
    ), row=3, col=1, secondary_y=True)
    
    # -------------------------------------------------------------------------
    # Panel 4: Context (T_out + Spot Price)
    # -------------------------------------------------------------------------
    fig.add_trace(go.Scatter(
        x=timestamps_all, y=T_out_all,
        name='T_outdoor',
        line=dict(color='brown', width=1),
        showlegend=False
    ), row=4, col=1, secondary_y=False)
    
    fig.add_trace(go.Scatter(
        x=timestamps_all, y=price_all,
        name='Spot Price',
        line=dict(color='purple', width=1),
        showlegend=False
    ), row=4, col=1, secondary_y=True)
    
    # -------------------------------------------------------------------------
    # Panel 5: PV Generation
    # -------------------------------------------------------------------------
    fig.add_trace(go.Scatter(
        x=timestamps_all, y=pv_all,
        name='PV Self-Consumption',
        line=dict(color='gold', width=1),
        fill='tozeroy',
        showlegend=False
    ), row=5, col=1)
    
    # -------------------------------------------------------------------------
    # Layout configuration
    # -------------------------------------------------------------------------
    fig.update_yaxes(title_text="Power (kW)", row=1, col=1)
    fig.update_yaxes(title_text="Temp (°C)", row=2, col=1)
    fig.update_yaxes(title_text="SOC (%)", row=3, col=1, secondary_y=False)
    fig.update_yaxes(title_text="PCM Power (kW)", row=3, col=1, secondary_y=True)
    fig.update_yaxes(title_text="T_outdoor (°C)", row=4, col=1, secondary_y=False)
    fig.update_yaxes(title_text="Price (€/MWh)", row=4, col=1, secondary_y=True)
    fig.update_yaxes(title_text="PV (kW)", row=5, col=1)
    
    fig.update_xaxes(title_text="Date", row=5, col=1)
    
    fig.update_layout(
        height=1400,
        title_text=f"{sys_name}: Active PCM Performance (Jan-Oct 2025)",
        hovermode='x unified'
    )
    
    # Save HTML
    filename = f'plots/section_7_active_pcm_{sys_name.replace(" ", "_")}_full_year_2025.html'
    fig.write_html(filename)
    print(f'  ✓ Saved: {filename}')
    
    # Show first system only (to avoid notebook bloat)
    if sys_name == "Pluskühlung 1":
        fig.show()

print('\n' + '='*70)
print('✓ Section 7.1 complete: Individual system plots generated')
print(f'  4 HTML files saved in plots/ directory')

# =============================================================================
# CELL 40 (Markdown): 3-Day Detailed Analysis Header
# =============================================================================
"""
## 7.2 Detailed 3-Day Analysis: Active PCM Dynamics

Zoomed-in view of July 4-6, 2025 showing how active PCM responds to price signals.

**Focus:**
- Price-responsive charge/discharge behavior
- PCM cycling patterns during peak vs off-peak periods
- Impact on grid power vs cost-aware baseline
- SOC management and constraint handling
"""

# =============================================================================
# CELL 41 (Code): 3-Day Detailed Visualization
# =============================================================================
print('\nSection 7.2: Generating 3-Day Detailed Active PCM Analysis (July 4-6)')
print('='*70)

# Select 3-day period in July 2025 (peak summer period)
july_month = 7
july_data = monthly_data[july_month]
july_idx = july_data['idx']

# Find July 4-6, 2025 (72 hours = 3 days)
start_date = pd.Timestamp('2025-07-04 00:00:00')
end_date = pd.Timestamp('2025-07-07 00:00:00')
mask = (july_idx >= start_date) & (july_idx < end_date)

july_slice = july_idx[mask]
T_out_slice = july_data['T_out'][mask]
price_slice = july_data['prices_arr'][mask]
pv_slice = july_data['P_pv_self_consumed'][mask]

# Create figure for each system
for sys_name in SYSTEM_NAMES:
    print(f'\nCreating 3-day plot for {sys_name}...')
    
    # Get July data for this system
    uncon = uncon_results[sys_name][july_month]
    passive = passive_pcm_results[sys_name][july_month]
    active = active_pcm_results[sys_name][july_month]
    flat = flat_baseline[sys_name][july_month]
    
    # Slice to 3-day period
    P_flat_slice = flat['P_cooling'][mask]
    P_uncon_slice = uncon['P_cooling'][mask]
    P_passive_slice = passive['P_el_kW'][mask]
    P_active_slice = active['P_el_kW'][mask]
    
    T_uncon_slice = uncon['T_set'][mask]
    T_active_slice = active['T_set'][mask]
    
    SOC_passive_slice = passive['SOC'][mask]
    SOC_active_slice = active['SOC'][mask]
    
    Q_chg_slice = active.get('Q_pcm_charge', np.zeros(len(july_idx)))[mask]
    Q_dis_slice = active.get('Q_pcm_discharge', np.zeros(len(july_idx)))[mask]
    
    # Create 4-panel figure
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        subplot_titles=(
            '1. Power: Active PCM vs Baselines',
            '2. Temperature & Price Signals',
            '3. PCM State of Charge & Charge/Discharge',
            '4. Context: Outdoor Temp & PV Generation'
        ),
        specs=[
            [{"secondary_y": False}],
            [{"secondary_y": True}],
            [{"secondary_y": True}],
            [{"secondary_y": True}]
        ]
    )
    
    # Panel 1: Power comparison
    fig.add_trace(go.Scatter(
        x=july_slice, y=P_flat_slice,
        name='Flat Baseline',
        line=dict(color='gray', width=2, dash='dot'),
        opacity=0.7
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(
        x=july_slice, y=P_uncon_slice,
        name='Cost-Aware (no PCM)',
        line=dict(color='blue', width=2)
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(
        x=july_slice, y=P_passive_slice,
        name='Passive PCM',
        line=dict(color='orange', width=2)
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(
        x=july_slice, y=P_active_slice,
        name='Active PCM',
        line=dict(color='green', width=3)
    ), row=1, col=1)
    
    # Panel 2: Temperature setpoints + Price signals
    fig.add_trace(go.Scatter(
        x=july_slice, y=T_uncon_slice,
        name='Cost-Aware T',
        line=dict(color='blue', width=1.5)
    ), row=2, col=1, secondary_y=False)
    
    fig.add_trace(go.Scatter(
        x=july_slice, y=T_active_slice,
        name='Active PCM T',
        line=dict(color='green', width=2)
    ), row=2, col=1, secondary_y=False)
    
    # Add T_melt line
    T_melt = PCM_CONFIGS[sys_name]['T_melt_C']
    fig.add_hline(
        y=T_melt, line_dash="dash", line_color="red",
        annotation_text=f"T_melt={T_melt}°C",
        row=2, col=1
    )
    
    # Price on secondary axis
    fig.add_trace(go.Scatter(
        x=july_slice, y=price_slice,
        name='Spot Price',
        line=dict(color='purple', width=1.5),
        opacity=0.7
    ), row=2, col=1, secondary_y=True)
    
    # Panel 3: SOC + Charge/Discharge Power
    fig.add_trace(go.Scatter(
        x=july_slice, y=[s*100 for s in SOC_passive_slice],
        name='Passive SOC',
        line=dict(color='orange', width=1.5)
    ), row=3, col=1, secondary_y=False)
    
    fig.add_trace(go.Scatter(
        x=july_slice, y=[s*100 for s in SOC_active_slice],
        name='Active SOC',
        line=dict(color='green', width=2)
    ), row=3, col=1, secondary_y=False)
    
    # Charge/discharge on secondary axis
    fig.add_trace(go.Scatter(
        x=july_slice, y=[q/1000 for q in Q_chg_slice],
        name='Charging (kW)',
        line=dict(color='cyan', width=2),
        fill='tozeroy'
    ), row=3, col=1, secondary_y=True)
    
    fig.add_trace(go.Scatter(
        x=july_slice, y=[-q/1000 for q in Q_dis_slice],
        name='Discharging (kW)',
        line=dict(color='red', width=2),
        fill='tozeroy'
    ), row=3, col=1, secondary_y=True)
    
    # Panel 4: Context
    fig.add_trace(go.Scatter(
        x=july_slice, y=T_out_slice,
        name='T_outdoor',
        line=dict(color='brown', width=1.5)
    ), row=4, col=1, secondary_y=False)
    
    fig.add_trace(go.Scatter(
        x=july_slice, y=pv_slice,
        name='PV Generation',
        line=dict(color='gold', width=2),
        fill='tozeroy'
    ), row=4, col=1, secondary_y=True)
    
    # Layout
    fig.update_yaxes(title_text="Power (kW)", row=1, col=1)
    fig.update_yaxes(title_text="Temp (°C)", row=2, col=1, secondary_y=False)
    fig.update_yaxes(title_text="Price (€/MWh)", row=2, col=1, secondary_y=True)
    fig.update_yaxes(title_text="SOC (%)", row=3, col=1, secondary_y=False)
    fig.update_yaxes(title_text="PCM Power (kW)", row=3, col=1, secondary_y=True)
    fig.update_yaxes(title_text="T_out (°C)", row=4, col=1, secondary_y=False)
    fig.update_yaxes(title_text="PV (kW)", row=4, col=1, secondary_y=True)
    
    fig.update_xaxes(title_text="Date & Time", row=4, col=1)
    
    fig.update_layout(
        height=1200,
        title_text=f"{sys_name}: Active PCM 3-Day Detail (July 4-6, 2025)",
        hovermode='x unified'
    )
    
    # Save
    filename = f'plots/section_7_2_active_pcm_3day_{sys_name.replace(" ", "_")}_july.html'
    fig.write_html(filename)
    print(f'  ✓ Saved: {filename}')
    
    # Show first system only
    if sys_name == "Tiefkühlung 2":  # Show largest system
        fig.show()

print('\n' + '='*70)
print('✓ Section 7.2 complete: 3-day detailed plots generated')

# =============================================================================
# CELL 42 (Markdown): Summary Comparison Header
# =============================================================================
"""
## 7.3 Summary Comparison: Cost Progression

Compare total costs across all optimization strategies to quantify value of each approach.

**Strategies Compared:**
1. **Flat Baseline** - Fixed temperature setpoints (unoptimized)
2. **Cost-Aware Scheduling** - Price-based optimization (zero CAPEX)
3. **Passive PCM** - Thermal storage with cost-aware schedules (no re-optimization)
4. **Active PCM** - Full price-based charge/discharge optimization

**Metrics:**
- Total 10-month cost (energy + demand)
- Absolute savings vs flat baseline (€)
- Relative savings (%)
- Incremental benefit of each strategy
"""

# =============================================================================
# CELL 43 (Code): Summary Comparison Table
# =============================================================================
print('\nSection 7.3: Active PCM Summary Comparison')
print('='*70)

# Aggregate costs across all months for each system
summary_data = []

for sys_name in SYSTEM_NAMES:
    # Sum across 10 months (Jan-Oct)
    flat_cost = sum([flat_baseline[sys_name][m]['total_cost'] for m in range(1, 11)])
    uncon_cost = sum([uncon_results[sys_name][m]['total_cost'] for m in range(1, 11)])
    passive_cost = sum([passive_pcm_results[sys_name][m]['total_cost'] for m in range(1, 11)])
    active_cost = sum([active_pcm_results[sys_name][m]['total_cost'] for m in range(1, 11)])
    
    # Calculate savings
    uncon_savings = flat_cost - uncon_cost
    passive_savings = flat_cost - passive_cost
    active_savings = flat_cost - active_cost
    
    # Incremental benefits
    passive_incremental = uncon_cost - passive_cost  # Benefit over cost-aware
    active_incremental = passive_cost - active_cost  # Benefit over passive
    
    summary_data.append({
        'System': sys_name,
        'Flat Cost (€)': f'{flat_cost:.2f}',
        'Cost-Aware (€)': f'{uncon_cost:.2f}',
        'Passive PCM (€)': f'{passive_cost:.2f}',
        'Active PCM (€)': f'{active_cost:.2f}',
        'Cost-Aware Savings': f'€{uncon_savings:.2f} ({100*uncon_savings/flat_cost:.2f}%)',
        'Passive Savings': f'€{passive_savings:.2f} ({100*passive_savings/flat_cost:.2f}%)',
        'Active Savings': f'€{active_savings:.2f} ({100*active_savings/flat_cost:.2f}%)',
        'Passive Incremental': f'€{passive_incremental:.2f}',
        'Active Incremental': f'€{active_incremental:.2f}'
    })

# Create summary DataFrame
df_summary = pd.DataFrame(summary_data)

print('\n📊 10-MONTH COST SUMMARY (Jan-Oct 2025)')
print('='*70)
print('\nTotal Costs by Strategy:')
print(df_summary[['System', 'Flat Cost (€)', 'Cost-Aware (€)', 'Passive PCM (€)', 'Active PCM (€)']].to_string(index=False))

print('\n\nSavings vs Flat Baseline:')
print(df_summary[['System', 'Cost-Aware Savings', 'Passive Savings', 'Active Savings']].to_string(index=False))

print('\n\nIncremental Benefits:')
print(df_summary[['System', 'Passive Incremental', 'Active Incremental']].to_string(index=False))

# Site-wide totals
flat_total = sum([float(row['Flat Cost (€)']) for row in summary_data])
uncon_total = sum([float(row['Cost-Aware (€)']) for row in summary_data])
passive_total = sum([float(row['Passive PCM (€)']) for row in summary_data])
active_total = sum([float(row['Active PCM (€)']) for row in summary_data])

print('\n' + '='*70)
print('🏢 TOTAL SITE (All 4 Systems Combined):')
print('='*70)
print(f'Flat Baseline:           €{flat_total:>10,.2f}')
print(f'Cost-Aware Scheduling:   €{uncon_total:>10,.2f}  (saves €{flat_total-uncon_total:>8,.2f}, {100*(flat_total-uncon_total)/flat_total:>5.2f}%)')
print(f'Passive PCM:             €{passive_total:>10,.2f}  (saves €{flat_total-passive_total:>8,.2f}, {100*(flat_total-passive_total)/flat_total:>5.2f}%)')
print(f'Active PCM:              €{active_total:>10,.2f}  (saves €{flat_total-active_total:>8,.2f}, {100*(flat_total-active_total)/flat_total:>5.2f}%)')

print('\n💰 INCREMENTAL VALUE:')
print(f'  Cost-Aware → Passive PCM:   €{uncon_total - passive_total:>8,.2f}  (Passive incremental)')
print(f'  Passive PCM → Active PCM:   €{passive_total - active_total:>8,.2f}  (Active incremental)')

# Economic analysis
pcm_capex = sum([PCM_CONFIGS[sys]['mass_kg'] * 
                 (2.50 if 'Tief' in sys else 0.50) * 2.5  # material cost × install multiplier
                 for sys in SYSTEM_NAMES])

print('\n' + '='*70)
print('📈 ECONOMIC ANALYSIS (10-Month Basis):')
print('='*70)
print(f'PCM CAPEX (all systems):     €{pcm_capex:,.2f}')
print(f'Passive PCM savings:         €{flat_total - passive_total:,.2f}/10-months')
print(f'Active PCM savings:          €{flat_total - active_total:,.2f}/10-months')
print(f'\nAnnualized (×1.2):')
print(f'  Passive: €{1.2*(flat_total - passive_total):,.2f}/year → Payback: {pcm_capex / (1.2*(flat_total - passive_total)):.1f} years')
print(f'  Active:  €{1.2*(flat_total - active_total):,.2f}/year → Payback: {pcm_capex / (1.2*(flat_total - active_total)):.1f} years')

print('\n💡 KEY INSIGHTS:')
if active_total < passive_total:
    improvement = 100 * (passive_total - active_total) / passive_total
    print(f'  ✓ Active PCM improves over passive by {improvement:.1f}%')
    print(f'  ✓ Additional €{passive_total - active_total:.2f} saved through active control')
else:
    print(f'  ⚠ Active PCM did not improve over passive (check optimization)')

print('\n' + '='*70)
print('✓ Section 7.3 complete: Summary comparison generated')
print('\n🎯 Next Steps: Proceed to parametric sweep (Section 7.4) to find optimal PCM configuration')
