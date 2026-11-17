from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from math import isfinite


class FormatError(ValueError):
    """Input is invalid or outside the supported format profile."""


MM = Decimal("0.001")
HEIGHT_DATUMS = ("NN2000", "NN54")


@dataclass(frozen=True)
class SurveyPoint:
    point_id: str
    x: float
    y: float
    z: float | None = None
    code: str = ""
    note: str = ""
    calculation_code: str = ""


@dataclass(frozen=True)
class PointSet:
    points: tuple[SurveyPoint, ...]
    crs: str | None = None
    height_datum: str | None = None


@dataclass(frozen=True)
class SosiVectorFeature:
    serial: str
    kind: str
    vertices: tuple[tuple[float, ...], ...]
    source_lines: tuple[str, ...]
    boundary: tuple[tuple[str, tuple[tuple[float, ...], ...]], ...] = ()


@dataclass(frozen=True)
class SosiVectorSet:
    features: tuple[SosiVectorFeature, ...]
    crs: str
    height_datum: str | None
    catalogue: str


def validate_points(points):
    if not points:
        raise FormatError("Fila eller laget har ingen støtta punkt.")

    seen = set()
    for point in points:
        if not point.point_id or point.point_id in seen:
            raise FormatError(f"Tom eller duplisert punkt-ID: {point.point_id!r}.")
        seen.add(point.point_id)
        if any(not isfinite(value) for value in coordinates(point)):
            raise FormatError(f"Punkt {point.point_id} har ein ugyldig koordinat.")


def coordinates(point):
    return (point.x, point.y) if point.z is None else (point.x, point.y, point.z)


def millimetres(value):
    return Decimal(str(value)).quantize(MM, rounding=ROUND_HALF_UP)
