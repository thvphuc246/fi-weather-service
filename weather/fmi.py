import math
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from typing import NamedTuple

WFS_URL = "https://opendata.fmi.fi/wfs"
OBSERVATIONS = "fmi::observations::weather::simple"
FORECAST = "fmi::forecast::edited::weather::scandinavia::point::simple"
FORECAST_AHEAD = timedelta(days=10)

OBSERVATION_PARAMS = {
    "t2m": "temperature",
    "ws_10min": "wind_speed",
    "rh": "humidity",
    "r_1h": "precipitation",
    "p_sea": "pressure",
}
FORECAST_PARAMS = {
    "Temperature": "temperature",
    "WindSpeedMS": "wind_speed",
    "Humidity": "humidity",
    "Precipitation1h": "precipitation",
    "Pressure": "pressure",
}

NS = {"BsWfs": "http://xml.fmi.fi/schema/wfs/2.0"}


class Reading(NamedTuple):
    ts: datetime
    param: str
    value: float


def parse(xml: bytes, names: dict[str, str]) -> list[Reading]:
    readings = []
    for el in ET.fromstring(xml).iterfind(".//BsWfs:BsWfsElement", NS):
        name = el.findtext("BsWfs:ParameterName", namespaces=NS)
        time = el.findtext("BsWfs:Time", namespaces=NS)
        value = float(el.findtext("BsWfs:ParameterValue", "nan", NS))
        if name in names and time and not math.isnan(value):
            readings.append(Reading(datetime.fromisoformat(time), names[name], value))
    return readings


def _iso(ts: datetime) -> str:
    return ts.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get(query: str, place: str, params: dict[str, str], **times: datetime) -> bytes:
    qs = urllib.parse.urlencode(
        {
            "service": "WFS",
            "version": "2.0.0",
            "request": "getFeature",
            "storedquery_id": query,
            "place": place,
            "parameters": ",".join(params),
            **{k: _iso(v) for k, v in times.items()},
        }
    )
    with urllib.request.urlopen(f"{WFS_URL}?{qs}", timeout=60) as resp:
        body: bytes = resp.read()
        return body


def fetch_observations(place: str, start: datetime) -> list[Reading]:
    return parse(_get(OBSERVATIONS, place, OBSERVATION_PARAMS, starttime=start), OBSERVATION_PARAMS)


def fetch_forecast(place: str) -> list[Reading]:
    end = datetime.now(UTC) + FORECAST_AHEAD
    return parse(_get(FORECAST, place, FORECAST_PARAMS, endtime=end), FORECAST_PARAMS)
