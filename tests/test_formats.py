from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from qgis_sosi import kof, sosi
from qgis_sosi.exchange import export_file, read_file
from qgis_sosi.model import FormatError, PointSet, SurveyPoint


FIXTURES = Path(__file__).with_name("fixtures")


class PointFormatTests(unittest.TestCase):
    def test_sosi_import_preserves_axes_serial_fields_and_height(self):
        data = read_file(FIXTURES / "utm32_points.sos")
        self.assertEqual((data.crs, data.height_datum), ("EPSG:25832", "NN2000"))
        self.assertEqual(data.points, (
            SurveyPoint("11", 398003.12, 6790013.78, None, "Fastmerke", "Punkt utan høgd"),
            SurveyPoint("12", 398003.13, 6790014.0, 0.0, "Fastmerke", "Punkt ved null"),
            SurveyPoint("13", 398003.15, 6790014.2, 12.345, "Fastmerke", "Punkt over null"),
            SurveyPoint("14", 398003.17, 6790014.5, -1.75, "Fastmerke", "Punkt under null"),
        ))

    def test_sosi_roundtrip_keeps_metadata_and_reports_rounding(self):
        source = read_file(FIXTURES / "utm32_points.sos")
        with TemporaryDirectory() as folder:
            path = Path(folder) / "roundtrip.sos"
            self.assertEqual(export_file(path, source), 0)
            self.assertEqual(read_file(path), source)
            extra_precision = replace(source.points[0], y=6790013.7805, x=398003.1234)
            source = replace(source, points=(extra_precision, *source.points[1:]))
            self.assertEqual(export_file(path, source), 2)
            self.assertEqual((read_file(path).points[0].x, read_file(path).points[0].y),
                             (398003.123, 6790013.781))

    def test_sosi_rejects_unsupported_geometry_property_and_crs(self):
        text = (FIXTURES / "utm32_points.sos").read_text(encoding="utf-8")
        cases = [
            (".PUNKT 11:", ".KURVE 11:", "minst 2 koordinatsett"),
            ("..OBJTYPE Fastmerke", "..IDENT test", "ukjend"),
            ("...KOORDSYS 22", "...KOORDSYS 99", "KOORDSYS"),
            ("...KOORDSYS 22", "...KOORDSYS 22\n...TRANSSYS 23", "TRANSSYS"),
            (".PUNKT 12:", ".PUNKT 11:", "duplisert"),
        ]
        for find, replacement, message in cases:
            with self.subTest(replacement=replacement):
                with self.assertRaisesRegex(FormatError, message):
                    sosi.decode(text.replace(find, replacement, 1).encode("utf-8"))

    def test_sosi_other_documented_crs_code(self):
        source = read_file(FIXTURES / "utm32_points.sos")
        for auth_id in ("EPSG:25833", "EPSG:25835"):
            with self.subTest(auth_id=auth_id):
                data = replace(source, crs=auth_id)
                self.assertEqual(sosi.decode(sosi.encode(data)), data)

    def test_bad_export_does_not_replace_existing_file(self):
        source = read_file(FIXTURES / "utm32_points.sos")
        with TemporaryDirectory() as folder:
            path = Path(folder) / "keep.sos"
            path.write_text("existing", encoding="utf-8")
            with self.assertRaisesRegex(FormatError, "høgdesystem"):
                export_file(path, replace(source, height_datum=None))
            self.assertEqual(path.read_text(encoding="utf-8"), "existing")
            self.assertEqual(list(Path(folder).iterdir()), [path])

    def test_kof_import_and_roundtrip(self):
        source = read_file(FIXTURES / "netlin05_points.kof")
        self.assertIsNone(source.crs)
        self.assertEqual(source.points, (
            SurveyPoint("A11", 398003.12, 6790013.78, None, "8601"),
            SurveyPoint("A12", 398003.13, 6790014.0, 0.0, "7002", "null"),
            SurveyPoint("A13", 398003.15, 6790014.2, 12.345, "7002", "", "07"),
            SurveyPoint("A14", 398003.17, 6790014.5, -1.75, "", "under"),
        ))
        self.assertEqual(kof.decode(kof.encode(source)), source)
        with TemporaryDirectory() as folder:
            path = Path(folder) / "roundtrip.kof"
            self.assertEqual(export_file(path, replace(source, crs="EPSG:25832", height_datum="NN2000")), 0)
            self.assertEqual(read_file(path), source)

    def test_kof_roundtrip_preserves_repeated_point_names_and_rows(self):
        rows = (FIXTURES / "netlin05_points.kof").read_bytes().splitlines()
        source = kof.decode(b"\n".join((rows[0], rows[1].replace(b"A12", b"A11"), rows[0])))
        expected = read_file(FIXTURES / "netlin05_points.kof").points
        self.assertEqual(source.points, (expected[0], replace(expected[1], point_id="A11"), expected[0]))
        self.assertEqual(kof.decode(kof.encode(source)), source)

    def test_extensionless_input_uses_content_and_full_format_validation(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "temporary_copy"
            for fixture in ("utm32_points.sos", "netlin05_points.kof"):
                source = FIXTURES / fixture
                path.write_bytes(source.read_bytes())
                self.assertEqual(read_file(path), read_file(source))
            path.write_bytes(b"-inactive\n\n 05 bad layout\n")
            with self.assertRaisesRegex(FormatError, "KOF linje 3"):
                read_file(path)
            path.write_bytes(b"unknown")
            with self.assertRaisesRegex(FormatError, "manglar filending"):
                read_file(path)

    def test_kof_rejects_other_layout_empty_name_and_overflow(self):
        good_row = (FIXTURES / "netlin05_points.kof").read_bytes().splitlines()[0]
        for malformed, message in (
            (b" 00 comment", "05-blokker"),
            (b" 05 A 8601 6790013.780 398003.120", "feltplasseringa"),
            (good_row.replace(b"A11", b"   "), "Tom punkt-ID"),
        ):
            with self.subTest(malformed=malformed):
                with self.assertRaisesRegex(FormatError, message):
                    kof.decode(malformed)
        with self.assertRaisesRegex(FormatError, "plass"):
            kof.encode(PointSet((SurveyPoint("pt", 398003.12, 6790013.78, -1000.0),)))


if __name__ == "__main__":
    unittest.main()
