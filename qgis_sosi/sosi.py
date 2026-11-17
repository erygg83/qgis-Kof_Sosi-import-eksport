"""SOSI 4.5 point exchange and import of vector and presentation data."""

from decimal import Decimal
from math import ceil, floor
import re

from .model import (
    FormatError, HEIGHT_DATUMS, MM, PointSet, SosiVectorFeature, SosiVectorSet,
    SurveyPoint, coordinates,
    millimetres, validate_points,
)


CRS_BY_CODE = {"22": "EPSG:25832", "23": "EPSG:25833", "25": "EPSG:25835"}
CODE_BY_CRS = {crs: code for code, crs in CRS_BY_CODE.items()}
ENCODINGS = {"UTF-8": "utf-8-sig", "ISO8859-1": "iso8859-1", "ISO8859-10": "iso8859-10"}
OUTPUT_CHARSET = "ISO8859-1"
HEADER_KEYS = {
    "..TEGNSETT", "..SOSI-VERSJON", "..SOSI-NIVÅ", "..TRANSPAR",
    "...KOORDSYS", "...ORIGO-NØ", "...ENHET", "...ENHET-H", "...VERT-DATUM",
    "..OMRÅDE", "...MIN-NØ", "...MAX-NØ",
}
VECTOR_HEADER_KEYS = HEADER_KEYS | {"..PROSESS_HISTORIE", "..PRODUSENT", "..OBJEKTKATALOG"}
VECTOR_KINDS = {"PUNKT", "KURVE", "BUEP", "FLATE", "TEKST", "SYMBOL"}
INTEGER = re.compile(r"[+-]?[0-9]{1,10}")
SERIAL = re.compile(r"[1-9][0-9]{0,8}")
DECIMAL = re.compile(r"[0-9]{1,8}(?:\.[0-9]{1,8})?")
OBJECT_TYPE = re.compile(r"[\w-]+")
QUOTED_TEXT = re.compile(r'"([^"\x00-\x1f\x7f]*)"')


def _int_values(text, count, context):
    values = text.split()
    if len(values) != count or any(not INTEGER.fullmatch(value) for value in values):
        raise FormatError(f"{context} må ha {count} heiltal i denne SOSI-profilen.")
    return tuple(int(value) for value in values)


def _unit(text, name):
    if not DECIMAL.fullmatch(text) or not Decimal(text) > 0:
        raise FormatError(f"{name} må vere eit positivt desimaltal.")
    return Decimal(text)


def _read_header(lines, *, vector=False):
    header = {}
    keys = VECTOR_HEADER_KEYS if vector else HEADER_KEYS
    section = None
    for line in lines:
        key, *parts = line.split(maxsplit=1)
        value = parts[0] if parts else ""
        if vector and key == "..PROSESS_HISTORIE" and key in header:
            continue
        if key not in keys or key in header:
            raise FormatError(f"Ukjend eller repetert SOSI-hovudfelt: {key}.")
        if not key.startswith("..."):
            section = key
        elif section != ("..OMRÅDE" if key in {"...MIN-NØ", "...MAX-NØ"} else "..TRANSPAR"):
            raise FormatError(f"{key} står under feil SOSI-hovudfelt.")
        header[key] = value

    if header.get("..TEGNSETT") not in ENCODINGS or header.get("..SOSI-VERSJON") != "4.5":
        raise FormatError("Importen støttar SOSI 4.5 med UTF-8, ISO8859-1 eller ISO8859-10.")
    if header.get("..SOSI-NIVÅ") not in (None, "2", "3", "4"):
        raise FormatError("SOSI-nivået ligg utanfor punktprofilen.")
    if header.get("..TRANSPAR") != "" or header.get("..OMRÅDE") != "":
        raise FormatError("SOSI-fila må ha hovudgruppene TRANSPAR og OMRÅDE.")

    crs = CRS_BY_CODE.get(header.get("...KOORDSYS"))
    if not crs:
        raise FormatError("Prototypen støttar SOSI KOORDSYS 22, 23 og 25 i meter.")
    origin = _int_values(header.get("...ORIGO-NØ", ""), 2, "ORIGO-NØ")
    lower = _int_values(header.get("...MIN-NØ", ""), 2, "MIN-NØ")
    upper = _int_values(header.get("...MAX-NØ", ""), 2, "MAX-NØ")
    if any(low > high for low, high in zip(lower, upper)):
        raise FormatError("Feil rekkjefølgje i MIN-NØ og MAX-NØ.")
    unit_text = header.get("...ENHET", "")
    unit = _unit(unit_text, "ENHET")
    height_unit = _unit(header.get("...ENHET-H", unit_text), "ENHET-H")
    datum = header.get("...VERT-DATUM")
    if datum is not None and datum not in HEIGHT_DATUMS:
        raise FormatError("Prototypen les VERT-DATUM NN2000 eller NN54 som éin verdi.")
    return crs, origin, unit, height_unit, datum, header.get("..OBJEKTKATALOG", "")


def _coordinate(north, east, *height, origin, unit, height_unit):
    xy = (float(origin[1] + east * unit), float(origin[0] + north * unit))
    return (*xy, float(height[0] * height_unit)) if height else xy


def _read_point(group, lines, origin, unit, height_unit):
    serial = re.fullmatch(r"\.PUNKT\s+([1-9][0-9]{0,8}):", group)
    if not serial:
        raise FormatError(f"Punktprofilen støttar berre .PUNKT med serienummer: {group}.")
    point_id = serial[1]
    fields = {}
    for line in lines[:-1]:
        key, *parts = line.split(maxsplit=1)
        if key in fields or key not in {"..OBJTYPE", "..NAVN", "..NØ", "..NØH"}:
            raise FormatError(f"Punkt {point_id}: ukjend eller repetert eigenskap {key}.")
        fields[key] = parts[0] if parts else ""

    code = fields.pop("..OBJTYPE", "")
    if not OBJECT_TYPE.fullmatch(code):
        raise FormatError(f"Punkt {point_id}: ventar éin OBJTYPE-verdi.")
    note = ""
    if "..NAVN" in fields:
        value = fields.pop("..NAVN")
        quoted = QUOTED_TEXT.fullmatch(value)
        if not quoted and not re.fullmatch(r'[^\s"\x00-\x1f\x7f]+', value):
            raise FormatError(f"Punkt {point_id}: ugyldig NAVN.")
        note = quoted[1] if quoted else value
    if len(fields) != 1 or not lines or lines[-2:-1] not in (["..NØ"], ["..NØH"]):
        raise FormatError(f"Punkt {point_id}: ventar eitt koordinatsett etter NØ eller NØH.")

    is_3d = "..NØH" in fields
    values = _int_values(lines[-1], 3 if is_3d else 2, f"Punkt {point_id}")
    xy = _coordinate(*values, origin=origin, unit=unit, height_unit=height_unit)
    return SurveyPoint(point_id, xy[0], xy[1], xy[2] if is_3d else None, code, note)


def decode(data):
    charset = re.search(rb"^\.\.TEGNSETT[ \t]+([A-Z0-9-]+)[ \t]*\r?$", data, re.MULTILINE)
    encoding = ENCODINGS.get(charset[1].decode("ascii")) if charset else None
    if encoding is None:
        raise FormatError("SOSI-fila må oppgi UTF-8, ISO8859-1 eller ISO8859-10 som teiknsett.")
    try:
        text = data.decode(encoding)
    except UnicodeDecodeError as error:
        raise FormatError("SOSI-fila samsvarar ikkje med teiknsettet i filhovudet.") from error

    groups = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(".") and not line.startswith(".."):
            groups.append((line, []))
        elif not groups:
            raise FormatError("SOSI-fila startar med eigenskapar utan datagruppe.")
        else:
            groups[-1][1].append(line)

    if len(groups) < 2 or not re.fullmatch(r"\.HODE(?:\s+0:)?", groups[0][0]):
        raise FormatError("SOSI-fila må starte med .HODE.")
    if groups[-1] != (".SLUTT", []):
        raise FormatError("SOSI-fila må avsluttast med .SLUTT.")

    objects = groups[1:-1]
    kinds = {group.split(maxsplit=1)[0][1:] for group, _ in objects}
    metadata_keys = VECTOR_HEADER_KEYS - HEADER_KEYS
    if (kinds & (VECTOR_KINDS - {"PUNKT"}) or
            any(line.split(maxsplit=1)[0] in metadata_keys for line in groups[0][1])):
        return _read_vectors(groups[0][1], objects)

    crs, origin, unit, height_unit, datum, _ = _read_header(groups[0][1])
    points = tuple(
        _read_point(group, lines, origin, unit, height_unit)
        for group, lines in objects
    )
    validate_points(points)
    return PointSet(points, crs, datum)


def _read_vectors(header, objects):
    crs, origin, unit, height_unit, datum, catalogue = _read_header(header, vector=True)
    entries = {}
    for group, lines in objects:
        match = re.fullmatch(r"\.([A-Z]+)\s+([1-9][0-9]{0,8}):", group)
        if not match or match[1] not in VECTOR_KINDS:
            raise FormatError(f"SOSI-geometrien er utanfor støtta importprofil: {group}.")
        kind, serial = match.groups()
        if serial in entries:
            raise FormatError(f"Duplisert SOSI-serienummer: {serial}.")
        entries[serial] = kind, lines

    if not entries:
        raise FormatError("SOSI-fila inneheld ingen objekt.")
    positions = {}
    for serial, (kind, lines) in entries.items():
        if kind != "FLATE":
            positions[serial] = _vector_positions(kind, serial, lines, origin, unit, height_unit)

    features = []
    for serial, (kind, lines) in entries.items():
        if kind == "FLATE":
            vertices, boundary = _surface_ring(serial, lines, entries, positions)
        else:
            vertices, boundary = positions[serial], ()
        features.append(SosiVectorFeature(serial, kind, vertices, tuple(lines), boundary))
    return SosiVectorSet(tuple(features), crs, datum, catalogue)


def _vector_positions(kind, serial, lines, origin, unit, height_unit):
    vertices = []
    dimensions = None
    count = None
    for line in lines:
        if line.startswith("!"):
            continue
        if line.startswith("."):
            key = line.split(maxsplit=1)[0]
            if key in {"..NØ", "..NØH"} and key == line:
                count = 3 if key == "..NØH" else 2
                if dimensions is not None and dimensions != count:
                    raise FormatError(f"{kind} {serial}: blanda koordinatdimensjonar.")
                dimensions = count
            elif key in {"..NØ", "..NØH", "..NØD", "..ENHET", "..ENHET-H", "..ORIGO-NØ"}:
                raise FormatError(f"{kind} {serial}: koordinatfeltet {key} er utanfor støtta profil.")
            else:
                count = None
        elif count:
            values, marker, annotation = line.partition("...KP")
            if marker and not re.fullmatch(r"[0-9]{1,3}", annotation.strip()):
                raise FormatError(f"{kind} {serial}: ugyldig knutepunktkode.")
            values = _int_values(values, count, f"{kind} {serial}")
            vertices.append(_coordinate(*values, origin=origin, unit=unit, height_unit=height_unit))
    minimum = 2 if kind == "KURVE" else 1
    if len(vertices) < minimum:
        raise FormatError(f"{kind} {serial}: ventar minst {minimum} koordinatsett.")
    exact_count = {"PUNKT": 1, "BUEP": 3}.get(kind)
    if exact_count is not None and len(vertices) != exact_count:
        raise FormatError(f"{kind} {serial}: ventar nøyaktig {exact_count} koordinatsett.")
    return tuple(vertices)


def _surface_ring(serial, lines, entries, positions):
    markers = [i for i, line in enumerate(lines) if line.split(maxsplit=1)[0] == "..REF"]
    if len(markers) != 1:
        raise FormatError(f"Flate {serial}: ventar eitt REF-felt med kurvereferansar.")
    start = markers[0]
    references = lines[start][len("..REF"):].split()
    for line in lines[start + 1:]:
        if line.startswith(("..", "!")):
            break
        references.extend(line.split())
    if not references or any(not re.fullmatch(r":-?[1-9][0-9]{0,8}", ref) for ref in references):
        raise FormatError(f"Flate {serial}: importen støttar éi ytre ring av kurvereferansar.")
    ring = []
    boundary = []
    seen = set()
    for ref in references:
        curve_id = ref[1:].lstrip("-")
        if curve_id not in entries or entries[curve_id][0] not in {"KURVE", "BUEP"} or curve_id in seen:
            raise FormatError(f"Flate {serial}: kurvereferansen {ref} manglar eller er repetert.")
        seen.add(curve_id)
        edge = positions[curve_id]
        if ref.startswith(":-"):
            edge = edge[::-1]
        if ring and ring[-1] != edge[0]:
            raise FormatError(f"Flate {serial}: {ref} møter ikkje førre kurve i same koordinat.")
        ring.extend(edge[1:] if ring else edge)
        boundary.append((entries[curve_id][0], edge))
    if ring[0] != ring[-1] or len({vertex[:2] for vertex in ring}) < 3:
        raise FormatError(f"Flate {serial}: kurvereferansane dannar ikkje ei lukka ring.")
    return tuple(ring), tuple(boundary)


def _write_point(point, origin_north, origin_east):
    if not SERIAL.fullmatch(point.point_id):
        raise FormatError(f"SOSI-serienummeret {point.point_id!r} må vere eit positivt heiltal.")
    if not OBJECT_TYPE.fullmatch(point.code):
        raise FormatError(f"Punkt {point.point_id}: fyll inn éin OBJTYPE-verdi.")
    if point.calculation_code or not QUOTED_TEXT.fullmatch(f'"{point.note}"'):
        raise FormatError(f"Punkt {point.point_id}: feltinnhaldet kan ikkje skrivast i SOSI-profilen.")
    group = [f".PUNKT {point.point_id}:", f"..OBJTYPE {point.code}"]
    if point.note:
        group.append(f'..NAVN "{point.note}"')
    group.append("..NØ" if point.z is None else "..NØH")
    if point.z is not None and abs(point.z) >= 10**7:
        raise FormatError(f"Punkt {point.point_id}: høgda ligg utanfor SOSI-punktprofilen.")
    east, north, *height = (int(millimetres(value) / MM) for value in coordinates(point))
    scaled = (north - origin_north * 1000, east - origin_east * 1000, *height)
    if any(not -(2**31) <= value < 2**31 for value in scaled):
        raise FormatError(f"Punkt {point.point_id}: koordinat utanfor 32-bit SOSI-profilen.")
    group.append(" ".join(map(str, scaled)))
    return group


def encode(dataset):
    validate_points(dataset.points)
    crs_code = CODE_BY_CRS.get(dataset.crs)
    if not crs_code:
        raise FormatError("SOSI-eksport krev EUREF89 / UTM sone 32, 33 eller 35.")
    if dataset.height_datum is not None and dataset.height_datum not in HEIGHT_DATUMS:
        raise FormatError("SOSI-eksport støttar NN2000 og NN54.")
    if any(point.z is not None for point in dataset.points) and not dataset.height_datum:
        raise FormatError("Vel høgdesystem før eksport av 3D-punkt til SOSI.")

    east = [point.x for point in dataset.points]
    north = [point.y for point in dataset.points]
    origin_north, origin_east = floor(min(north)), floor(min(east))
    if any(abs(value) >= 10**8 for value in (origin_north, origin_east, max(north), max(east))):
        raise FormatError("Koordinatane ligg utanfor området til SOSI-punktprofilen.")
    header = [
        ".HODE", f"..TEGNSETT {OUTPUT_CHARSET}", "..TRANSPAR",
        f"...KOORDSYS {crs_code}", f"...ORIGO-NØ {origin_north} {origin_east}",
        "...ENHET 0.001",
    ]
    if dataset.height_datum:
        header.append(f"...VERT-DATUM {dataset.height_datum}")
    lines = header + [
        "..OMRÅDE", f"...MIN-NØ {origin_north} {origin_east}",
        f"...MAX-NØ {ceil(max(north))} {ceil(max(east))}",
        "..SOSI-VERSJON 4.5",
    ]
    for point in dataset.points:
        lines.extend(_write_point(point, origin_north, origin_east))
    try:
        return ("\r\n".join(lines + [".SLUTT", ""])).encode(ENCODINGS[OUTPUT_CHARSET])
    except UnicodeEncodeError as error:
        raise FormatError("SOSI-eksport støttar berre teikn i ISO8859-1.") from error
