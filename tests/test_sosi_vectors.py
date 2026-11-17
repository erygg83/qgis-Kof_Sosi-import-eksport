import unittest

from qgis_sosi import sosi
from qgis_sosi.model import FormatError


VECTOR_SAMPLE = '''.HODE
..PROSESS_HISTORIE IOB
..TEGNSETT ISO8859-10
..SOSI-VERSJON 4.5
..SOSI-NIVÅ 4
..TRANSPAR
...KOORDSYS 22
...VERT-DATUM NN2000
...ORIGO-NØ 6785000 404000
...ENHET 0.01
...ENHET-H 0.001
..OMRÅDE
...MIN-NØ 6785000 404000
...MAX-NØ 6785010 404010
..OBJEKTKATALOG FKB-Veg 4.61
.KURVE 11:
..OBJTYPE Vegdekkekant
..IDENT
...LOKALID eksempel-11
...NAVNEROM "ÅŊ"
..NØH
0 0 0 ...KP 1
..NØH
0 1000 12000 ...KP 1
.KURVE 12:
..OBJTYPE Vegdekkekant
..NØH
1000 1000 -500
0 1000 12000
.KURVE 13:
..OBJTYPE Vegdekkekant
..NØH
1000 1000 -500
1000 0 12000
0 0 0
.FLATE 14:
..OBJTYPE Veg
..REF :11 :-12
:13
..NØH
500 500 6000
.SLUTT
'''

PRESENTATION_SAMPLE = VECTOR_SAMPLE.replace(
    ".KURVE 12:\n..OBJTYPE Vegdekkekant\n..NØH\n1000 1000 -500\n0 1000 12000",
    ".BUEP 12:\n..OBJTYPE Eiendomsgrense\n..NØH\n1000 1000 -500\n500 1250 6000\n0 1000 12000",
).replace(".SLUTT", '''.PUNKT 15:
..OBJTYPE Kumlokk
..NØH
100 100 17000
.PUNKT 16:
..OBJTYPE VA_Sluk
..NØH
200 200 16900
.TEKST 17:
..OBJTYPE StedsnavnTekst
..STRENG "Nordre Voll"
..NØ
0 0
100 200
.TEKST 18:
..OBJTYPE PresentasjonTekst
..TEKSTTYPE vegnavn
..STRENG Testvegen
..NØ
100 200
110 210
120 220
130 230
.SYMBOL 19:
..OBJTYPE AR5Symbol
..ARTYPE 21
..NØ
10 10
20 30
20 40
.SLUTT''')


class SosiVectorTests(unittest.TestCase):
    def test_iso_8859_10_curves_and_surface(self):
        dataset = sosi.decode(VECTOR_SAMPLE.encode("iso8859-10"))
        self.assertEqual((dataset.crs, dataset.height_datum, dataset.catalogue),
                         ("EPSG:25832", "NN2000", "FKB-Veg 4.61"))
        first, _, _, surface = dataset.features
        self.assertIn('...NAVNEROM "ÅŊ"', first.source_lines)
        self.assertEqual(first.vertices, ((404000.0, 6785000.0, 0.0), (404010.0, 6785000.0, 12.0)))
        self.assertEqual(surface.vertices, (
            (404000.0, 6785000.0, 0.0),
            (404010.0, 6785000.0, 12.0),
            (404010.0, 6785010.0, -0.5),
            (404000.0, 6785010.0, 12.0),
            (404000.0, 6785000.0, 0.0),
        ))

    def test_missing_reference_and_discontinuous_ring_are_rejected(self):
        for refs, error in ((":11 :-99\n:13", "manglar"), (":11 :12\n:13", "møter ikkje")):
            with self.subTest(refs=refs), self.assertRaisesRegex(FormatError, error):
                sosi.decode(VECTOR_SAMPLE.replace(":11 :-12\n:13", refs).encode("iso8859-10"))

    def test_sosi_metadata_and_mixed_geometry_keep_arc_and_presentation_positions(self):
        data = sosi.decode(PRESENTATION_SAMPLE.encode("iso8859-10"))
        features = {feature.serial: feature for feature in data.features}
        self.assertEqual(features["14"].boundary[1][0], "BUEP")
        self.assertEqual(features["14"].boundary[1][1][1], (404012.5, 6785005.0, 6.0))
        self.assertEqual(features["15"].vertices, ((404001.0, 6785001.0, 17.0),))
        self.assertEqual(features["17"].vertices[1], (404002.0, 6785001.0))
        self.assertEqual(len(features["18"].vertices), 4)
        self.assertEqual(features["19"].kind, "SYMBOL")
