# Utviklingsoppdrag til Codex: SOSI og KOF import/eksport for QGIS

## 1. Mål
Bygg éi installerbar QGIS-utviding (Python/PyQGIS) for import og eksport av både norske SOSI-filer og KOF-filer (koordinatfiler). Begge format skal vere tilgjengelege i same plugin, med felles brukargrensesnitt og valideringssystem. Ho skal støtte (a) generelle kart-, terreng- og VA-data med 3D/Z-verdiar og (b) reguleringsplanar for kommunal leveranse. Prioriter korrektheit, sporbarheit og validering framfor eit omfattande grensesnitt.

**Viktig:** Ei fil som kan lesast av QGIS er ikkje automatisk gyldig etter ein bestemt SOSI-produktspesifikasjon. Ikkje merk ei leveranse som «godkjend» utan at relevant kontroll er køyrd og resultatet dokumentert.

## 2. Arbeidsmåte for Codex
1. Undersøk repository og eksisterande kode før du endrar noko. Dersom repository er tomt, opprett eit nytt QGIS-plugin-prosjekt.
2. Gjer ei teknisk vurdering av biblioteka under, inkludert lisens, vedlikehaldsstatus, avhengigheiter, 3D-støtte og topologi. Ikkje kopier tredjepartskode utan lisensvurdering.
3. Lag først ein fungerande vertikal prototype: importer ei SOSI-fil, bevar relevante attributt, eksporter minst eitt SOSI-objekt og importer resultatet på nytt.
4. Implementer modulært og testbart. Skil mellom filformat, geometri/topologi, produktprofilar, validering og QGIS-grensesnitt.
5. Arbeid i små, etterprøvbare steg. Kjør testar og dokumenter kva som faktisk er verifisert. Ikkje påstå støtte for format eller kommunal aksept som ikkje er testa.
6. Dersom kritiske standarddokument, eksempeldata eller eksterne kontrollverktøy manglar: lag tydelege TODO-ar, testgrensesnitt og ei oversikt over blokkeringar. Ikkje finn på SOSI-kodar eller obligatoriske attributt.

## 3. Eksisterande kode som skal vurderast
- Kartverket `sosi2gpkg`: https://github.com/kartverket/sosi2gpkg — kandidat for import og QGIS-integrasjon.
- `sosilogikk`: https://github.com/jesperfjellin/sosilogikk — kandidat for SOSI-lesing/-skriving. Verifiser spesielt om Z-koordinatar blir bevarte og om biblioteket kan skrive nødvendig topologi.
- `sosicon`: https://github.com/espena/sosicon — historisk referanse, ikkje automatisk valt som avhengigheit.
- GDAL/OGR SOSI-driver: undersøk faktisk lese-/skrivestøtte i målmiljøet. Ikkje anta at GDAL kan skrive SOSI.

Dokumenter funna i `docs/dependency-assessment.md`, med lenker til kjeldekode og konkrete testresultat. Verifiser gjeldande lisensar direkte i kvart repository.

## 4. Omfang og funksjonskrav

### 4.1 Import
- Importer SOSI til QGIS-lag eller GeoPackage med punkt, linjer og flater.
- Bevar så mykje som mogleg av SOSI-objekttype, identifikatorar, eigenskapar og relasjonar. Registrer eventuelt informasjonstap eksplisitt.
- Les koordinatreferansesystem frå filhovud, vis kjelde-CRS og tillat eksplisitt transformasjon.
- Støtt EUREF89 UTM sone 32 (EPSG:25832) som viktig testtilfelle, utan å hardkode dette for alle filer.
- Bevar 3D/Z og skil mellom manglande Z, Z=0 og gyldig Z. Handter høgdereferansesystem og einingar eksplisitt.
- Vis forståelege feilmeldingar ved ukjend objekttype, ugyldig geometri eller manglande bibliotek.

### 4.2 Generell eksport / terreng og VA
- Eksporter valde QGIS-lag/objekt til SOSI etter vald, dokumentert profil.
- Støtt punkt, linjer, polygon og 3D-geometri der målprofilen tillèt det.
- Bevar koordinatpresisjon, Z, attributt og objektidentitet i den grad standarden krev.
- Unngå stille konvertering frå 3D til 2D.
- Støtt relevante kurvetypar dersom SOSI-profilen krev dei; elles skal eksporten stoppe med presis feilmelding eller krevje eksplisitt, dokumentert segmentering.
- Skriv korrekt filhovud og koding etter vald profil; ikkje bygg filhovud av udokumenterte konstantar.

### 4.3 Reguleringsplaneksport
- Eige eksportløp for reguleringsplanar etter plan- og bygningslova 2008, med **versjonert produktprofil**.
- Profilen må definere lovlege objekttypar, kodeverk, obligatoriske eigenskapar, geometri- og topologireglar, SOSI-versjon og objektkatalog.
- Støtt planområde, arealføremål, omsynssoner og juridiske linjer i den grad dei er definerte i vald produktspesifikasjon.
- Implementer SOSI-flater med korrekt referanse til avgrensingskurver når spesifikasjonen krev dette. Delte grenser og retning må behandlast konsistent.
- Ikkje hardkod eldre SOSI-/objektkatalogversjon som universell standard. Profilval og versjon må vere synleg for brukaren.
- Import og eksport av reguleringsplan skal vere tapsfri for dei eigenskapane som inngår i støtta profil, eller rapportere avvik.

### 4.4 KOF-import og -eksport (same plugin)
- Implementer **KOF som eit sjølvstendig filformat i den same QGIS-utvidinga**, ikkje som ein separat plugin. Brukaren skal kunne velje SOSI eller KOF i import- og eksportdialogen.
- Importer KOF-punkt med punktnummer/ID, X/Y-koordinatar, Z/høgd og relevante kodar, merknader og andre felt som faktisk finst i den valde KOF-varianten.
- Eksporter QGIS-punktlag til KOF med valbar feltmapping for punktnummer, koordinatar, høgd, kode og merknad. Ver tydeleg på kva geometri- og objekttypar KOF-varianten støttar; ikkje lat som om polygon eller linjer kan eksporterast tapsfritt dersom formatet berre representerer punkt.
- **KOF har ulike variantar i praktisk bruk.** Finn og dokumenter reelle filspesifikasjonar og representative eksempel før parseren blir fastsett. Ikkje finn på faste kolonneposisjonar, skiljeteikn, koordinatrekkjefølgje eller kodeverk. Gjer variant/profil eksplisitt, og tilby trygg automatisk gjenkjenning berre når formatet kan identifiserast påliteleg.
- Støtt relevante koordinatsystem, særleg EPSG:25832, og høgdesystem (til dømes NN2000) gjennom eksplisitte innstillingar. KOF-filer kan mangle eintydig CRS-metadata: krev stadfesting frå brukaren når dette ikkje kan lesast sikkert. Ikkje bytt om nord/øst eller X/Y utan kontroll.
- Bevar Z-verdiar og numerisk presisjon ved import og eksport. Skil mellom manglande høgd og høgd 0. Rapporter tap av felt eller presisjon.
- Gje førehandsvising av dei første datapunkta og feltmapping før import/eksport, med kontroll av ugyldige linjer, dupliserte punktnummer, manglande koordinatar og inkonsistente felt.
- Lag rundturtestar KOF → QGIS → KOF og QGIS → KOF → QGIS, med samanlikning av punktnummer, koordinatar, Z og eigenskapar innanfor dokumenterte toleransar.
- Halde SOSI- og KOF-parserar/skrivarar skilde, men del CRS-, geometri-, felttilordnings-, rapporterings- og UI-komponentar der det er naturleg.

### 4.5 Validering
- Før eksport: kontroll av obligatoriske attributt, kodeverk, CRS, geometri, Z, polygonlukking, overlapp/gap og topologiske relasjonar der det er relevant.
- Etter eksport: automatisk rundturtest (SOSI -> import) med samanlikning av objekttal, objekttypar, attributt, koordinatar og Z innanfor eksplisitt toleranse.
- Legg til adapter for eksternt SOSI-kontrollverktøy dersom tilgjengeleg, med dokumentert versjon, kommando/API og tolking av resultat.
- Lag maskinlesbar JSON-rapport og lesbar rapport med `error`, `warning`, `info`, objekt-ID, regel, forklaring og eventuell rettleiing.
- Skill mellom «interne testar bestått», «ekstern SOSI-kontroll bestått» og «kommunal aksept». Berre dei to første kan verifiserast automatisk når verktøya finst.

## 5. Føreslått arkitektur
```text
qgis-sosi/
  metadata.txt
  __init__.py
  plugin.py
  ui/
    import_dialog.py
    export_dialog.py
    validation_dialog.py
  core/
    models.py
    sosi_reader.py
    sosi_writer.py
    kof_reader.py
    kof_writer.py
    field_mapping.py
    geometry_3d.py
    topology.py
    crs.py
  profiles/
    terrain.yaml
    kof_profiles/
      README.md
    reguleringsplan.yaml
  validation/
    geometry.py
    attributes.py
    roundtrip.py
    external_control.py
    reports.py
  tests/
    fixtures/
    test_import.py
    test_export.py
    test_3d.py
    test_topology.py
    test_regulation_profile.py
    test_roundtrip.py
    test_kof_import.py
    test_kof_export.py
    test_kof_roundtrip.py
  docs/
    architecture.md
    dependency-assessment.md
    supported-profiles.md
    installation.md
    validation.md
```
Tilpass strukturen om ei anna oppdeling gir betre QGIS-kompatibilitet. Kjernelogikk skal kunne testast utan å starte QGIS GUI så langt det er praktisk.

## 6. Grensesnitt
- Meny/toolbar: **Importer fil (SOSI/KOF)**, **Eksporter fil (SOSI/KOF)**, **Valider fil**.
- Import: vel SOSI eller KOF (eventuelt automatisk identifikasjon), fil, mål-GeoPackage/prosjekt, CRS-handtering, førehandsvising for KOF og resultatlogg.
- Eksport: vel SOSI eller KOF, lag, eksportprofil og profilversjon, utfil, eventuelle feltmappingar og valideringsnivå.
- Før skriving: vis kritiske feil; blokker eksport ved feil som gjer fila ugyldig for vald profil.
- Etter eksport: vis status, filbane og rapport, inkludert eventuelle tap/transformasjonar.
- Norsk grensesnitt (nynorsk er ønskjeleg), men bruk tekniske standardtermar der det er mest presist.

## 7. Testdata og akseptansekriterium
Lag syntetiske testdata for grunnleggjande funksjonar, men bruk **offisielle/autoritative eksempel** for å verifisere produktspesifikk SOSI-korrektheit. Dokumenter kjelde og bruksrett.

Minimumstestar:
1. 2D-punkt, linje og polygon: import/eksport/rundtur utan utilsikta endring.
2. 3D-punkt og 3D-linje med både positiv, negativ og null Z: same Z etter rundtur innanfor dokumentert presisjon.
3. UTM32-koordinatar: inga akserekkjefølgje- eller einingsfeil.
4. SOSI-fil med ukjend objekttype: kontrollert åtvaring, ikkje stille tap.
5. Reguleringsplan med delte grenser: korrekt topologi og referansar.
6. Manglande obligatoriske planattributt: eksport blokkert med presis feilmelding.
7. Ugyldig polygon, overlapp og gap: rapporterte etter profilreglar.
8. Eksportert fil blir kontrollert i relevant eksternt SOSI-kontrollverktøy dersom tilgjengeleg.
9. KOF med punktnummer, koordinatar og Z: import/eksport/rundtur, inkludert manglande høgd, negative høgder og ulike presisjonsnivå.
10. KOF med ukjend variant eller tvitydig koordinatrekkjefølgje: tydeleg feil eller krav om brukarstadfesting.
11. Ingen test får bli markert «bestått» dersom han ikkje faktisk er køyrd.

## 8. Leveransar og milepålar
**M1 – Kartlegging og prototype:** `docs/dependency-assessment.md`, fungerande import, minimal eksport og rundturtest. Beskriv risiko ved Z og topologi.

**M2 – Generell SOSI og KOF:** installerbar QGIS-plugin, import/eksport for støtta kart- og terrengobjekt, grunnleggjande validering. KOF-import/-eksport med punktnummer, Z, feltmapping og rundturtestar skal vere inkludert.

**M3 – 3D:** dokumentert støtte for Z, høgdesystem og aktuelle kurvetypar, med automatiske testar.

**M4 – Reguleringsplan:** versjonert produktprofil, attributt- og topologikontroll, eksterne valideringstestar der mogleg.

**M5 – Utgjeving:** ZIP som kan installerast i QGIS, README, brukarrettleiing, testlogg, kjende avgrensingar og lisensoversikt.

## 9. Første konkrete oppgåve til Codex
Start med **M1**, ikkje bygg heile produktet på ein gong:
1. Finn og inspiser kjeldekode og lisensar for dei tre GitHub-prosjekta.
2. Kontroller GDAL/SOSI-støtte og kompatibilitet med installert QGIS/Python-versjon.
3. Lag eit minimalt plugin-skjelett med felles import-/eksportmeny for SOSI og KOF.
4. Lag ein eksperimentell SOSI-skrivar/adapter og test med 2D og 3D-data.
5. Lag ein automatisk rundturtest som samanliknar X/Y/Z og eigenskapar.
6. Finn representative KOF-eksempelfiler og dokumentasjon for aktuell KOF-variant; lag ein minimal KOF-lesar og -skrivar med punktnummer og XYZ, og test rundtur. Dersom spesifikasjon/testfiler manglar, dokumenter blokkeringa i staden for å gjette.
7. Dokumenter kva som fungerer, kva som feilar, og kva eksterne testfiler/spesifikasjonar som trengst før M2.
8. Oppsummer konkrete neste steg og ikkje start M2 før M1 er dokumentert.

## 10. Avklaringar som må innhentast ved behov
- Målversjon(ar) av QGIS, operativsystem og distribusjonsform.
- Autoritative SOSI-testfiler for terreng/VA og godkjend reguleringsplan.
- Representative KOF-filer frå dei aktuelle landmålings-/prosjekteringssystema og avklaring av KOF-variant og feltstruktur.
- Nøyaktig reguleringsplan-produktspesifikasjon og versjon kommunen krev.
- Tilgang til eksternt SOSI-kontrollverktøy og eventuelle lisensar.
- Kva høgdesystem (t.d. NN2000) og andre koordinatsystem som skal støttast.

**Definisjon av ferdig:** Ein funksjon er ikkje ferdig før han har automatiserte testar, dokumentert avgrensing og reproduserbart resultat. Kommunal leveranseklarheit krev kontroll mot den konkrete mottakaren sine krav.
