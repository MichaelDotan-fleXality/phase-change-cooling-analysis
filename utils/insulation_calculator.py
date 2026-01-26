"""
Helper functions for calculating heat transfer coefficients from insulation properties.
"""

from typing import Union, Optional

# Typical thermal conductivity values (lambda) in W/(m·K) for common insulation materials
INSULATION_THERMAL_CONDUCTIVITY = {
    # Common insulation types
    "mineral_wool": 0.040,      # Mineral wool / Rock wool
    "glass_wool": 0.040,        # Glass wool
    "eps": 0.035,               # Expanded Polystyrene (EPS)
    "xps": 0.035,               # Extruded Polystyrene (XPS)
    "pur": 0.025,               # Polyurethane (PUR)
    "pir": 0.025,               # Polyisocyanurate (PIR)
    "cellulose": 0.040,         # Cellulose insulation
    "wood_fiber": 0.050,        # Wood fiber insulation
    "cork": 0.040,              # Cork insulation
    "concrete": 1.5,            # Concrete (poor insulation)
    "brick": 0.77,              # Brick
    "aerated_concrete": 0.120,  # Aerated concrete
    "mineral_fiber": 0.040,     # General mineral fiber
    "polyethylene": 0.033,      # Polyethylene foam
    "none": 0.5,                # No insulation / poor insulation (default)
}

def calculate_heat_transfer_coefficient(
    insulation_thickness_m: Union[int, float],
    insulation_type: str = "mineral_wool",
    thermal_conductivity: Optional[Union[int, float]] = None,
) -> float:
    """
    Calculate U-value (heat transfer coefficient) from insulation thickness and type.
    
    U-value = λ / d
    where:
    - λ (lambda) = thermal conductivity in W/(m·K)
    - d = thickness in meters
    
    Parameters:
    -----------
    insulation_thickness_m : float
        Thickness of insulation in meters
    insulation_type : str, optional
        Type of insulation material. Common values:
        - "mineral_wool", "glass_wool" (λ ≈ 0.040)
        - "eps", "xps" (λ ≈ 0.035)
        - "pur", "pir" (λ ≈ 0.025)
        - "concrete" (λ ≈ 1.5, poor insulation)
        - "none" (default, poor insulation)
        See INSULATION_THERMAL_CONDUCTIVITY for all options
    thermal_conductivity : float, optional
        Custom thermal conductivity value in W/(m·K).
        If provided, this overrides the insulation_type lookup.
    
    Returns:
    --------
    float
        U-value (heat transfer coefficient) in W/(m²·K)
    """
    if thermal_conductivity is not None:
        lambda_value = thermal_conductivity
    else:
        # Look up thermal conductivity from insulation type
        lambda_value = INSULATION_THERMAL_CONDUCTIVITY.get(
            insulation_type.lower(),
            INSULATION_THERMAL_CONDUCTIVITY["none"]  # Default if not found
        )
    
    if insulation_thickness_m <= 0:
        raise ValueError(f"Insulation thickness must be positive, got {insulation_thickness_m}")
    
    # Calculate U-value: U = λ / d
    u_value = lambda_value / insulation_thickness_m
    
    return u_value

def get_insulation_types() -> list:
    """Return list of available insulation types."""
    return list(INSULATION_THERMAL_CONDUCTIVITY.keys())

