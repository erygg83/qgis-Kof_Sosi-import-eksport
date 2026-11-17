# SOSI og KOF for QGIS

Versjon 0.2.1 importerer fleire SOSI- og KOF-filer i same operasjon. SOSI-laga får teiknereglar etter objekttype i QGIS og ved lagring til nytt GeoPackage. Utvikling og testing er gjort med QGIS 4.0.2 på Windows. [Utviklingsplan](UTVIKLINGSPLAN.md)

## Prøv i QGIS

Bygg installasjonspakka frå Git i PowerShell ved behov.

```powershell
New-Item -ItemType Directory -Force dist | Out-Null
git archive --format=zip --output=dist/qgis_sosi-0.2.1.zip HEAD qgis_sosi
```

1. Installer `dist/qgis_sosi-0.2.1.zip` frå **Utvidingar → Handsam og installer utvidingar → Installer frå ZIP**.
2. Vel **Utvidingar → SOSI og KOF → Importer filer (SOSI/KOF)**. Hald inne **Ctrl** for å velje fleire filer i same dialog. Prøv [SOSI-eksempelet](tests/fixtures/utm32_points.sos) og [KOF-eksempelet](tests/fixtures/netlin05_points.kof).
3. Kontroller KOF-førehandsvisinga og stadfest kjelde-CRS og høgdesystem. For KOF-testfila er det EPSG:25832 og NN2000. Kryss av for felles innstillingar berre når alle dei attverande KOF-filene brukar same system.
4. Sjå **Vis detaljar** for resultat per fil, eller vel **Lagre JSON-rapport**. Filfeil blir rapporterte medan dei andre filene blir prøvde.
5. Bruk **Importer filer til nytt GeoPackage** for å lagre laga permanent. Vel eit nytt filnamn. GeoPackage-laga bevarer koordinatdimensjon og CRS, og høgdesystemet er dokumentert i metadata.
6. Vel eit punktlag og bruk **Eksporter aktivt lag (SOSI/KOF)**. For KOF vel du kva felt som skal gi punkt-ID, temakode, merknad og berekningskode. Koordinatar og høgd kjem frå geometrien. **Valider fil (SOSI/KOF)** sjekkar syntaks innanfor dei støtta importprofilane.

## Stadfesta omfang

SOSI-importen les UTF-8, ISO8859-1 og ISO8859-10. Punkt, kurver, sirkelbogar, flater, tekst og symbol kan liggje saman i ei fil. Flater kan ha éi ytre ring av kurvereferansar, også over fleire linjer. Fil-ID, utvalde identitetsfelt og teksten i den opphavlege SOSI-gruppa blir bevarte per objekt. SOSI-importen er prøvd med FKB-Veg, FKB-Ledning, FKB-LedningVA, Matrikkelkart, N5 Presentasjonsdata, FKB-Naturinfo og FKB-Tiltak.

Teiknereglane er lokale QGIS-visingsreglar med tilpassa symbol for mellom anna lys, mast, skap, kum, sluk, eigedomsgrenser, hekk, veg og tiltak. N5-tekst brukar innhaldet i `STRENG`, med punktplassering eller kurveplassering i QGIS. Detaljar som forskyving langs tekstkurva og alle kartografiske spesialfelt står att. N5-symbol for AR5 blir grupperte etter arealtype. GeoPackage lagrar QGIS-stilen som standardstil for dei importerte SOSI-laga. [N5 Presentasjonsdata, Kartverket](https://register.geonorge.no/data/documents/Produktspesifikasjoner_N5%20Presentasjonsdata_v2_produktspesifikasjon-kartverket-n5-presentasjonsdata-20170701_.pdf), [Arealtype i AR5, NIBIO](https://nibio.no/tema/jord/arealressurser/arealressurskart-ar5/arealtype)

Eksporten er avgrensa til enkeltpunkt, med fast feltmapping for SOSI og valbar mapping for KOF. Produktvalidering, flater med hol og skrivestøtte for kurver og flater står att. Punktprofilane og testkommandoane er skildra i [M1-testloggen](docs/m1.md). [SOSI-formatet, Kartverket](https://register.geonorge.no/standarder/sosi/del-1-generell-del/sosi-realisering-sosi-gml/4.5)
