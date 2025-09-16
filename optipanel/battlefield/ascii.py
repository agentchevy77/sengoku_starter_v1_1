"""
ASCII battlefield renderer.

Pure, deterministic; no I/O.
"""

from typing import Dict, Any


def render_battlefield(units: Dict[str, Any], width: int = 20) -> str:
    """
    Render battlefield as ASCII grid.

    Args:
        units: Dict with unit positions and types
        width: Grid width (height auto-calculated)

    Returns:
        ASCII string representation of battlefield
    """
    if not units:
        return "." * width + "\n"

    # Extract positions and determine grid bounds
    positions = []
    for unit_data in units.values():
        if isinstance(unit_data, dict) and "pos" in unit_data:
            pos = unit_data["pos"]
            if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                positions.append((int(pos[0]), int(pos[1])))

    if not positions:
        return "." * width + "\n"

    # Calculate grid dimensions
    min_x = min(pos[0] for pos in positions)
    max_x = max(pos[0] for pos in positions)
    min_y = min(pos[1] for pos in positions)
    max_y = max(pos[1] for pos in positions)

    # Ensure minimum grid size
    grid_width = max(width, max_x - min_x + 3)
    grid_height = max(3, max_y - min_y + 3)

    # Create grid
    grid = [["." for _ in range(grid_width)] for _ in range(grid_height)]

    # Place units on grid
    for unit_id, unit_data in units.items():
        if isinstance(unit_data, dict) and "pos" in unit_data:
            pos = unit_data["pos"]
            if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                x, y = int(pos[0]) - min_x + 1, int(pos[1]) - min_y + 1
                if 0 <= x < grid_width and 0 <= y < grid_height:
                    # Use first character of unit type or ID
                    symbol = "?"
                    if "type" in unit_data and unit_data["type"]:
                        symbol = str(unit_data["type"])[0].upper()
                    elif unit_id:
                        symbol = str(unit_id)[0].upper()
                    grid[y][x] = symbol

    # Convert grid to string
    return "\n".join("".join(row) for row in grid) + "\n"