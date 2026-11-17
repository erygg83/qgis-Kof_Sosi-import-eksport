"""Map the supported SOSI and KOF geometries to and from PyQGIS memory layers."""

from qgis.core import (
    Qgis, QgsCircularString, QgsCompoundCurve, QgsCoordinateReferenceSystem,
    QgsCurvePolygon, QgsFeature, QgsField, QgsGeometry, QgsLineString, QgsPoint,
    QgsPointXY, QgsPolygon, QgsVariantUtils, QgsVectorLayer,
)
from qgis.PyQt.QtCore import QMetaType

from .model import FormatError, PointSet, SosiVectorSet, SurveyPoint
from .styles import apply_sosi_style


HEIGHT_PROPERTY = "qgis_sosi/height_datum"
FIELD_NAMES = {
    ".sos": ("punkt_id", "objtype", "navn"),
    ".kof": ("punkt_id", "temakode", "merknad", "berekningskode"),
}
SOSI_VECTOR_FIELDS = {
    "..OBJTYPE": "objtype", "...LOKALID": "lokalid", "...NAVNEROM": "navnerom",
    "...VERSJONID": "versjonid", "..VREF": "vref", "..STRENG": "sosi_tekst",
    "..TEKSTTYPE": "teksttype", "..ARTYPE": "artype",
}
GEOMETRY_LABELS = {
    ("PUNKT", "Point"): "Punkt", ("KURVE", "LineString"): "Kurver",
    ("BUEP", "CircularString"): "Bogar", ("FLATE", "Polygon"): "Flater",
    ("FLATE", "CurvePolygon"): "Flater med boge", ("SYMBOL", "Point"): "Symbol",
    ("TEKST", "Point"): "Tekst", ("TEKST", "LineString"): "Tekst langs kurve",
}


def projected_crs(authid):
    crs = QgsCoordinateReferenceSystem(authid or "")
    if (
        not crs.isValid() or crs.type() != Qgis.CrsType.Projected
        or crs.mapUnits() != Qgis.DistanceUnit.Meters
    ):
        raise FormatError("Vel eit gyldig projisert koordinatsystem med meter som eining.")
    return crs


def create_layers(dataset, name, suffix):
    if isinstance(dataset, SosiVectorSet):
        return _create_sosi_vector_layers(dataset, name)
    crs = projected_crs(dataset.crs)
    field_names = FIELD_NAMES[suffix]
    layers = []
    for has_z in (False, True):
        points = [point for point in dataset.points if (point.z is not None) == has_z]
        if not points:
            continue
        geometry_type = "PointZ" if has_z else "Point"
        dimension = "3D" if has_z else "2D"
        layer = _memory_layer(
            geometry_type, f"{name} ({dimension})", crs, dataset.height_datum, field_names,
        )
        features = []
        for point in points:
            feature = QgsFeature(layer.fields())
            attributes = [point.point_id, point.code, point.note, point.calculation_code]
            feature.setAttributes(attributes[:len(field_names)])
            if has_z:
                feature.setGeometry(QgsGeometry(QgsPoint(point.x, point.y, point.z)))
            else:
                feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(point.x, point.y)))
            features.append(feature)
        _add_features(layer, features)
        if suffix == ".sos":
            apply_sosi_style(layer)
        layers.append(layer)
    return layers


def _create_sosi_vector_layers(dataset, name):
    crs = projected_crs(dataset.crs)
    grouped = {}
    for feature in dataset.features:
        geometry_type = _sosi_geometry_type(feature)
        key = feature.kind, geometry_type, len(feature.vertices[0])
        grouped.setdefault(key, []).append(feature)

    layers = []
    for kind, geometry_type in GEOMETRY_LABELS:
        for dimensions in (2, 3):
            group = grouped.get((kind, geometry_type, dimensions))
            if group:
                label = GEOMETRY_LABELS[kind, geometry_type]
                layers.append(_sosi_layer(group, name, geometry_type, dimensions, label, crs, dataset))
    return layers


def _sosi_layer(group, name, geometry_type, dimensions, label, crs, dataset):
    fields = ("sosi_id", *SOSI_VECTOR_FIELDS.values(), "sosi_kjelde")
    layer = _memory_layer(
        geometry_type + ("Z" if dimensions == 3 else ""), f"{name} ({label} {dimensions}D)",
        crs, dataset.height_datum, fields,
    )
    kind = group[0].kind
    layer.setCustomProperty("qgis_sosi/catalogue", dataset.catalogue)
    layer.setCustomProperty("qgis_sosi/geometry", kind)
    features = []
    for source in group:
        feature = QgsFeature(layer.fields())
        attributes = {}
        for line in source.source_lines:
            parts = line.split(maxsplit=1)
            if len(parts) != 2 or parts[0] not in SOSI_VECTOR_FIELDS:
                continue
            key, value = parts
            if len(value) >= 2 and value[0] in ("'", '"') and value[0] == value[-1]:
                value = value[1:-1]
            if key == "..STRENG" and key in attributes:
                value = attributes[key] + "\n" + value
            attributes[key] = value
        source_group = "\n".join((f".{kind} {source.serial}:", *source.source_lines))
        feature.setAttributes([
            source.serial, *(attributes.get(key, "") for key in SOSI_VECTOR_FIELDS), source_group,
        ])
        feature.setGeometry(_sosi_geometry(source, geometry_type))
        features.append(feature)
    _add_features(layer, features)
    apply_sosi_style(layer)
    return layer


def _sosi_geometry_type(feature):
    if feature.kind == "FLATE":
        return "CurvePolygon" if any(kind == "BUEP" for kind, _ in feature.boundary) else "Polygon"
    if feature.kind == "BUEP":
        return "CircularString"
    if feature.kind == "KURVE" or (
        feature.kind == "TEKST" and len(feature.vertices) > 3
        and len({vertex[:2] for vertex in feature.vertices[1:]}) > 1
    ):
        return "LineString"
    return "Point"


def _sosi_geometry(source, geometry_type):
    points = [QgsPoint(*vertex) for vertex in source.vertices]
    if geometry_type == "Point":
        index = 1 if source.kind in {"TEKST", "SYMBOL"} and len(points) > 1 else 0
        return QgsGeometry(points[index])
    if geometry_type == "LineString":
        return QgsGeometry(QgsLineString(points[1:] if source.kind == "TEKST" else points))
    if geometry_type == "CircularString":
        arc = QgsCircularString()
        arc.setPoints(points)
        return QgsGeometry(arc)
    if geometry_type == "CurvePolygon":
        boundary = QgsCompoundCurve()
        for kind, vertices in source.boundary:
            edge = [QgsPoint(*vertex) for vertex in vertices]
            if kind == "BUEP":
                arc = QgsCircularString()
                arc.setPoints(edge)
                boundary.addCurve(arc)
            else:
                boundary.addCurve(QgsLineString(edge))
        polygon = QgsCurvePolygon()
        polygon.setExteriorRing(boundary)
    else:
        polygon = QgsPolygon()
        polygon.setExteriorRing(QgsLineString(points))
    return QgsGeometry(polygon)


def _memory_layer(geometry_type, name, crs, height_datum, field_names):
    layer = QgsVectorLayer(geometry_type, name, "memory")
    if not layer.isValid():
        raise FormatError("QGIS kunne ikkje opprette laget.")
    layer.setCrs(crs)
    layer.setCustomProperty(HEIGHT_PROPERTY, height_datum or "")
    fields = [QgsField(field, QMetaType.Type.QString) for field in field_names]
    if not layer.dataProvider().addAttributes(fields):
        raise FormatError("QGIS kunne ikkje opprette felt i laget.")
    layer.updateFields()
    return layer


def _add_features(layer, features):
    added, _ = layer.dataProvider().addFeatures(features)
    if not added:
        raise FormatError("QGIS kunne ikkje leggje objekta til i laget.")
    layer.updateExtents()


def read_layer(layer, suffix, mapping=None):
    if not isinstance(layer, QgsVectorLayer) or layer.wkbType() not in (
        Qgis.WkbType.Point, Qgis.WkbType.PointZ,
    ):
        raise FormatError("Vel eit aktivt lag med enkeltpunkt i 2D eller 3D.")
    crs = projected_crs(layer.crs().authid())
    field_names = FIELD_NAMES[suffix]
    layer_fields = set(layer.fields().names())
    if mapping is None:
        if "punkt_id" not in layer_fields:
            raise FormatError("Det aktive laget må ha feltet punkt_id.")
        unsupported = sorted(layer_fields.difference(field_names))
        if unsupported:
            raise FormatError(f"Desse felta kan ikkje eksporterast i prototypen: {', '.join(unsupported)}.")
        source_fields = field_names
    else:
        source_fields = [mapping.get(field) for field in field_names]
        if source_fields[0] is None or any(field not in layer_fields for field in source_fields if field is not None):
            raise FormatError("Vel eit gyldig felt for punkt-ID og eventuelle tilleggsfelt.")

    points = []
    for feature in layer.getFeatures():
        geometry = feature.geometry()
        if geometry.isEmpty() or geometry.wkbType() not in (Qgis.WkbType.Point, Qgis.WkbType.PointZ):
            raise FormatError(f"Objekt {feature.id()} har ugyldig punktgeometri.")
        vertex = geometry.constGet()
        values = [_text_attribute(feature, field, layer_fields) for field in source_fields]
        point_id, code, note, *calculation = values
        points.append(SurveyPoint(
            point_id, vertex.x(), vertex.y(), vertex.z() if vertex.is3D() else None,
            code, note, *calculation,
        ))
    return PointSet(
        tuple(points), crs.authid(), layer.customProperty(HEIGHT_PROPERTY, "") or None,
    )


def _text_attribute(feature, field, layer_fields):
    if field not in layer_fields:
        return ""
    index = feature.fieldNameIndex(field)
    value = feature.attribute(index)
    return "" if QgsVariantUtils.isNull(value) else str(value)
