"""Read and verify the supported prototypes without starting QGIS."""

from dataclasses import replace
from math import isclose
from pathlib import Path
from tempfile import NamedTemporaryFile

from . import kof, sosi
from .model import FormatError, coordinates


FORMATS = {".sos": sosi, ".kof": kof}
ROUNDTRIP_TOLERANCE = 0.000500002


def read_file(path):
    return read_file_with_format(path)[1]


def read_file_with_format(path):
    path = Path(path)
    if path.suffix:
        codec = _format(path)
        return path.suffix.lower(), codec.decode(path.read_bytes())

    # File dialogs can return a temporary copy without the original extension.
    with path.open("rb") as source:
        for line in source:
            if not line.strip() or line.startswith(b"-"):
                continue
            if line.startswith(b" 05 "):
                suffix = ".kof"
            elif line.split()[:1] == [b".HODE"]:
                suffix = ".sos"
            else:
                break
            source.seek(0)
            return suffix, FORMATS[suffix].decode(source.read())
    raise FormatError("Fila manglar filending, og innhaldet kunne ikkje kjennast att som SOSI eller KOF.")


def _format(path):
    codec = FORMATS.get(path.suffix.lower())
    if codec is None:
        raise FormatError("Vel ei fil med endinga .sos eller .kof.")
    return codec


def export_file(path, source):
    path = Path(path)
    codec = _format(path)
    content = codec.encode(source)
    # KOF does not carry CRS or a vertical datum. The UI reports this separately.
    expected = replace(source, crs=None, height_datum=None) if codec is kof else source
    rounded = _check_roundtrip(expected, codec.decode(content))
    write_atomic(path, content)
    return rounded


def write_atomic(path, content):
    temporary = NamedTemporaryFile(dir=path.parent, delete=False)
    staging = Path(temporary.name)
    try:
        with temporary:
            temporary.write(content)
        staging.replace(path)
    finally:
        staging.unlink(missing_ok=True)


def _check_roundtrip(expected, actual):
    if (
        expected.crs != actual.crs or expected.height_datum != actual.height_datum
        or len(expected.points) != len(actual.points)
    ):
        raise FormatError("Rundturen endra koordinatsystem, høgdesystem eller punkttal.")

    rounded = 0
    for before, after in zip(expected.points, actual.points):
        old = coordinates(before)
        new = coordinates(after)
        if len(old) != len(new) or replace(after, x=before.x, y=before.y, z=before.z) != before:
            raise FormatError(f"Rundturen endra dimensjonen eller eigenskapane til punkt {before.point_id}.")
        if any(not isclose(a, b, rel_tol=0, abs_tol=ROUNDTRIP_TOLERANCE) for a, b in zip(old, new)):
            raise FormatError(f"Rundturen endra koordinatane for mykje for punkt {before.point_id}.")
        rounded += sum(not isclose(a, b, rel_tol=0, abs_tol=1e-9) for a, b in zip(old, new))
    return rounded
