from contextlib import closing
from dataclasses import replace
import json
import os
from pathlib import Path
from shutil import copyfile
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from qgis_sosi.exchange import export_file, read_file
from qgis_sosi.model import FormatError
from test_sosi_vectors import PRESENTATION_SAMPLE, VECTOR_SAMPLE

try:
    from osgeo import gdal
    from qgis.core import Qgis, QgsApplication, QgsProject
    from qgis.PyQt.QtWidgets import QCheckBox, QComboBox, QDialog, QLineEdit, QTableWidget
except ImportError as error:
    QGIS_UNAVAILABLE = str(error)
else:
    from qgis_sosi.plugin import KOF_FILTER, SOSI_FILTER, SurveyFilePlugin
    from qgis_sosi.qgis_points import create_layers, projected_crs, read_layer

    QGIS_UNAVAILABLE = ""


FIXTURES = Path(__file__).with_name("fixtures")


class TestInterface:
    def __init__(self):
        self.actions = []
        self.active_layer = None

    def mainWindow(self):
        return None

    def activeLayer(self):
        return self.active_layer

    def addPluginToMenu(self, _name, action):
        self.actions.append(action)

    def removePluginMenu(self, _name, action):
        self.actions.remove(action)


@unittest.skipIf(QGIS_UNAVAILABLE, f"Krev QGIS Python: {QGIS_UNAVAILABLE}")
class QgisPointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QgsApplication([], False)
        cls.app.initQgis()
        gdal.UseExceptions()

    @classmethod
    def tearDownClass(cls):
        QgsProject.instance().clear()
        cls.app.exitQgis()

    def test_rejects_geographic_or_unrecognised_kof_crs(self):
        for code in ("EPSG:4326", "EPSG:9999999", ""):
            with self.subTest(code=code), self.assertRaises(FormatError):
                projected_crs(code)

    def test_sosi_points_via_real_qgis_layers(self):
        data = read_file(FIXTURES / "utm32_points.sos")
        layers = create_layers(data, "SOSI", ".sos")
        self.assertEqual([layer.wkbType() for layer in layers],
                         [Qgis.WkbType.Point, Qgis.WkbType.PointZ])
        with TemporaryDirectory() as folder:
            for number, layer in enumerate(layers):
                layer_data = read_layer(layer, ".sos")
                expected = tuple(point for point in data.points if (point.z is not None) == bool(number))
                self.assertEqual(layer_data, replace(data, points=expected))
                path = Path(folder) / f"qgis{number}.sos"
                self.assertEqual(export_file(path, layer_data), 0)
                self.assertEqual(read_file(path), layer_data)

    def test_sosi_export_opens_in_gdal_with_expected_xy_and_attributes(self):
        if gdal.GetDriverByName("SOSI") is None:
            self.skipTest("GDAL SOSI-drivaren manglar.")
        source = read_file(FIXTURES / "utm32_points.sos")
        with TemporaryDirectory() as folder:
            for points in (source.points[:1], source.points[1:]):
                path = Path(folder) / "independent.sos"
                export_file(path, replace(source, points=points))
                with gdal.OpenEx(str(path), gdal.OF_VECTOR, allowed_drivers=["SOSI"]) as data:
                    layer = data.GetLayer(0)
                    self.assertIn(layer.GetSpatialRef().GetAuthorityCode(None), {"3044", "25832"})
                    self.assertEqual(layer.GetFeatureCount(), len(points))
                    for point, feature in zip(points, layer):
                        geometry = feature.GetGeometryRef()
                        self.assertAlmostEqual(geometry.GetX(), point.x, places=8)
                        self.assertAlmostEqual(geometry.GetY(), point.y, places=8)
                        self.assertEqual(feature["navn"], point.note)
                        self.assertEqual(feature["objekttypenavn"], point.code)

    def test_kof_menu_import_validate_export_and_unload(self):
        path = FIXTURES / "netlin05_points.kof"
        expected = read_file(path)
        iface = TestInterface()
        plugin = SurveyFilePlugin(iface)
        plugin.initGui()
        self.addCleanup(plugin.unload)
        self.addCleanup(QgsProject.instance().clear)
        self.assertEqual(len(iface.actions), 4)

        with (
            patch("qgis_sosi.plugin.QFileDialog.getOpenFileName", return_value=(str(path), KOF_FILTER)),
            patch("qgis_sosi.plugin.QFileDialog.getOpenFileNames", return_value=([str(path)], KOF_FILTER)),
            patch.object(plugin, "_select_kof_options", return_value=("EPSG:25832", "NN2000", False)),
            patch.object(plugin, "_show_import_report") as imported,
            patch.object(plugin, "_select_kof_mapping", return_value={
                "punkt_id": "punkt_id", "temakode": "temakode",
                "merknad": "merknad", "berekningskode": "berekningskode",
            }),
            patch("qgis_sosi.plugin.QMessageBox.information") as report,
            patch("qgis_sosi.plugin.QMessageBox.warning") as warning,
            TemporaryDirectory() as folder,
        ):
            iface.actions[2].trigger()
            iface.actions[0].trigger()
            layers = sorted(QgsProject.instance().mapLayers().values(), key=lambda layer: layer.name())
            self.assertEqual([layer.featureCount() for layer in layers], [1, 3])
            for number, layer in enumerate(layers):
                iface.active_layer = layer
                output = str(Path(folder) / f"qgis{number}.kof")
                with patch("qgis_sosi.plugin.QFileDialog.getSaveFileName", return_value=(output, KOF_FILTER)):
                    iface.actions[1].trigger()
                points = tuple(point for point in expected.points if (point.z is not None) == bool(number))
                self.assertEqual(read_file(output), replace(expected, points=points))
            warning.assert_not_called()
            self.assertEqual(report.call_count, 3)
            self.assertEqual(imported.call_args.args[0][0]["status"], "imported")
        plugin.unload()
        self.assertEqual(iface.actions, [])

    def test_sosi_menu_import_and_export(self):
        source = FIXTURES / "utm32_points.sos"
        iface = TestInterface()
        plugin = SurveyFilePlugin(iface)
        plugin.initGui()
        self.addCleanup(plugin.unload)
        self.addCleanup(QgsProject.instance().clear)
        with (
            patch("qgis_sosi.plugin.QFileDialog.getOpenFileNames", return_value=([str(source)], SOSI_FILTER)),
            patch.object(plugin, "_show_import_report"),
            patch("qgis_sosi.plugin.QMessageBox.information") as report,
            patch("qgis_sosi.plugin.QMessageBox.warning") as warning,
            TemporaryDirectory() as folder,
        ):
            iface.actions[0].trigger()
            iface.active_layer = next(
                layer for layer in QgsProject.instance().mapLayers().values()
                if layer.wkbType() == Qgis.WkbType.Point
            )
            destination = str(Path(folder) / "qgis.sos")
            with patch("qgis_sosi.plugin.QFileDialog.getSaveFileName", return_value=(destination, SOSI_FILTER)):
                iface.actions[1].trigger()
            self.assertEqual(read_file(destination).points, read_file(source).points[:1])
            warning.assert_not_called()
            self.assertEqual(report.call_count, 1)

    def test_sosi_vector_menu_import_preserves_z_and_source_fields(self):
        iface = TestInterface()
        plugin = SurveyFilePlugin(iface)
        plugin.initGui()
        self.addCleanup(plugin.unload)
        self.addCleanup(QgsProject.instance().clear)
        with (
            patch.object(plugin, "_show_import_report") as report,
            patch("qgis_sosi.plugin.QMessageBox.warning") as warning,
            TemporaryDirectory() as folder,
        ):
            path = Path(folder) / "vectors.sos"
            path.write_bytes(VECTOR_SAMPLE.encode("iso8859-10"))
            with patch("qgis_sosi.plugin.QFileDialog.getOpenFileNames", return_value=([str(path)], SOSI_FILTER)):
                iface.actions[0].trigger()
            layers = {layer.wkbType(): layer for layer in QgsProject.instance().mapLayers().values()}
            curve = layers[Qgis.WkbType.LineStringZ]
            surface = layers[Qgis.WkbType.PolygonZ]
            self.assertEqual((curve.featureCount(), surface.featureCount()), (3, 1))
            first = next(curve.getFeatures())
            self.assertEqual((first["lokalid"], first["navnerom"]), ("eksempel-11", "ÅŊ"))
            geometry = next(surface.getFeatures()).geometry()
            self.assertTrue(geometry.isGeosValid())
            self.assertEqual(geometry.area(), 100)
            self.assertEqual([vertex.z() for vertex in geometry.vertices()], [0, 12, -0.5, 12, 0])
            warning.assert_not_called()
            report.assert_called_once()

    def test_batch_import_mixed_files_reports_errors_and_reuses_kof_options(self):
        iface = TestInterface()
        plugin = SurveyFilePlugin(iface)
        plugin.initGui()
        project = QgsProject.instance()
        self.addCleanup(plugin.unload)
        self.addCleanup(project.clear)
        with TemporaryDirectory() as folder:
            parent = Path(folder)
            a = FIXTURES / "netlin05_points.kof"
            b = parent / "another.kof"
            copyfile(a, b)
            broken = parent / "broken.sos"
            broken.write_text("invalid", encoding="ascii")
            sos = FIXTURES / "utm32_points.sos"
            names = [str(path) for path in (a, broken, sos, b)]
            with (
                patch("qgis_sosi.plugin.QFileDialog.getOpenFileNames", return_value=(names, "")),
                patch.object(plugin, "_select_kof_options", return_value=("EPSG:25832", "NN2000", True)) as options,
                patch.object(plugin, "_show_import_report") as report,
            ):
                iface.actions[0].trigger()
            outcomes = report.call_args.args[0]
            self.assertEqual([row["status"] for row in outcomes], ["imported", "error", "imported", "imported"])
            self.assertEqual(outcomes[1]["issues"][0]["severity"], "error")
            self.assertEqual(len(project.mapLayers()), 6)
            self.assertEqual([node.name() for node in project.layerTreeRoot().children()],
                             [a.name, sos.name, b.name])
            options.assert_called_once()
            self.assertTrue(options.call_args.args[-1])

            path = parent / "report.json"
            with patch("qgis_sosi.plugin.QFileDialog.getSaveFileName", return_value=(str(path), "")):
                plugin._save_import_report(outcomes, None)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["files"], outcomes)

    def test_batch_import_geopackage_is_persistent_with_duplicate_source_names(self):
        iface = TestInterface()
        plugin = SurveyFilePlugin(iface)
        plugin.initGui()
        project = QgsProject.instance()
        self.addCleanup(plugin.unload)
        self.addCleanup(project.clear)
        with TemporaryDirectory() as folder:
            parent = Path(folder)
            paths = []
            for directory in ("a", "b"):
                (parent / directory).mkdir()
                path = parent / directory / "vegar.sos"
                path.write_bytes(VECTOR_SAMPLE.encode("iso8859-10"))
                paths.append(str(path))
            destination = parent / "vegar.gpkg"
            with (
                patch("qgis_sosi.plugin.QFileDialog.getOpenFileNames", return_value=(paths, "")),
                patch("qgis_sosi.plugin.QFileDialog.getSaveFileName", return_value=(str(destination), "")),
                patch.object(plugin, "_show_import_report") as report,
            ):
                iface.actions[3].trigger()
            results = report.call_args.args[0]
            self.assertEqual([row["status"] for row in results], ["imported", "imported"], results)
            counts = []
            for layer in project.mapLayers().values():
                counts.append(layer.featureCount())
                self.assertEqual(layer.providerType(), "ogr")
                self.assertIn(layer.wkbType(), (Qgis.WkbType.LineStringZ, Qgis.WkbType.PolygonZ))
                self.assertEqual(layer.customProperty("qgis_sosi/height_datum"), "NN2000")
                self.assertEqual(layer.renderer().type(), "categorizedSymbol")
                self.assertFalse(layer.customProperty("qgis_sosi/style_error", ""))
            self.assertEqual(sorted(counts), [1, 1, 3, 3])
            del layer
            project.clear()
            with gdal.OpenEx(str(destination), gdal.OF_VECTOR) as gpkg:
                data_layers = [layer for layer in gpkg if layer.GetName() != "layer_styles"]
                self.assertEqual(sorted(layer.GetFeatureCount() for layer in data_layers), [1, 1, 3, 3])
                del data_layers
            with closing(sqlite3.connect(destination)) as gpkg:
                tables = gpkg.execute("""
                    SELECT DISTINCT r.table_name
                    FROM gpkg_metadata_reference AS r
                    JOIN gpkg_metadata AS m ON r.md_file_id = m.id
                    WHERE m.metadata LIKE '%NN2000%' AND r.table_name IS NOT NULL
                """).fetchall()
                self.assertEqual(len(tables), 4)
                self.assertEqual(gpkg.execute("SELECT count(*) FROM layer_styles WHERE useAsDefault").fetchone(),
                                 (4,))

    def test_kof_preview_distinguishes_blank_height_and_zero(self):
        plugin = SurveyFilePlugin(TestInterface())
        path = FIXTURES / "netlin05_points.kof"

        def choose(dialog):
            table = dialog.findChild(QTableWidget)
            self.assertEqual(table.item(0, 3).text(), "")
            self.assertEqual(table.item(1, 3).text(), "0.0")
            dialog.findChild(QLineEdit).setText("25832")
            dialog.findChild(QComboBox).setCurrentText("NN2000")
            dialog.findChild(QCheckBox).setChecked(True)
            return QDialog.DialogCode.Accepted

        with patch("qgis_sosi.plugin.QDialog.exec", new=choose):
            self.assertEqual(plugin._select_kof_options(path, read_file(path), True),
                             ("EPSG:25832", "NN2000", True))

    def test_sosi_uses_symbols_labels_and_curved_geometry_by_object_type(self):
        from qgis_sosi import sosi

        data = sosi.decode(PRESENTATION_SAMPLE.encode("iso8859-10"))
        layers = create_layers(data, "Kart", ".sos")
        point_layer = next(layer for layer in layers if layer.wkbType() == Qgis.WkbType.PointZ)
        categories = {category.value(): category for category in point_layer.renderer().categories()}
        self.assertEqual(categories["Kumlokk"].label(), "Kumlokk")
        self.assertNotEqual(categories["Kumlokk"].symbol().color(), categories["VA_Sluk"].symbol().color())
        self.assertIn(Qgis.WkbType.CircularStringZ, {layer.wkbType() for layer in layers})
        self.assertIn(Qgis.WkbType.CurvePolygonZ, {layer.wkbType() for layer in layers})
        annotations = [layer for layer in layers if layer.labelsEnabled()]
        self.assertEqual(len(annotations), 2)
        labels = {next(layer.getFeatures())["sosi_tekst"]: layer for layer in annotations}
        location = next(next(labels["Nordre Voll"].getFeatures()).geometry().vertices())
        self.assertAlmostEqual(location.x(), 404002.0)
        self.assertAlmostEqual(location.y(), 6785001.0)
        self.assertEqual(labels["Testvegen"].labeling().settings().placement, Qgis.LabelPlacement.Curved)
        ar5 = next(layer for layer in layers if layer.customProperty("qgis_sosi/geometry") == "SYMBOL")
        self.assertEqual(ar5.renderer().categories()[0].label(), "Fulldyrka jord")

    def test_kof_export_reads_explicit_field_mapping_and_uses_point_geometry(self):
        dataset = replace(read_file(FIXTURES / "netlin05_points.kof"), crs="EPSG:25832")
        _, layer = create_layers(dataset, "KOF", ".kof")
        self.assertTrue(layer.startEditing())
        self.assertTrue(layer.renameAttribute(0, "Stikkenummer"))
        self.assertTrue(layer.renameAttribute(1, "Typekode"))
        self.assertTrue(layer.commitChanges())
        result = read_layer(layer, ".kof", {"punkt_id": "Stikkenummer", "temakode": "Typekode"})
        expected = replace(dataset, points=tuple(
            replace(point, note="", calculation_code="") for point in dataset.points if point.z is not None
        ))
        self.assertEqual(result, expected)
