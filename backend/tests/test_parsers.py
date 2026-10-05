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
