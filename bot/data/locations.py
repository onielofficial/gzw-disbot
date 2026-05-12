"""Static pixel coordinates for each named location on the Lamang base map.
Map image size: approximately 1456x816 pixels (full island zoom-fit screenshot).
Coordinates are (x, y) pixel positions from top-left corner."""
from __future__ import annotations

LOCATION_COORDS: dict[str, tuple[int, int]] = {
    "Tiger Bay":      (1050, 580),
    "Ban Pa":         (380,  290),
    "Fort Narith":    (430,  540),
    "Lamang":         (728,  408),
    "MSR":            (580,  340),
    "Sawmill":        (290,  240),
    "Airport":        (410,  520),
    "Mithras HQ":     (690,  390),
    "Nam Suon":       (850,  460),
    "Prai Wan":       (620,  480),
    "Shipwreck":      (1150, 480),
    "Industrial":     (700,  550),
    "Ban Pha":        (450,  310),
    "North Camp":     (500,  200),
    "South Beach":    (900,  700),
    "Quarry":         (250,  400),
    "Village":        (600,  300),
    "Jungle Camp":    (300,  450),
}


def find_coords(location: str | None) -> tuple[int, int] | None:
    """Case-insensitive location lookup. Returns None if not found."""
    if not location:
        return None
    location = location.strip()
    if location in LOCATION_COORDS:
        return LOCATION_COORDS[location]
    lower = location.lower()
    for key, coords in LOCATION_COORDS.items():
        if key.lower() == lower:
            return coords
    for key, coords in LOCATION_COORDS.items():
        if lower in key.lower() or key.lower() in lower:
            return coords
    return None
