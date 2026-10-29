from pathlib import Path

from weather import fmi

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_observations_maps_params_and_skips_nan() -> None:
    readings = fmi.parse((FIXTURES / "observations.xml").read_bytes(), fmi.OBSERVATION_PARAMS)
    assert len(readings) == 25
    assert {r.param for r in readings} == set(fmi.OBSERVATION_PARAMS.values())
    assert all(r.ts.tzinfo is not None for r in readings)
    assert sum(r.param == "precipitation" for r in readings) == 1


def test_parse_forecast() -> None:
    readings = fmi.parse((FIXTURES / "forecast.xml").read_bytes(), fmi.FORECAST_PARAMS)
    assert len(readings) == 15
    assert {r.param for r in readings} == set(fmi.FORECAST_PARAMS.values())
