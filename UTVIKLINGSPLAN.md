# Utviklingsplan for SOSI og KOF i QGIS

Bygg éi installerbar QGIS-utviding for SOSI og KOF. Første leveranse er ein liten SOSI-rundtur i QGIS med dokumentert resultat. I same milepålen prøver vi KOF for éin dokumentert variant dersom vi finn både feltbeskriving og ei representativ fil. [Utviklingsoppdraget](CODEX_QGIS_SOSI_UTVIKLINGSOPPDRAG.md)

## Utgangspunkt

- QGIS MCP svarar på `127.0.0.1:9876`. Den opne QGIS-instansen køyrer QGIS 4.0.2, Python 3.12.13, Qt 6.11.0 og GDAL 3.12.4. Bruk dette Windows-miljøet som første testmål. QGIS 3.40.7 er òg installert og kan testast dersom vi vel å støtte 3.x.
- SOSI-drivaren i den aktive GDAL-instansen annonserer lesestøtte og manglar funksjon for oppretting av SOSI-filer eller lag. Prøv GDAL som importadapter og test ein eigen SOSI-skrivar eller `sosilogikk` som eksportkandidat. Mål kva som blir bevart, særleg Z, SOSI-identitet og topologiske referansar. [GDAL SOSI](https://gdal.org/en/stable/drivers/vector/sosi.html), [sosilogikk](https://github.com/jesperfjellin/sosilogikk)
- Test i eit eige QGIS-prosjekt eller ein separat testprofil. Bruk MCP til å sjekke at utvidinga lastar og at menyane, dialogane og laga fungerer i QGIS. Køyr automatiske format- og rundturtestar uavhengig av det opne arbeidsprosjektet.

## M1 Kartlegging og prototype

1. Inspiser kjeldekode og testdata i `sosi2gpkg`, `sosilogikk` og `sosicon`. Registrer commit, lisens, vedlikehald, avhengigheiter, støtta Python-versjonar og resultat for lesing, skriving, 3D og topologi. Verifiser lisensvilkåra før eventuell gjenbruk eller pakking. Skriv funna og grunngje val av adapter i `docs/dependency-assessment.md`. [sosi2gpkg](https://github.com/kartverket/sosi2gpkg), [sosilogikk](https://github.com/jesperfjellin/sosilogikk), [sosicon](https://github.com/espena/sosicon)
2. Lag eit minimalt plugin-skjelett i `qgis_sosi/` med `metadata.txt`, `classFactory`, import og eksport med formatval og grunnlag for validering. Hald SOSI- og KOF-lesarane og -skrivarane skilde. Del CRS-handtering, felttilordning og rapportering mellom formata der reglane er felles.
3. Importer ei dokumentert SOSI-fil til eit QGIS-lag. Eksporter eit enkelt punkt eller ei linje og les resultatet inn att i QGIS/GDAL. Prøv den same kjeda for 3D og før resultatet for kvart steg. Samanlikn objekttal, objekttype, ID, støtta attributt, CRS og X/Y/Z. Test UTM32 med ulike verdiar for aust og nord slik at ei akseforveksling blir synleg. Fastset toleransar frå fileining og eksportpresisjon. Merk eventuelt 3D- eller attributtap i testrapporten.
4. Vel éin KOF-punktvariant når kjeldesystem, feltstruktur, akseorden, høgdefelt og bruksrett er avklarte. Lag ein minimal lesar og skrivar for punkt-ID og XYZ. Test rundtur med positiv, negativ, null og manglande høgd slik varianten representerer dei. Merk ukjend variant som ei blokkering dersom dokumentasjon eller representativ fil manglar. Trimble sine kjelder gir døme på ulike KOF-bruksområde. [Quadri-eksport](https://quadrihelp.trimble.com/Quadri-for-Windows/Output/Export-to-File/Export-to-KOF), [Novapoint 3D-linje](https://novapointhelp.trimble.com/Road/Road-CAD-tools/3D-Tools/Create-3D-Line)
5. Legg testfiler med kjeldenotat i `tests/fixtures/` når bruksretten tillet det. Lever reproduserbare testkommandoar, resultat og ei liste over avgrensingar. Gå vidare til M2 når den avgrensa 2D-rundturen er demonstrert, og status for 3D, topologi og KOF er dokumentert.

## M2 Generell SOSI og KOF

Versjon 0.2.0 har fleirfilimport med resultat per fil, import til nytt GeoPackage, JSON-importrapport, KOF-førehandsvising og valbar feltmapping ved KOF-eksport. SOSI-import for punkt og FKB-Veg-kurver og -flater er prøvd. Eksport av SOSI-kurver og -flater med rundtur, eksplisitt CRS-transformasjon og produktkontroll står att før M2 kan avsluttast.

- Utvid SOSI-støtta til punkt, linjer og flater for éin dokumentert kart-, terreng- eller VA-profil. Bevar støtta eigenskapar, ID-ar og relasjonar ved import til QGIS-lag eller GeoPackage. Rapporter ukjende objekttypar, tapte felt og avvik i geometri eller CRS. Vis kjelde-CRS og gjer eventuell transformasjon til eit eksplisitt val.
- Gjer éin dokumentert KOF-punktvariant tilgjengeleg i dei same dialogane, med førehandsvising og feltmapping for ID, koordinatar, høgd, kode og merknad der varianten støttar det. Be om stadfesting når filinnhaldet gir tvitydig akseorden, CRS eller høgdesystem. Test dublettar, ugyldige linjer, presisjon og rundtur i begge retningar.
- Køyr kontroll før eksport og rundtur etter skriving. Rapporter alvor, objekt-ID, regel, forklaring og eventuell rettleiing i JSON og ein lesbar rapport. Blokker eksport når kritiske profilreglar feilar. Akseptanse for M2 er ein installerbar plugin med demonstrert import, eksport og rundtur for kvar støtta geometri og KOF-variant.

## M3 3D og høgdesystem

- Test 3D-punkt og -linjer med negativ, positiv, null og manglande Z. Bevar skiljet mellom dei, og dokumenter presisjon, høgdeeining og høgdesystem. Bruk EPSG:25832 som horisontalt testtilfelle og NN2000 som vertikalt testtilfelle der kjeldedata oppgir det. Verifiser kvar støtta transformasjon mot kjende kontrollpunkt.
- Prøv 3D-flater og kurvetypar som vald profil krev. Krav til segmentering skal utløyse eit eksplisitt val og dokumenterast i rapporten. Blokker eksport ved 3D-tap som profilen eller brukaren ikkje har godkjent.

## M4 Reguleringsplan med versjonert produktprofil

- Avklar kommunen, planstatus, utvekslingsformat og eksakt NPAD-versjon før profilen blir vald. SOSI-prikkformat er aktuelt for eldre profilar. PLAN 5.0 bruker GML og innfører digitale planføresegner. Departementet opplyser at kommunane kan ha ulik praksis i overgangen. Dersom første mottakar krev PLAN 5.0, avklar GML og digitale føresegner som ei eiga leveranse før omfanget blir låst. [Departementet om arealplanar](https://www.regjeringen.no/no/tema/plan-bygg-og-eiendom/plan_bygningsloven/planlegging/veiledning/plankart_planregister/plankart/id2836126/), [NPAD PLAN 5.0 reguleringsplan](https://planverk.ft.dibk.no/npad/v-plan50/del-3-2-reguleringsplan)
- For ein avtalt SOSI-profil, test planområde, arealføremål, omsynssoner og juridiske linjer etter objektkatalogen. Valider påkravde eigenskapar, kodeverk, delte grenser, kurveretning, flatehol, lukking, overlapp og gap der profilreglane krev det. Test mot eit autoritativt eksempel med dokumentert bruksrett.
- Køyr relevant ekstern kontroll når han er tilgjengeleg. Registrer kontrollverktøy, versjon, profil og resultat. Vis intern teststatus og ekstern kontroll kvar for seg. Kommunal aksept blir registrert når mottakaren har stadfesta henne. [Kartverket om kontroll av arealplanar](https://kartverket.no/geodataarbeid/planarbeid/kontrollere-arealplaner)

## M5 Utgjeving

Bygg ein ZIP og test første installasjon i ein rein QGIS-profil for kvar støtta QGIS-versjon. Lever brukarrettleiing, støttematrise for format og profilversjonar, testlogg, lisensoversikt og kjende avgrensingar.

## Grunnlag vi treng undervegs

| Grunnlag | Når det trengst |
| --- | --- |
| SOSI-referansefiler for 2D og 3D med dokumentert CRS, kjelde og bruksrett | M1 før verifisering av den første rundturen |
| Representativ KOF-fil frå oppmålingssystemet, med programversjon, eksportinnstillingar, CRS og høgdesystem | M1 før val av variant og M2 før full feltmapping |
| Autoritativt eksempel frå vald terreng- eller VA-profil, med opplyst høgdesystem og presisjon | M2–M3 før profilen blir merkt som støtta |
| Kommunen sitt leveransekrav, godkjend referanseplan og tilgang til relevant kontrollverktøy | M4 før produktprofil og ekstern kontroll kan verifiserast |
