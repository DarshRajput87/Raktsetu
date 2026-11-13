"""Distances on the globe and snapping a location to the nearest road junction."""

import math

EARTH_RADIUS_KM = 6371.0
KM_PER_DEG_LAT = 111.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two points in km. O(1)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


class GridIndex:
    """Uniform grid of buckets over the junctions: cell -> [node ids].

    Build: O(V), one dict insert per junction.
    nearest(): looks at the cell containing the point, then at rings of cells
    around it, and stops once no closer junction can exist. With junctions
    spread fairly evenly this checks a constant number of cells and junctions:
    O(1) on average. Worst case (everything in one cell, or a point far outside
    the city) is O(V).
    """

    def __init__(self, node_coords: dict[str, tuple[float, float]], cell_deg: float = 0.01) -> None:
        self._coords = node_coords
        self._cell_deg = cell_deg
        self._cells: dict[tuple[int, int], list[str]] = {}
        for node_id, (lat, lng) in node_coords.items():
            self._cells.setdefault(self._cell(lat, lng), []).append(node_id)
        rows = [c[0] for c in self._cells]
        cols = [c[1] for c in self._cells]
        self._bounds = (min(rows), max(rows), min(cols), max(cols)) if self._cells else None

    def _cell(self, lat: float, lng: float) -> tuple[int, int]:
        return math.floor(lat / self._cell_deg), math.floor(lng / self._cell_deg)

    def nearest(self, lat: float, lng: float) -> tuple[str, float]:
        """(node id, distance in km) of the junction closest to the point."""
        if self._bounds is None:
            raise ValueError("the index has no junctions")
        row, col = self._cell(lat, lng)
        # A cell is at least this wide in km in either direction.
        cell_km = self._cell_deg * KM_PER_DEG_LAT * min(1.0, math.cos(math.radians(abs(lat) + 1)))
        min_row, max_row, min_col, max_col = self._bounds
        max_ring = max(abs(row - min_row), abs(row - max_row), abs(col - min_col), abs(col - max_col))

        best_id, best_km = "", math.inf
        if not (min_row <= row <= max_row and min_col <= col <= max_col):
            # Outside the city: walking rings of empty cells would be wasteful, scan instead.
            for node_id, (n_lat, n_lng) in self._coords.items():
                d = haversine_km(lat, lng, n_lat, n_lng)
                if d < best_km:
                    best_id, best_km = node_id, d
            return best_id, best_km
        for ring in range(max_ring + 1):
            for cell in self._ring(row, col, ring):
                for node_id in self._cells.get(cell, ()):
                    n_lat, n_lng = self._coords[node_id]
                    d = haversine_km(lat, lng, n_lat, n_lng)
                    if d < best_km:
                        best_id, best_km = node_id, d
            # Anything in a ring further out is at least ring * cell_km away.
            if best_km <= ring * cell_km:
                break
        return best_id, best_km

    @staticmethod
    def _ring(row: int, col: int, ring: int) -> list[tuple[int, int]]:
        """The cells exactly `ring` steps away (the border of a square)."""
        if ring == 0:
            return [(row, col)]
        cells = []
        for c in range(col - ring, col + ring + 1):
            cells.append((row - ring, c))
            cells.append((row + ring, c))
        for r in range(row - ring + 1, row + ring):
            cells.append((r, col - ring))
            cells.append((r, col + ring))
        return cells


def nearest_node(index: GridIndex, lat: float, lng: float) -> str:
    """Snap a location to the closest road junction. Average O(1), see GridIndex."""
    return index.nearest(lat, lng)[0]
