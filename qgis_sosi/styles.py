"""Readable QGIS map styles for the supported SOSI object types."""

from qgis.PyQt.QtGui import QColor, QFont
from qgis.core import (
    Qgis, QgsCategorizedSymbolRenderer, QgsFillSymbol, QgsLineSymbol,
    QgsMarkerSymbol, QgsPalLayerSettings, QgsProperty, QgsPropertyCollection,
    QgsRendererCategory, QgsSingleSymbolRenderer, QgsTextBufferSettings,
    QgsTextFormat, QgsVectorLayerSimpleLabeling,
)


POINTS = {
    "EL_Belysningspunkt": ("Belysningspunkt", "circle", "#e7ab20", "#78530f", 2.5),
    "Mast": ("Mast", "triangle", "#9b6828", "#56360f", 2.7),
    "Skap": ("Skap", "square", "#674d36", "#352819", 2.4),
    "Kumlokk": ("Kumlokk", "circle", "#f7fbff", "#17679f", 2.7),
    "VA_Sluk": ("Sluk", "square", "#4295bd", "#125278", 2.5),
    "VA_Hydrant": ("Hydrant", "triangle", "#28669b", "#123957", 2.6),
    "Teiggrensepunkt": ("Teiggrensepunkt", "circle", "#ffffff", "#a53248", 1.7),
    "PblTiltak": ("PBL-tiltak", "diamond", "#aa65b3", "#63346f", 2.7),
    "Fastmerke": ("Fastmerke", "cross", "#33495e", "#233443", 2.6),
}
LINES = {
    "Eiendomsgrense": ("Eigedomsgrense", "#a53248", 0.26, "solid"),
    "Hjelpelinje": ("Hjelpelinje", "#9e6d78", 0.17, "dash"),
    "KantUtsnitt": ("Kant av kartutsnitt", "#8a9197", 0.15, "dot"),
    "Hekk": ("Hekk", "#347339", 0.40, "dot"),
    "TiltakGrense": ("Tiltaksgrense", "#864389", 0.28, "dash"),
    "Vegdekkekant": ("Vegdekkekant", "#555557", 0.25, "solid"),
    "VegkantAvkjørsel": ("Avkøyrsel", "#77736f", 0.20, "solid"),
    "AnnetVegarealAvgrensning": ("Anna vegareal", "#7f766c", 0.19, "solid"),
    "VegkantAnnetVegareal": ("Anna vegareal", "#7f766c", 0.19, "solid"),
    "VegkantFiktiv": ("Fiktiv vegkant", "#8b8987", 0.18, "dash"),
    "Fortauskant": ("Fortauskant", "#6b6257", 0.18, "solid"),
    "VeggrøftÅpen": ("Open veggrøft", "#5887a0", 0.23, "dash"),
    "Vegrekkverk": ("Vegrekkverk", "#504236", 0.24, "dash"),
    "ElvBekk": ("Elv og bekk", "#337ea6", 0.34, "solid"),
    "Innsjøkant": ("Innsjøkant", "#347ca0", 0.21, "solid"),
    "Høydekurve": ("Høgdekurve", "#a57449", 0.16, "solid"),
}
AREAS = {
    "Teig": ("Eigedomsteig", "165,50,72,14", "#a53248", 0.13),
    "PblTiltak": ("PBL-tiltak", "170,101,179,52", "#864389", 0.20),
    "Veg": ("Vegflate", "204,198,186,160", "#77736f", 0.19),
    "Innsjø": ("Innsjø", "157,206,230,170", "#347ca0", 0.18),
    "ElvBekk": ("Elv og bekk", "157,206,230,170", "#347ca0", 0.18),
}
AR5 = {
    "21": ("Fulldyrka jord", "square", "#d5a848", "#92661d", 2.6),
    "22": ("Overflatedyrka jord", "diamond", "#e0bb64", "#92661d", 2.6),
    "23": ("Innmarksbeite", "triangle", "#b2aa56", "#68672b", 2.6),
    "30": ("Skog", "triangle", "#6a9a54", "#3d6733", 2.8),
}


def _point(style):
    _, shape, color, outline, size = style
    return QgsMarkerSymbol.createSimple({
        "name": shape, "color": color, "outline_color": outline,
        "outline_width": "0.28", "size": str(size),
    })


def _line(style):
    _, color, width, pattern = style
    return QgsLineSymbol.createSimple({
        "line_color": color, "line_width": str(width), "line_style": pattern,
    })


def _area(style):
    _, fill, outline, width = style
    return QgsFillSymbol.createSimple({
        "color": fill, "outline_color": outline, "outline_width": str(width),
    })


def apply_map_color(layer, color):
    """Use one ink for the chosen layers, retaining SOSI text placement."""
    layer.setCustomProperty("qgis_sosi/style", color.name())
    if layer.labelsEnabled() and layer.labeling() is not None:
        settings = layer.labeling().settings()
        properties = settings.dataDefinedProperties()
        properties.setProperty(QgsPalLayerSettings.Property.Color, QgsProperty())
        settings.setDataDefinedProperties(properties)
        text = settings.format()
        text.setColor(color)
        settings.setFormat(text)
        layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
        return
    ink = color.name()
    if layer.geometryType() == Qgis.GeometryType.Point:
        symbol = _point(("", "circle", ink, color.darker(135).name(), 2.3))
    elif layer.geometryType() == Qgis.GeometryType.Line:
        symbol = _line(("", ink, 0.28, "solid"))
    else:
        fill = f"{color.red()},{color.green()},{color.blue()},55"
        symbol = _area(("", fill, ink, 0.22))
    layer.setRenderer(QgsSingleSymbolRenderer(symbol))


def apply_sosi_style(layer):
    """Apply local display rules with one legend entry per observed category."""
    if "objtype" not in layer.fields().names():
        return
    layer.setCustomProperty("qgis_sosi/style", "sosi-display")
    kind = layer.customProperty("qgis_sosi/geometry", "")
    if kind == "TEKST":
        _label_layer(layer)
        return
    if kind == "SYMBOL" and layer.uniqueValues(layer.fields().indexFromName("objtype")) == {"AR5Symbol"}:
        _categorize(layer, "artype", AR5, _point, ("", "diamond", "#8c9767", "#515a36", 2.5))
        return

    rules, factory, default = {
        Qgis.GeometryType.Point: (POINTS, _point, ("", "circle", "#688092", "#33495e", 2.1)),
        Qgis.GeometryType.Line: (LINES, _line, ("", "#697a85", 0.24, "solid")),
        Qgis.GeometryType.Polygon: (AREAS, _area, ("", "121,150,160,48", "#526873", 0.19)),
    }[layer.geometryType()]
    _categorize(layer, "objtype", rules, factory, default)


def _categorize(layer, field, rules, factory, default):
    values = layer.uniqueValues(layer.fields().indexFromName(field))
    categories = []
    for value in sorted(values, key=str):
        style = rules.get(value, default)
        categories.append(QgsRendererCategory(value, factory(style), style[0] or str(value) or "Ukjend type"))
    layer.setRenderer(QgsCategorizedSymbolRenderer(field, categories))


def _label_layer(layer):
    if layer.geometryType() == Qgis.GeometryType.Line:
        symbol = _line(("", "0,0,0,0", 0.1, "solid"))
        placement = Qgis.LabelPlacement.Curved
    else:
        symbol = _point(("", "circle", "0,0,0,0", "0,0,0,0", 0.4))
        placement = Qgis.LabelPlacement.OverPoint
    layer.setRenderer(QgsSingleSymbolRenderer(symbol))
    settings = QgsPalLayerSettings()
    settings.fieldName = "sosi_tekst"
    settings.placement = placement
    properties = QgsPropertyCollection()
    properties.setProperty(QgsPalLayerSettings.Property.Size, QgsProperty.fromExpression(
        """CASE WHEN "objtype" = 'StedsnavnTekst' THEN 10.5 WHEN "teksttype" = 'eiendom' THEN 8 ELSE 9 END""",
    ))
    properties.setProperty(QgsPalLayerSettings.Property.Color, QgsProperty.fromExpression(
        """CASE WHEN "teksttype" = 'eiendom' THEN '#99384d' ELSE '#28343b' END""",
    ))
    properties.setProperty(QgsPalLayerSettings.Property.Italic, QgsProperty.fromExpression(
        "\"teksttype\" = 'vegnavn'",
    ))
    settings.setDataDefinedProperties(properties)
    text = QgsTextFormat()
    text.setFont(QFont("Arial"))
    text.setSize(9)
    text.setColor(QColor("#28343b"))
    buffer = QgsTextBufferSettings()
    buffer.setEnabled(True)
    buffer.setSize(0.55)
    buffer.setColor(QColor("#ffffff"))
    text.setBuffer(buffer)
    settings.setFormat(text)
    layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
    layer.setLabelsEnabled(True)
