"""Write a batch of imported layers to a new GeoPackage."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from qgis.core import QgsMapLayer, QgsVectorFileWriter, QgsVectorLayer

from .model import FormatError


def save_layers(destination, layers, transform_context):
    if destination.exists():
        raise FormatError("Vel eit nytt GeoPackage. Fila finst frå før.")

    writer = QgsVectorFileWriter
    table_names = []
    with TemporaryDirectory(dir=destination.parent) as folder:
        staged = Path(folder) / "import.gpkg"
        for index, layer in enumerate(layers, start=1):
            table = f"import_{index:03}"
            options = writer.SaveVectorOptions()
            options.driverName = "GPKG"
            options.layerName = table
            options.layerOptions = [f"IDENTIFIER={index:03} {layer.name()}"]
            if index > 1:
                options.actionOnExistingFile = writer.ActionOnExistingFile.CreateOrOverwriteLayer
            options.saveMetadata = True
            options.layerMetadata = layer.metadata()
            error, _, _, message = writer.writeAsVectorFormatV3(layer, str(staged), transform_context, options)
            if error != writer.WriterError.NoError:
                raise FormatError(f"Kunne ikkje lagre {layer.name()} i GeoPackage. {message}")
            table_names.append(table)

        # Publish the finished package without replacing a destination another process created.
        if os.name == "nt":
            staged.rename(destination)
        else:
            os.link(staged, destination)

    saved = []
    for table, original in zip(table_names, layers):
        layer = QgsVectorLayer(f"{destination}|layername={table}", original.name(), "ogr")
        if (not layer.isValid() or layer.featureCount() != original.featureCount()
                or layer.wkbType() != original.wkbType()):
            raise FormatError(f"GeoPackage er skrive, men QGIS kunne ikkje kontrollere {table}.")
        for key in original.customPropertyKeys():
            layer.setCustomProperty(key, original.customProperty(key))
        if original.customProperty("qgis_sosi/style", ""):
            _save_style(layer, original)
        saved.append(layer)
    return saved


def _save_style(layer, source):
    layer.setRenderer(source.renderer().clone())
    if source.labeling() is not None:
        layer.setLabeling(source.labeling().clone())
        layer.setLabelsEnabled(source.labelsEnabled())
    categories = QgsMapLayer.StyleCategory.Symbology | QgsMapLayer.StyleCategory.Labeling
    result, message = layer.saveStyleToDatabaseV2("Kartstil", "Kartstil frå SOSI og KOF", True, "", categories)
    failures = (
        QgsMapLayer.SaveStyleResult.QmlGenerationFailed.value
        | QgsMapLayer.SaveStyleResult.DatabaseWriteFailed.value
    )
    if result.value & failures:
        layer.setCustomProperty(
            "qgis_sosi/style_error",
            f"Kunne ikkje lagre teiknereglane for {source.name()} i GeoPackage. {message}",
        )
