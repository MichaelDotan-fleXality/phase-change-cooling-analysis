"""
Plotting utilities for phase-change cooling analysis.
"""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Optional, List, Dict, Union


class PhaseChangePlotter:
    """Plotting class for phase-change cooling analysis."""
    
    def __init__(self, data: pd.DataFrame):
        """
        Initialize plotter with data.
        
        Parameters:
        -----------
        data : pd.DataFrame
            Data to plot
        """
        self.data = data
    
    def plot_power_curves(
        self,
        power_cols: List[str],
        energy_price_col: Optional[str] = None,
        temp_col: Optional[str] = None,
        colors: Optional[Dict[str, str]] = None,
        title: Optional[str] = None,
        save_path: Optional[str] = None,
    ):
        """
        Plot power curves with optional energy price and temperature.
        
        Parameters:
        -----------
        power_cols : list
            List of column names for power data
        energy_price_col : str, optional
            Column name for energy price
        temp_col : str, optional
            Column name for temperature
        colors : dict, optional
            Color mapping for columns
        title : str, optional
            Plot title
        save_path : str, optional
            Path to save HTML file
        """
        # Determine number of y-axes
        n_axes = 1
        if energy_price_col:
            n_axes += 1
        if temp_col:
            n_axes += 1
        
        # Create subplots
        fig = make_subplots(
            rows=n_axes,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            subplot_titles=(
                ["Power (kW)"] + 
                (["Energy Price (ct/kWh)"] if energy_price_col else []) +
                (["Temperature (°C)"] if temp_col else [])
            )
        )
        
        # Default colors
        if colors is None:
            colors = {}
        default_colors = ["blue", "red", "green", "orange", "purple", "brown"]
        
        # Plot power
        for i, col in enumerate(power_cols):
            color = colors.get(col, default_colors[i % len(default_colors)])
            fig.add_trace(
                go.Scatter(
                    x=self.data.index,
                    y=self.data[col],
                    name=col,
                    line=dict(color=color),
                ),
                row=1,
                col=1,
            )
        
        # Plot energy price
        if energy_price_col:
            row = 2
            fig.add_trace(
                go.Scatter(
                    x=self.data.index,
                    y=self.data[energy_price_col],
                    name=energy_price_col,
                    line=dict(color=colors.get(energy_price_col, "red")),
                ),
                row=row,
                col=1,
            )
        
        # Plot temperature
        if temp_col:
            row = n_axes
            fig.add_trace(
                go.Scatter(
                    x=self.data.index,
                    y=self.data[temp_col],
                    name=temp_col,
                    line=dict(color=colors.get(temp_col, "purple")),
                ),
                row=row,
                col=1,
            )
        
        # Update layout
        fig.update_layout(
            title=title,
            height=300 * n_axes,
            showlegend=True,
            hovermode="x unified",
        )
        
        fig.update_xaxes(title_text="Time", row=n_axes, col=1)
        
        if save_path:
            fig.write_html(save_path)
        
        return fig
    
    def plot_comparison(
        self,
        before_col: str,
        after_col: str,
        title: Optional[str] = None,
        save_path: Optional[str] = None,
        yaxis_title: Optional[str] = None,
    ):
        """
        Plot before/after comparison.
        
        Parameters:
        -----------
        before_col : str
            Column name for before data
        after_col : str
            Column name for after data
        title : str, optional
            Plot title
        save_path : str, optional
            Path to save HTML file
        yaxis_title : str, optional
            Y-axis title (auto-detected from column name if not provided)
        """
        fig = go.Figure()
        
        # For cumulative energy plots, add difference shading to make divergence visible
        show_difference_shading = "Energy Consumption" in before_col
        
        fig.add_trace(go.Scatter(
            x=self.data.index,
            y=self.data[before_col],
            name="Before",
            line=dict(color="blue", width=2),
            fill=None,
        ))
        
        fig.add_trace(go.Scatter(
            x=self.data.index,
            y=self.data[after_col],
            name="After",
            line=dict(color="red", width=2, dash="dash"),
            fill='tonexty' if show_difference_shading else None,
            fillcolor='rgba(255, 0, 0, 0.1)' if show_difference_shading else None,
        ))
        
        # Add annotation showing final savings for energy consumption plots
        if "Energy Consumption" in before_col:
            final_before = self.data[before_col].iloc[-1]
            final_after = self.data[after_col].iloc[-1]
            savings = final_before - final_after
            savings_pct = (savings / final_before * 100) if final_before > 0 else 0
            
            if savings > 0:
                annotation_text = f"Savings: {savings:.1f} kWh ({savings_pct:.1f}%)"
                annotation_color = "green"
            else:
                annotation_text = f"Increase: {abs(savings):.1f} kWh ({abs(savings_pct):.1f}%)"
                annotation_color = "red"
            
            fig.add_annotation(
                x=self.data.index[-1],
                y=max(final_before, final_after),
                text=annotation_text,
                showarrow=True,
                arrowhead=2,
                arrowcolor=annotation_color,
                font=dict(color=annotation_color, size=12),
                bgcolor="white",
                bordercolor=annotation_color,
                borderwidth=1,
            )
        
        # Auto-detect y-axis title from column name if not provided
        if yaxis_title is None:
            if "Cost" in before_col:
                yaxis_title = "Cost (€/h)"
            elif "Energy Consumption" in before_col:
                yaxis_title = "Energy Consumption (kWh)"
            elif "Power" in before_col:
                yaxis_title = "Power (kW)"
            else:
                yaxis_title = "Value"
        
        # For cumulative energy, ensure y-axis starts from 0 for better visualization
        yaxis_range = None
        if "Energy Consumption" in before_col:
            # Start from 0 to show the cumulative nature clearly
            yaxis_range = [0, max(self.data[before_col].max(), self.data[after_col].max()) * 1.1]
        
        fig.update_layout(
            title=title or "Before/After Comparison",
            xaxis_title="Time",
            yaxis_title=yaxis_title,
            hovermode="x unified",
            yaxis=dict(range=yaxis_range) if yaxis_range else {},
        )
        
        if save_path:
            fig.write_html(save_path)
        
        return fig
    
    def plot_before_optimization(
        self,
        evu_col: str,
        site_consumption_col: str,
        cooling_power_col: Optional[str] = None,
        pv_power_col: Optional[str] = None,
        title: Optional[str] = None,
        save_path: Optional[str] = None,
    ):
        """
        Plot power curves before optimization (German labels).
        
        Shows:
        - EVU-Zähler vor Optimierung (black)
        - Standortverbrauch vor Optimierung (green)
        - PV-Leistung (orange, if available)
        
        Parameters:
        -----------
        evu_col : str
            Column name for EVU meter (utility grid exchange)
        site_consumption_col : str
            Column name for site consumption
        cooling_power_col : str, optional
            Column name for cooling power (not displayed, kept for compatibility)
        pv_power_col : str, optional
            Column name for PV power
        title : str, optional
            Plot title
        save_path : str, optional
            Path to save HTML file
        """
        fig = go.Figure()
        
        # EVU-Zähler vor Optimierung (black line)
        # EVU Meter is now always net (after PV offset)
        evu_display_col = "EVU Meter" if "EVU Meter" in self.data.columns else evu_col
        fig.add_trace(go.Scatter(
            x=self.data.index,
            y=self.data[evu_display_col],
            name="EVU-Zähler vor Optimierung",
            line=dict(color="black", width=2),
            mode="lines",
        ))
        
        # Standortverbrauch vor Optimierung (green line)
        fig.add_trace(go.Scatter(
            x=self.data.index,
            y=self.data[site_consumption_col],
            name="Standortverbrauch vor Optimierung",
            line=dict(color="green", width=2),
            mode="lines",
        ))
        
        # PV-Leistung (orange line) - if available
        if pv_power_col and pv_power_col in self.data.columns:
            fig.add_trace(go.Scatter(
                x=self.data.index,
                y=self.data[pv_power_col],
                name="PV-Leistung",
                line=dict(color="orange", width=2),
                mode="lines",
            ))
        
        # Update layout with German labels
        fig.update_layout(
            title=title or "Datenlage vor Optimierung: Phase-Change Kühlsystem mit PV",
            xaxis_title="Zeit",
            yaxis_title="Leistung in kW",
            hovermode="x unified",
            height=600,
            showlegend=True,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor="rgba(255,255,255,0.8)",
            ),
            template="plotly_white",
        )
        
        # Format x-axis for better readability
        fig.update_xaxes(
            showgrid=True,
            gridwidth=1,
            gridcolor="lightgray",
        )
        
        # Format y-axis
        fig.update_yaxes(
            showgrid=True,
            gridwidth=1,
            gridcolor="lightgray",
        )
        
        if save_path:
            fig.write_html(save_path)
        
        return fig
    
    def plot_before_optimization_with_price(
        self,
        evu_col: str,
        grid_power_col: str,
        site_consumption_col: str,
        price_col: str,
        cooling_power_col: Optional[str] = None,
        pv_power_col: Optional[str] = None,
        title: Optional[str] = None,
        save_path: Optional[str] = None,
    ):
        """
        Plot power curves before optimization with electricity price (German labels).
        
        Shows:
        - Standortverbrauch vorher (green)
        - Netzbezugsleistung vorher (black)
        - PV-Leistung (orange, if available)
        - EVU-Zähler vorher (brown)
        - Strompreis vorher (red dashed, on secondary y-axis)
        
        Parameters:
        -----------
        evu_col : str
            Column name for EVU meter (utility grid exchange, can be negative)
        grid_power_col : str
            Column name for grid power (grid consumption, >= 0)
        site_consumption_col : str
            Column name for site consumption
        price_col : str
            Column name for electricity price (in ct/kWh)
        cooling_power_col : str, optional
            Column name for cooling power (not displayed, kept for compatibility)
        pv_power_col : str, optional
            Column name for PV power
        title : str, optional
            Plot title
        save_path : str, optional
            Path to save HTML file
        """
        from plotly.subplots import make_subplots
        
        # Create figure with secondary y-axis
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        # Standortverbrauch vorher (green line)
        fig.add_trace(go.Scatter(
            x=self.data.index,
            y=self.data[site_consumption_col],
            name="Standortverbrauch vorher",
            line=dict(color="green", width=2),
            mode="lines",
        ), secondary_y=False)
        
        # Netzbezugsleistung vorher (black line) - grid consumption
        fig.add_trace(go.Scatter(
            x=self.data.index,
            y=self.data[grid_power_col],
            name="Netzbezugsleistung vorher",
            line=dict(color="black", width=2),
            mode="lines",
        ), secondary_y=False)
        
        # PV-Leistung (orange line) - if available
        if pv_power_col and pv_power_col in self.data.columns:
            fig.add_trace(go.Scatter(
                x=self.data.index,
                y=self.data[pv_power_col],
                name="PV-Leistung",
                line=dict(color="orange", width=2),
                mode="lines",
            ), secondary_y=False)
        
        # EVU-Zähler vorher (brown line) - can be negative
        # EVU Meter is now always net (after PV offset)
        evu_display_col = "EVU Meter" if "EVU Meter" in self.data.columns else evu_col
        fig.add_trace(go.Scatter(
            x=self.data.index,
            y=self.data[evu_display_col],
            name="EVU-Zähler vorher",
            line=dict(color="brown", width=2),
            mode="lines",
        ), secondary_y=False)
        
        # Strompreis vorher (red dashed line) - on secondary y-axis
        fig.add_trace(go.Scatter(
            x=self.data.index,
            y=self.data[price_col],
            name="Strompreis vorher",
            line=dict(color="red", width=2, dash="dash"),
            mode="lines",
        ), secondary_y=True)
        
        # Update layout with German labels
        fig.update_layout(
            title=title or "Effekt 1: Optimierung des Netzbezugs zum Ausnutzen günstiger Marktpreise: Ausgangslage",
            xaxis_title="Zeit",
            hovermode="x unified",
            height=600,
            showlegend=True,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor="rgba(255,255,255,0.8)",
            ),
            template="plotly_white",
        )
        
        # Set y-axis labels
        fig.update_yaxes(
            title_text="Leistung in kW",
            secondary_y=False,
            showgrid=True,
            gridwidth=1,
            gridcolor="lightgray",
        )
        fig.update_yaxes(
            title_text="Strompreis in ct/kWh",
            secondary_y=True,
            showgrid=False,
        )
        
        # Format x-axis
        fig.update_xaxes(
            showgrid=True,
            gridwidth=1,
            gridcolor="lightgray",
        )
        
        if save_path:
            fig.write_html(save_path)
        
        return fig
    
    def plot_emission_factor_curve(
        self,
        emission_factor_col: str,
        schedule_temp_col: str,
        title: Optional[str] = None,
        save_path: Optional[str] = None,
    ):
        """
        Plot emission factor curve with temperature schedule.
        
        Parameters:
        -----------
        emission_factor_col : str
            Column name for emission factors (g CO2/kWh)
        schedule_temp_col : str
            Column name for temperature schedule
        title : str, optional
            Plot title
        save_path : str, optional
            Path to save HTML file
        """
        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.1,
            subplot_titles=("Emission Factor (g CO₂/kWh)", "Temperature Schedule (°C)"),
        )
        
        # Emission factor curve
        fig.add_trace(
            go.Scatter(
                x=self.data.index,
                y=self.data[emission_factor_col],
                name="Emission Factor",
                line=dict(color="orange", width=2),
                mode="lines",
            ),
            row=1,
            col=1,
        )
        
        # Temperature schedule
        fig.add_trace(
            go.Scatter(
                x=self.data.index,
                y=self.data[schedule_temp_col],
                name="Temperature Schedule",
                line=dict(color="blue", width=2),
                mode="lines",
            ),
            row=2,
            col=1,
        )
        
        fig.update_layout(
            title=title or "Emission Factor and Temperature Schedule",
            hovermode="x unified",
            height=600,
        )
        
        fig.update_xaxes(title_text="Time", row=2, col=1)
        fig.update_yaxes(title_text="Emission Factor (g CO₂/kWh)", row=1, col=1)
        fig.update_yaxes(title_text="Temperature (°C)", row=2, col=1)
        
        if save_path:
            fig.write_html(save_path)
        
        return fig

