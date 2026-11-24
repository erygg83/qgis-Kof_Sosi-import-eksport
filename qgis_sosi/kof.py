"""KOF 05 coordinates in the column layout documented for netLIN 3."""

import re

from .model import FormatError, PointSet, SurveyPoint, millimetres, validate_points


NUMBER = re.compile(r"[+-]?[0-9]+(?:\.[0-9]{1,3})?")
SEPARATORS = (3, 14, 23, 36, 48, 57, 60)


def _coordinate(field, line_number, name):
    value = field.strip()
    if not NUMBER.fullmatch(value):
        raise FormatError(f"KOF linje {line_number}: ugyldig {name} i fast felt.")
    return float(value)


def decode(data):
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as error:
        raise FormatError("KOF-profilen krev ASCII-teikn.") from error

    points = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip() or line.startswith("-"):
            continue
        if not line.startswith(" 05"):
            raise FormatError(f"KOF linje {number}: prototypen les berre aktive 05-blokker.")
        if len(line) > 80 or any(not " " <= char <= "~" for char in line):
            raise FormatError(f"KOF linje {number}: ugyldige teikn eller meir enn 80 kolonnar.")

        row = line.ljust(80)
        if any(row[index] != " " for index in SEPARATORS) or row[68:].strip():
            raise FormatError(f"KOF linje {number}: feltplasseringa samsvarar ikkje med netLIN 05.")

        height = row[49:57]
        points.append(SurveyPoint(
            row[4:14].strip(),
            _coordinate(row[37:48], number, "aust"),
            _coordinate(row[24:36], number, "nord"),
            _coordinate(height, number, "høgd") if height.strip() else None,
            row[15:23].strip(),
            row[61:68].strip(),
            row[58:60].strip(),
        ))
    validate_points(points, require_unique_ids=False)
    return PointSet(tuple(points))


def _text_field(value, width, label, point_id):
    if (
        len(value) > width or value != value.strip()
        or any(not " " <= char <= "~" for char in value)
    ):
        raise FormatError(f"Punkt {point_id}: {label} må ha høgst {width} ASCII-teikn.")
    return value.ljust(width)


def _numeric_field(value, width, label, point_id):
    if value is not None and abs(value) >= 10**width:
        raise FormatError(f"Punkt {point_id}: {label} får ikkje plass i KOF-feltet.")
    text = "" if value is None else str(millimetres(value))
    if len(text) > width:
        raise FormatError(f"Punkt {point_id}: {label} får ikkje plass i KOF-feltet.")
    return text.rjust(width)


def encode(dataset):
    validate_points(dataset.points, require_unique_ids=False)
    rows = []
    for point in dataset.points:
        point_id = point.point_id
        fields = [
            " 05",
            _text_field(point_id, 10, "punkt-ID", point_id),
            _text_field(point.code, 8, "temakode", point_id),
            _numeric_field(point.y, 12, "nord", point_id),
            _numeric_field(point.x, 11, "aust", point_id),
            _numeric_field(point.z, 8, "høgd", point_id),
            _text_field(point.calculation_code, 2, "berekningskode", point_id),
            _text_field(point.note, 7, "merknad", point_id),
        ]
        rows.append(" ".join(fields).rstrip())
    return ("\r\n".join(rows) + "\r\n").encode("ascii")
