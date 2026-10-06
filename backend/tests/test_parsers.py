import json

import pytest

from app.sources.dmc import split_value
from app.sources.sinca import parse_tooltip
from app.stats.trend import mann_kendall
from app.uploads.parsers import ParseError, extract_text, parse_csv, parse_features, parse_geojson, parse_kml
from app.uploads.service import UploadError, category_for, hazard_for, parse_date


def test_sinca_tooltip_reads_concentration_not_chart_value():
    value, unit = parse_tooltip("<strong>2 &micro;g&#8260;m<sup>3</sup></strong> 4 ICAP<br><em>2026-10-04 11:00 hrs.</em>")
    assert value == 2.0
    assert unit == "µg/m³"


def test_sinca_tooltip_without_data():
    assert parse_tooltip("no disponible<br><em>2026-10-05 10:00 hrs.</em>") == (None, None)


def test_dmc_split_value():
    assert split_value("20.2 °C") == (20.2, "°C")
    assert split_value("0.0 mm") == (0.0, "mm")
    assert split_value(None) == (None, None)
    assert split_value("sin dato") == (None, None)


def test_csv_with_semicolons_and_comma_decimals():
    data = "nombre;categoria;latitud;longitud\nAlbergue 1;albergue;-37,09;-73,15\n".encode("latin-1")
    features = parse_csv(data)
    assert features[0].geometry == {"type": "Point", "coordinates": [-73.15, -37.09]}
    assert features[0].properties["nombre"] == "Albergue 1"


def test_csv_rejects_out_of_range_coordinates():
    with pytest.raises(ParseError):
        parse_csv(b"nombre,lat,lon\nX,-137,-73\n")


def test_geojson_rejects_projected_crs():
    doc = {"type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": "EPSG:32718"}}, "features": []}
    with pytest.raises(ParseError):
        parse_geojson(json.dumps(doc).encode())


def test_kml_point_and_polygon():
    kml = b"""<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>
    <Placemark><name>Punto</name><Point><coordinates>-73.1,-37.1,0</coordinates></Point></Placemark>
    <Placemark><name>Sector</name><Polygon><outerBoundaryIs><LinearRing><coordinates>
      -73.1,-37.1 -73.0,-37.1 -73.0,-37.0 -73.1,-37.1</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>
    </Document></kml>"""
    features = parse_kml(kml)
    assert features[0].geometry == {"type": "Point", "coordinates": [-73.1, -37.1]}
    assert features[1].geometry["type"] == "MultiPolygon"
    assert features[1].properties["nombre"] == "Sector"


def test_unsupported_format_message_mentions_planned_formats():
    with pytest.raises(ParseError, match="shapefile"):
        parse_features("capa.shp", b"")


def test_text_document_chunks_keep_overlap():
    text = ("Oración de prueba número uno. " * 120).encode()
    chunks, pages = extract_text("plan.txt", text)
    assert pages == 1
    assert len(chunks) > 1
    assert all(len(c.content) <= 1200 for c in chunks)


def test_hazard_and_category_normalization():
    assert hazard_for("Inundación") == "inundacion"
    assert hazard_for("Remoción en masa") == "remocion"
    assert hazard_for("algo raro") == "otro"
    assert category_for("Punto crítico inundación", None) == "punto_critico_inundacion"
    with pytest.raises(UploadError):
        hazard_for("")


def test_parse_date_formats():
    assert str(parse_date("2024-06-15")) == "2024-06-15"
    assert str(parse_date("15-06-2024")) == "2024-06-15"
    assert str(parse_date("15/06/2024")) == "2024-06-15"
    with pytest.raises(UploadError):
        parse_date("junio 2024")


def test_mann_kendall_requires_ten_years():
    assert mann_kendall([1, 2, 3]).conclusion == "insufficient"


def test_mann_kendall_detects_monotonic_increase():
    result = mann_kendall([float(i) for i in range(15)])
    assert result.conclusion == "creciente"
    assert result.p_value < 0.05


def test_mann_kendall_no_trend_on_constant_series():
    assert mann_kendall([3.0] * 12).conclusion == "no_trend"


def test_mann_kendall_no_trend_on_alternating_series():
    assert mann_kendall([1.0, 5.0] * 6).conclusion == "no_trend"


CAP_ITEM = {"title": "Alerta AA1/2026: Viento fuerte", "link": "https://example.invalid/cap.xml", "category": "Alerta", "guid": "", "pub_date": ""}


def _cap(msg_type="Alert", area="<polygon>-37.0,-73.2 -37.0,-73.0 -37.2,-73.0 -37.2,-73.2</polygon>", references=""):
    return f"""<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
      <identifier>urn:oid:2.49.0.0.152.0.2026.1</identifier><sender>x</sender><sent>2026-10-05T12:00:00-03:00</sent>
      <status>Actual</status><msgType>{msg_type}</msgType><scope>Public</scope>{references}
      <info><category>Met</category><event>Viento Fuerte</event><urgency>Expected</urgency><severity>Moderate</severity>
      <certainty>Likely</certainty><onset>2026-10-05T15:00:00-03:00</onset><expires>2026-10-06T23:59:59-03:00</expires>
      <web>https://example.invalid/evento</web><area><areaDesc>Biobío: Litoral</areaDesc>{area}</area></info></alert>"""


def test_cap_polygon_is_converted_to_lon_lat():
    from app.sources.dmc_cap import parse_cap

    record = parse_cap(_cap(), CAP_ITEM)
    ring = record.area["coordinates"][0][0]
    assert ring[0] == [-73.2, -37.0] and ring[0] == ring[-1]
    assert record.level == "Alerta" and record.hazard == "wind"
    assert record.source_url == "https://example.invalid/evento"
    assert record.ends_at.isoformat() == "2026-10-06T23:59:59-03:00"


def test_cap_circle_becomes_polygon_around_center():
    from app.sources.dmc_cap import parse_cap

    record = parse_cap(_cap(area="<circle>-27.11,-109.35 250</circle>"), CAP_ITEM)
    ring = record.area["coordinates"][0][0]
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    assert min(lats) < -27.11 - 2.2 and max(lats) > -27.11 + 2.2
    assert min(lons) < -109.35 and max(lons) > -109.35


def test_cap_update_and_cancel_reference_earlier_messages():
    from app.sources.dmc_cap import parse_cap

    refs = "<references>x,urn:oid:old.1,2026-10-05T07:00:00-03:00 x,urn:oid:old.2,2026-10-05T08:00:00-03:00</references>"
    update = parse_cap(_cap("Update", references=refs), CAP_ITEM)
    assert update.supersedes == ("urn:oid:old.1", "urn:oid:old.2") and not update.cancelled
    assert parse_cap(_cap("Cancel", references=refs), CAP_ITEM).cancelled


def test_cap_exercise_messages_are_ignored():
    from app.sources.dmc_cap import parse_cap

    assert parse_cap(_cap().replace("<status>Actual</status>", "<status>Exercise</status>"), CAP_ITEM) is None


def test_dmc_feed_items_are_read():
    from app.sources.dmc_cap import parse_feed

    feed = """<rss version="2.0"><channel><item><title>Aviso A1/2026: Viento</title>
      <link>https://example.invalid/a.xml</link><category>Aviso</category></item></channel></rss>"""
    assert parse_feed(feed) == [{"title": "Aviso A1/2026: Viento", "link": "https://example.invalid/a.xml", "category": "Aviso", "guid": "", "pub_date": ""}]


def _write_gis(folder, filename, driver, crs="EPSG:32718"):
    import os
    import struct

    import numpy as np
    from pyogrio import raw

    path = os.path.join(folder, filename)
    geometry = np.array([struct.pack("<BIdd", 1, 1, 670000.0, 5895000.0)], dtype=object)
    raw.write(path, geometry, [np.array(["Albergue Norte"], dtype=object)], fields=["nombre"], geometry_type="Point", crs=crs, driver=driver)
    return path


def _zip_folder(folder, skip=()):
    import io
    import os
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in os.listdir(folder):
            if not name.endswith(skip):
                archive.write(os.path.join(folder, name), name)
    return buffer.getvalue()


def test_zipped_utm_shapefile_is_reprojected_to_wgs84(tmp_path):
    from app.uploads.parsers import parse_features

    _write_gis(str(tmp_path), "activos.shp", "ESRI Shapefile")
    features = parse_features("activos.zip", _zip_folder(str(tmp_path)))
    lon, lat = features[0].geometry["coordinates"]
    assert round(lon, 2) == -73.09 and round(lat, 2) == -37.08
    assert features[0].properties["nombre"] == "Albergue Norte"


def test_geopackage_is_read(tmp_path):
    from app.uploads.parsers import parse_features

    path = _write_gis(str(tmp_path), "activos.gpkg", "GPKG")
    with open(path, "rb") as handle:
        features = parse_features("activos.gpkg", handle.read())
    assert len(features) == 1 and round(features[0].geometry["coordinates"][1], 2) == -37.08


def test_shapefile_without_projection_is_rejected(tmp_path):
    import pytest

    from app.uploads.parsers import ParseError, parse_features

    _write_gis(str(tmp_path), "activos.shp", "ESRI Shapefile")
    with pytest.raises(ParseError, match="sistema de coordenadas"):
        parse_features("activos.zip", _zip_folder(str(tmp_path), skip=(".prj",)))


def test_geocoder_is_bounded_and_cached(monkeypatch):
    from app import geocode

    calls = []

    class Fake:
        def raise_for_status(self):
            return None

        def json(self):
            return [{"display_name": "Calle Falsa 123, Lota", "lon": "-73.15", "lat": "-37.09"}]

    def fake_get(url, params, headers, timeout):
        calls.append(params)
        return Fake()

    monkeypatch.setattr(geocode.httpx, "get", fake_get)
    monkeypatch.setattr(geocode, "MIN_INTERVAL_SECONDS", 0)
    geocode._cache.clear()
    first = geocode.search_address("Calle  Falsa 123", (-73.2, -37.2, -73.0, -37.0), "Lota")
    second = geocode.search_address("calle falsa 123", (-73.2, -37.2, -73.0, -37.0), "Lota")
    assert first == second and len(calls) == 1
    assert calls[0]["bounded"] == 1 and calls[0]["countrycodes"] == "cl" and "Lota" in calls[0]["q"]
    assert geocode.search_address("ab", (-73.2, -37.2, -73.0, -37.0), "Lota") == []


SENAPRED_COMUNAS = [
    {"cut": "08106", "name": "Lota", "region": "Biobío", "provincia": "Concepción"},
    {"cut": "08201", "name": "Lebu", "region": "Biobío", "provincia": "Arauco"},
    {"cut": "07101", "name": "Talca", "region": "Maule", "provincia": "Talca"},
    {"cut": "09115", "name": "Pucón", "region": "La Araucanía", "provincia": "Cautín"},
    {"cut": "14108", "name": "Panguipulli", "region": "Los Ríos", "provincia": "Valdivia"},
    {"cut": "14101", "name": "Valdivia", "region": "Los Ríos", "provincia": "Valdivia"},
]


def test_senapred_scopes_are_parsed_from_real_titles():
    from app.sources.senapred_alerts import parse_scope

    assert parse_scope("la Región del Biobío") == [("region", ["biobio"])]
    assert parse_scope("la Región de O´Higgins") == [("region", ["ohiggins"])]
    assert parse_scope("las comunas de Pinto y Coihueco") == [("comuna", ["pinto", "coihueco"])]
    assert parse_scope("la provincia de Arauco y las comunas de Florida, Lota, Penco, Talcahuano y Tomé") == [
        ("provincia", ["arauco"]),
        ("comuna", ["florida", "lota", "penco", "talcahuano", "tome"]),
    ]
    assert parse_scope(
        "las comunas de Villarrica, Pucón y Curarrehue en la Región de La Araucanía y para la comuna de Panguipulli en la Región de Los Ríos"
    ) == [("comuna", ["villarrica", "pucon", "curarrehue"]), ("comuna", ["panguipulli"])]


def test_senapred_card_is_read_with_chile_time():
    from app.sources.senapred_alerts import parse_card

    card = parse_card(
        "Monitoreo Alerta Temprana Preventiva para la Región del Biobío por evento meteorológico\n\n05-10-2026 07:41",
        "https://senapred.cl/alerta/se-declara-alerta-temprana-preventiva-para-la-region-del-biobio-por-evento-meteorologico-2026-09-30-15-03-26",
    )
    assert card.action == "monitor" and card.level == "Alerta Temprana Preventiva" and card.hazard == "meteo"
    assert card.published_at.isoformat() == "2026-10-05T07:41:00-03:00"
    assert parse_card("sin fecha", "https://senapred.cl/alerta/x") is None


def test_senapred_matching_does_not_spill_into_other_comunas():
    from app.sources.senapred_alerts import match_cut_codes

    assert match_cut_codes([("region", ["biobio"])], SENAPRED_COMUNAS) == ["08106", "08201"]
    assert match_cut_codes([("provincia", ["arauco"])], SENAPRED_COMUNAS) == ["08201"]
    assert match_cut_codes([("comuna", ["pucon"]), ("comuna", ["panguipulli"])], SENAPRED_COMUNAS) == ["09115", "14108"]
    assert match_cut_codes([("region", ["los rios"])], SENAPRED_COMUNAS) == ["14108", "14101"]


def test_senapred_thread_ends_when_cancelled():
    from app.sources.senapred_alerts import parse_card, to_records

    link = "https://senapred.cl/alerta/se-declara-alerta-roja-para-la-comuna-de-lota-por-desborde-2026-10-02-21-05-44"
    cards = [
        ("Se declara Alerta Roja para la comuna de Lota por desborde\n\n02-10-2026 21:05", link),
        ("Se cancela Alerta Roja para la comuna de Lota por desborde\n\n05-10-2026 13:28", link),
    ]
    records, warnings = to_records([parse_card(t, l) for t, l in cards], SENAPRED_COMUNAS)
    assert len(records) == 1 and not warnings
    record = records[0]
    assert record.level == "Alerta Roja" and record.hazard == "flood" and record.area_cut_codes == ("08106",)
    assert record.starts_at.isoformat() == "2026-10-02T21:05:44-03:00"
    assert record.ends_at.isoformat() == "2026-10-05T13:28:00-03:00"
    assert record.source_url == link


def test_census_block_keeps_only_aggregate_counts():
    from app.sources.ine_census import block_record, comuna_record

    feature = {
        "geometry": {"type": "Polygon", "coordinates": [[[-73.1, -37.0], [-73.0, -37.0], [-73.0, -37.1], [-73.1, -37.0]]]},
        "properties": {"CUT": 8106, "MANZENT": 8106011001003.0, "TIPO_MZ": "URBANO", "CATEGORIA": "Ciudad", "ENTIDAD": "LOTA", "n_per": 136, "n_vp": 50, "n_edad_60_mas": 20, "n_hog": None},
    }
    record = block_record(feature)
    assert record.external_id == "8106011001003"
    assert record.category == "urbano"
    assert record.properties["cut"] == "08106"
    assert record.properties["n_per"] == 136 and record.properties["n_hog"] == 0
    assert block_record({"properties": {}}) is None

    total = comuna_record({"CUT": 7405, "COMUNA": "RETIRO", "n_per": 22310, "n_vp": 10148, "n_hog": 8218})
    assert (total.cut_code, total.year, total.value) == ("07405", 2024, 22310)


def test_mop_roads_and_bridges_become_geojson_records():
    from app.sources.arcgis import esri_to_geojson
    from app.sources.mop_vialidad import bridge_record, road_record

    assert esri_to_geojson({"x": -73.1, "y": -37.1}) == {"type": "Point", "coordinates": [-73.1, -37.1]}
    assert esri_to_geojson({"paths": [[[-73.1, -37.1], [-73.0, -37.0]]]})["type"] == "MultiLineString"
    assert esri_to_geojson({"rings": [[[0, 0], [1, 0], [0, 1], [0, 0]]]}) is None

    road = road_record(
        {
            "geometry": {"type": "MultiLineString", "coordinates": [[[-73.1, -37.1], [-73.0, -37.0]]]},
            "properties": {"GlobalID": "{ABC-1}", "ROL": "Ruta 160_1", "ROL_LABEL": "160", "NOMBRE_CAMINO": "Concepción - Lebu", "CLASIFICACION": "Camino Nacional", "CARPETA": "Pavimento"},
        }
    )
    assert road.external_id == "abc-1" and road.category == "Camino Nacional" and road.properties["rol"] == "160"
    from app.sources.mop_vialidad import road_class

    assert road_class("Camino Nacional Longitudinal") == "Camino Nacional"
    assert road_class("Camino Regional Comunal (En Proceso de Enrolamiento)") == "Camino Regional Comunal"
    assert road_class(None) is None

    bridge = bridge_record(
        {
            "geometry": {"type": "Point", "coordinates": [-73.0, -37.2]},
            "properties": {"OBJECTID": 7, "NOMBRE_PUENTE": "PUENTE LIA", "CAUCE_QUEB": "LIA", "LARGO": 50.5, "AÑO_CONTRUCCION": 0, "TIPO_INFRA_WEB": " "},
        }
    )
    assert bridge.external_id == "7" and bridge.category is None
    assert bridge.properties["cauce"] == "LIA" and bridge.properties["anio_construccion"] is None
