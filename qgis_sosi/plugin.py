"""User interface for importing and exporting SOSI and KOF files."""

from dataclasses import replace
from collections import Counter
import json
from pathlib import Path

from qgis.core import Qgis, QgsProject, QgsVectorLayer
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QAction
from qgis.PyQt.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QInputDialog, QLabel, QLineEdit, QMessageBox, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from .exchange import export_file, read_file, write_atomic
from .geopackage import save_layers
from .model import FormatError, HEIGHT_DATUMS, SosiVectorSet
from .qgis_points import FIELD_NAMES, create_layers, projected_crs, read_layer


TITLE = "SOSI og KOF"
SOSI_FILTER = "SOSI 4.5-punkt (*.sos)"
KOF_FILTER = "netLIN KOF 05-punkt (*.kof)"
FILTERS = f"{SOSI_FILTER};;{KOF_FILTER}"
INPUT_FILTERS = f"Alle støtta filer (*.sos *.kof);;SOSI 4.5 (*.sos);;{KOF_FILTER}"


class SurveyFilePlugin:
    def __init__(self, iface):
        self.iface = iface
        self.parent = iface.mainWindow()
        self.actions = []

    def initGui(self):
        for label, handler in (
            ("Importer filer (SOSI/KOF)", self.import_file),
            ("Eksporter aktivt lag (SOSI/KOF)", self.export_layer),
            ("Valider fil (SOSI/KOF)", self.validate_file),
            ("Importer filer til nytt GeoPackage", self.import_geopackage),
        ):
            action = QAction(label, self.parent)
            action.triggered.connect(handler)
            self.iface.addPluginToMenu(TITLE, action)
            self.actions.append(action)

    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(TITLE, action)
            action.deleteLater()
        self.actions.clear()

    def import_file(self):
        self._import_files(to_geopackage=False)

    def import_geopackage(self):
        self._import_files(to_geopackage=True)

    def _import_files(self, *, to_geopackage):
        names, _ = QFileDialog.getOpenFileNames(
            self.parent, "Vel SOSI- og KOF-filer", "", INPUT_FILTERS,
        )
        if not names:
            return
        paths = [Path(name) for name in dict.fromkeys(names)]
        destination = None
        if to_geopackage:
            destination = self._choose_package()
            if destination is None:
                return

        project = QgsProject.instance()
        results = []
        prepared = []
        common_kof = None
        remaining_kof = sum(path.suffix.lower() == ".kof" for path in paths)
        for path in paths:
            result = {"file": str(path), "status": "pending", "layers": [], "issues": []}
            results.append(result)
            suffix = path.suffix.lower()
            if suffix == ".kof":
                remaining_kof -= 1
            try:
                dataset = read_file(path)
                if suffix == ".kof":
                    options = common_kof or self._select_kof_options(path, dataset, remaining_kof > 0)
                    if options is None:
                        result["status"] = "skipped"
                        result["issues"].append(_issue("info", "import.cancelled", "KOF-innstillingane vart avbrotne."))
                        continue
                    crs, datum, reuse = options
                    if reuse:
                        common_kof = options
                    dataset = replace(dataset, crs=crs, height_datum=datum)
                layers = create_layers(dataset, path.stem, suffix)
                result["summary"] = self._summary(dataset)
                for layer in layers:
                    metadata = layer.metadata()
                    metadata.setTitle(layer.name())
                    metadata.setAbstract(f"Kjelde: {path.name}\n{result['summary']}")
                    layer.setMetadata(metadata)
                result["crs"] = dataset.crs
                result["height_datum"] = dataset.height_datum
                result["issues"].extend(_import_issues(dataset))
                prepared.append((path, layers, result))
            except (FormatError, OSError) as error:
                result["status"] = "error"
                result["issues"].append(_issue("error", "import.read", str(error)))

        if destination is not None and prepared:
            try:
                incoming = [layer for _, layers, _ in prepared for layer in layers]
                saved = iter(save_layers(destination, incoming, project.transformContext()))
                prepared = [(path, [next(saved) for _ in layers], result) for path, layers, result in prepared]
            except (FormatError, OSError) as error:
                for _, _, result in prepared:
                    result["status"] = "error"
                    result["issues"].append(_issue("error", "import.geopackage", str(error)))
                prepared = []

        for path, layers, result in prepared:
            group = project.layerTreeRoot().addGroup(path.name) if len(paths) > 1 else None
            project.addMapLayers(layers, group is None)
            if group is not None:
                for layer in layers:
                    group.addLayer(layer)
            for layer in layers:
                style_error = layer.customProperty("qgis_sosi/style_error", "")
                if style_error:
                    result["issues"].append(_issue("warning", "style.save", style_error))
            result["status"] = "imported"
            result["layers"] = [{"name": layer.name(), "features": layer.featureCount()} for layer in layers]
        self._show_import_report(results, destination)

    def _choose_package(self):
        name, _ = QFileDialog.getSaveFileName(
            self.parent, "Nytt GeoPackage", "", "GeoPackage (*.gpkg)",
            options=QFileDialog.Option.DontConfirmOverwrite,
        )
        if not name:
            return None
        path = Path(name)
        if not path.suffix:
            path = path.with_suffix(".gpkg")
        if path.suffix.lower() != ".gpkg" or path.exists():
            self._show_error("Vel ei ny fil med endinga .gpkg.")
            return None
        return path

    def _show_import_report(self, results, destination):
        imported = sum(result["status"] == "imported" for result in results)
        errors = sum(result["status"] == "error" for result in results)
        skipped = len(results) - imported - errors
        layer_count = sum(len(result["layers"]) for result in results)
        status_labels = {"imported": "Importert", "error": "Feil", "skipped": "Hoppa over"}
        details = []
        for result in results:
            detail = result.get("summary", "")
            issues = "\n".join(issue["message"] for issue in result["issues"])
            details.append("\n".join(filter(None, (
                f"{Path(result['file']).name} · {status_labels[result['status']]}", detail, issues,
            ))))
        message = QMessageBox(self.parent)
        message.setWindowTitle(TITLE)
        message.setTextFormat(Qt.TextFormat.PlainText)
        message.setIcon(QMessageBox.Icon.Warning if errors else QMessageBox.Icon.Information)
        message.setText(f"{imported} av {len(results)} filer importerte. {layer_count} lag.")
        subtitle = f"Feil: {errors}. Hoppa over: {skipped}."
        if len(results) == 1:
            subtitle += "\n\n" + details[0]
        message.setInformativeText(subtitle)
        message.setDetailedText("\n\n".join(details))
        message.setStandardButtons(QMessageBox.StandardButton.Ok)
        save = message.addButton("Lagre JSON-rapport", QMessageBox.ButtonRole.ActionRole)
        message.exec()
        if message.clickedButton() == save:
            self._save_import_report(results, destination)

    def _save_import_report(self, results, destination):
        name, _ = QFileDialog.getSaveFileName(
            self.parent, "Lagre importrapport", "sosi-kof-import.json", "JSON (*.json)",
        )
        if not name:
            return
        path = Path(name)
        if not path.suffix:
            path = path.with_suffix(".json")
        try:
            if path.suffix.lower() != ".json":
                raise FormatError("Rapporten må ha endinga .json.")
            payload = {"geopackage": str(destination) if destination else None, "files": results}
            content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
            write_atomic(path, content.encode("utf-8"))
        except (FormatError, OSError) as error:
            self._show_error(error)

    def export_layer(self):
        filename, file_filter = QFileDialog.getSaveFileName(
            self.parent, "Eksporter det aktive punktlaget", "", FILTERS,
        )
        if not filename:
            return
        suffix = ".kof" if file_filter == KOF_FILTER else ".sos"
        path = Path(filename)
        if not path.suffix:
            path = path.with_suffix(suffix)
        try:
            if path.suffix.lower() != suffix:
                raise FormatError("Filendinga må samsvare med formatet du valde.")
            layer = self.iface.activeLayer()
            mapping = None
            if suffix == ".kof":
                mapping = self._select_kof_mapping(layer)
                if mapping is None:
                    return
            dataset = read_layer(layer, suffix, mapping)
            if suffix == ".sos" and dataset.height_datum is None and any(
                point.z is not None for point in dataset.points
            ):
                datum, ok = self._select_height()
                if not ok:
                    return
                dataset = replace(dataset, height_datum=datum)
            rounded = export_file(path, dataset)
            text = f"Skrive {len(dataset.points)} punkt til {path.name}. Intern rundtur bestått."
            if rounded:
                text += f" {rounded} koordinatverdiar er avrunda til millimeter."
            if suffix == ".kof":
                text += f" KOF-fila lagrar ikkje {dataset.crs} eller høgdesystem."
                omitted = sorted(set(layer.fields().names()).difference(mapping.values()))
                if omitted:
                    text += f" Felt utan mapping: {', '.join(omitted)}."
            elif any(point.z is not None for point in dataset.points):
                text += " Bruk denne utvidinga ved ny import for å få med Z."
            QMessageBox.information(self.parent, TITLE, text)
        except (FormatError, OSError) as error:
            self._show_error(error)

    def validate_file(self):
        path = self._select_input("Valider SOSI- eller KOF-fil")
        if path is None:
            return
        try:
            dataset = read_file(path)
            text = f"Intern formatkontroll bestått. {self._summary(dataset)}"
            QMessageBox.information(self.parent, TITLE, text)
        except (FormatError, OSError) as error:
            self._show_error(error)

    def _select_input(self, title):
        filename, _ = QFileDialog.getOpenFileName(
            self.parent, title, "", INPUT_FILTERS,
        )
        return Path(filename) if filename else None

    def _select_kof_options(self, path, dataset, can_reuse):
        dialog = QDialog(self.parent)
        dialog.setWindowTitle(f"KOF-import · {path.name}")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("netLIN 05 les X som nord og Y som aust. Kontroller dei første punkta."))
        points = dataset.points[:6]
        preview = QTableWidget(len(points), 6)
        preview.setHorizontalHeaderLabels(["Punkt-ID", "Nord", "Aust", "Høgd", "Temakode", "Merknad"])
        preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for row, point in enumerate(points):
            values = [point.point_id, point.y, point.x, point.z, point.code, point.note]
            for column, value in enumerate(values):
                preview.setItem(row, column, QTableWidgetItem("" if value is None else str(value)))
        preview.resizeColumnsToContents()
        layout.addWidget(preview)
        form = QFormLayout()
        code = QLineEdit()
        code.setPlaceholderText("t.d. 25832")
        form.addRow("Kjelde-CRS (EPSG)", code)
        height = QComboBox()
        height.addItem("Ukjent")
        height.addItems(HEIGHT_DATUMS)
        form.addRow("Høgdesystem", height)
        layout.addLayout(form)
        common = QCheckBox("Bruk same CRS og høgdesystem for resten av KOF-filene")
        if can_reuse:
            layout.addWidget(common)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.resize(620, 330)
        while dialog.exec() == QDialog.DialogCode.Accepted:
            authid = code.text().strip().upper()
            if authid.isdecimal():
                authid = f"EPSG:{authid}"
            try:
                crs = projected_crs(authid).authid()
            except FormatError as error:
                QMessageBox.warning(dialog, TITLE, str(error))
                continue
            return crs, height.currentText() if height.currentIndex() else None, common.isChecked()
        return None

    def _select_kof_mapping(self, layer):
        if not isinstance(layer, QgsVectorLayer) or layer.wkbType() not in (Qgis.WkbType.Point, Qgis.WkbType.PointZ):
            raise FormatError("Vel eit aktivt lag med enkeltpunkt i 2D eller 3D.")
        field_names = layer.fields().names()
        if not field_names:
            raise FormatError("Punktlaget må ha eit felt som kan brukast som punkt-ID.")
        dialog = QDialog(self.parent)
        dialog.setWindowTitle("Feltmapping for KOF-eksport")
        form = QFormLayout(dialog)
        form.addRow(QLabel("Nord, aust og eventuell høgd blir lesne frå geometrien i punktlaget."))
        inputs = {}
        for index, (field, label) in enumerate(zip(
            FIELD_NAMES[".kof"], ("Punkt-ID", "Temakode", "Merknad", "Berekningskode"),
        )):
            box = QComboBox()
            box.addItem("Vel felt" if index == 0 else "Utan felt", None)
            for name in field_names:
                box.addItem(name, name)
            box.setCurrentIndex(max(0, box.findData(field)))
            form.addRow(label, box)
            inputs[field] = box
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        form.addRow(buttons)
        confirm = buttons.button(QDialogButtonBox.StandardButton.Ok)
        id_picker = inputs["punkt_id"]
        confirm.setEnabled(id_picker.currentIndex() > 0)
        id_picker.currentIndexChanged.connect(lambda index: confirm.setEnabled(index > 0))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return {field: box.currentData() for field, box in inputs.items()}
        return None

    def _select_height(self):
        return QInputDialog.getItem(
            self.parent, "Høgdesystem", "Vel høgdesystemet til høgdeverdiane i meter.",
            list(HEIGHT_DATUMS), editable=False,
        )

    def _summary(self, dataset):
        if isinstance(dataset, SosiVectorSet):
            counts = Counter(feature.kind for feature in dataset.features)
            labels = {"PUNKT": "punkt", "KURVE": "kurver", "BUEP": "bogar", "FLATE": "flater",
                      "TEKST": "tekstobjekt", "SYMBOL": "symbol"}
            objects = ", ".join(f"{counts[kind]} {label}" for kind, label in labels.items() if counts[kind])
            text = (
                f"{objects}. CRS {dataset.crs}. "
                f"Høgdesystem {dataset.height_datum or 'ukjent'}."
            )
            collapsed = [
                feature.serial for feature in dataset.features
                if feature.kind == "KURVE" and len({vertex[:2] for vertex in feature.vertices}) < 2
            ]
            if collapsed:
                serials = ", ".join(collapsed[:5])
                text += f" {len(collapsed)} kurve(r) med null lengd i grunnriss er bevarte, mellom anna ID {serials}."
            return text
        elevated = sum(point.z is not None for point in dataset.points)
        text = f"{len(dataset.points)} punkt, {elevated} med høgd. CRS {dataset.crs or 'ikkje oppgitt i fila'}."
        if elevated:
            text += f" Høgdesystem {dataset.height_datum or 'ukjent'}."
        return text

    def _show_error(self, error):
        QMessageBox.warning(self.parent, TITLE, str(error))


def _issue(severity, rule, message, object_id=None):
    return {"severity": severity, "rule": rule, "message": message, "object_id": object_id}


def _import_issues(dataset):
    if isinstance(dataset, SosiVectorSet):
        return [
            _issue("warning", "geometry.zero_xy_length", f"Kurve {feature.serial} har null lengd i grunnriss.",
                   feature.serial)
            for feature in dataset.features
            if feature.kind == "KURVE" and len({vertex[:2] for vertex in feature.vertices}) < 2
        ]
    if not dataset.height_datum and any(point.z is not None for point in dataset.points):
        return [_issue("warning", "crs.unknown_height_datum", "Punkta har Z med ukjent høgdesystem.")]
    return []
