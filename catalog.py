"""
Catalogues for the "Select from list" option and the IS 2062 : 2011 tables.

Only entries confirmed from the client frontend are listed. Add further
uprights, beams, connectors and steel grades here in the same format.
"""

# ---------------- Sections (dimensions in mm) ----------------

UPRIGHTS = {
    "Upright 90 x 1.4mm": {"D": 65.2, "W": 90.0, "B": 51.8, "T": 1.4},
    "Upright 90 x 65 x 1.6mm": {"D": 65.0, "W": 90.0, "B": 51.5, "T": 1.6},
}

BEAMS = {
    "RFB 80 - 1.2mm": {"H": 80.0, "W": 50.0, "T": 1.2, "type": "RFB"},
    "Beam 80 x 50 x 1.5mm": {"H": 80.0, "W": 50.0, "T": 1.5, "type": "Box"},
}

CONNECTORS = {
    "3 Lip Connector": {"n_lips": 3, "H": 190.0, "D": 63.0, "W": 41.0, "T": 4.0},
    "3 Lip Connector 155mm": {"n_lips": 3, "H": 155.0, "D": 64.0, "W": 40.0, "T": 3.0},
    "5 Lip Connector 245mm": {"n_lips": 5, "H": 245.0, "D": 64.0, "W": 40.0, "T": 4.0},
}

# ---------------- IS 2062 : 2011 ----------------
# Mechanical properties (Clauses 5, 10.3, 10.3.1, 11.3.1, 12.2 and 12.4)
# Rm = tensile strength (min, MPa); ReH = yield stress (min, MPa) by
# thickness band; A = % elongation.
IS2062_MECHANICAL = {
    "E 250": {
        q: {"Rm": 410, "ReH <20": 250, "ReH 20-40": 240, "ReH >40": 230, "A %": 23}
        for q in ("A", "BR", "B0", "C")
    },
}

# Chemical properties (Clauses 5, 8.1 and 8.2), max %
IS2062_CHEMICAL = {
    "E 250": {
        "A": {"C": 0.23, "Mn": 1.50, "S": 0.045, "P": 0.045, "Si": 0.40,
              "CE": 0.42, "Deoxidation": "Semi-killed/killed"},
        "BR, B0": {"C": 0.22, "Mn": 1.50, "S": 0.045, "P": 0.045, "Si": 0.40,
                   "CE": 0.41, "Deoxidation": "Semi-killed/killed"},
        "C": {"C": 0.20, "Mn": 1.50, "S": 0.040, "P": 0.040, "Si": 0.40,
              "CE": 0.39, "Deoxidation": "Killed"},
    },
}


def chemical_row(grade: str, quality: str) -> dict:
    for key, row in IS2062_CHEMICAL[grade].items():
        if quality in [k.strip() for k in key.split(",")]:
            return row
    raise KeyError(f"{grade} quality {quality}")


def yield_strength(grade: str, quality: str, thickness_mm: float) -> float:
    """ReH for the thickness band of the thickest part under test."""
    row = IS2062_MECHANICAL[grade][quality]
    if thickness_mm < 20:
        return row["ReH <20"]
    if thickness_mm <= 40:
        return row["ReH 20-40"]
    return row["ReH >40"]
