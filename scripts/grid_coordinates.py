"""Resolve continuous grid coordinates using the geometry of the latest view."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import re


_POINT_ID = re.compile(r"([GL])-([0-9]+(?:\.[0-9]+)?)-([0-9]+(?:\.[0-9]+)?)")


@dataclass(frozen=True)
class GridTransform:
    step: int
    width: int
    height: int
    offset_x: int = 0
    offset_y: int = 0
    anchor_x: int = 0
    anchor_y: int = 0
    anchor_col: int = 0
    anchor_row: int = 0

    def resolve(self, column, row):
        x = Decimal(str(self.anchor_x)) + (column - self.anchor_col) * self.step
        y = Decimal(str(self.anchor_y)) + (row - self.anchor_row) * self.step
        # A line drawn at the image's far boundary still names its last pixel,
        # just as it does in the original integer-point dictionary.
        if not (0 <= x <= self.width and 0 <= y <= self.height):
            raise ValueError("Point is outside the visible view; choose a point inside the latest image.")
        pixel_x = min(self.width - 1, int(x.to_integral_value(rounding=ROUND_HALF_UP)))
        pixel_y = min(self.height - 1, int(y.to_integral_value(rounding=ROUND_HALF_UP)))
        return self.offset_x + pixel_x, self.offset_y + pixel_y


class GridCoordinateMap(dict):
    """Keep discrete points compatible while resolving decimals without snapping."""

    def __init__(self, points=None, *, transforms=None):
        super().__init__(points if points is not None else {})
        self._transforms = dict(transforms or {})

    def merged(self, other):
        return GridCoordinateMap(
            {**self, **other},
            transforms={**self._transforms, **other._transforms},
        )

    def resolve(self, point_id):
        match = _POINT_ID.fullmatch(point_id) if isinstance(point_id, str) else None
        if match is None:
            raise ValueError(
                "Expected G-column-row or L-column-row with non-negative integer or decimal indices, "
                "for example L-10-10.32 or G-01.10-08."
            )
        if point_id in self:
            return self[point_id]
        prefix, column, row = match.groups()
        transform = self._transforms.get(prefix)
        if transform is None:
            raise ValueError(f"No {prefix} view geometry is available in the latest coordinate map.")
        return transform.resolve(Decimal(column), Decimal(row))
