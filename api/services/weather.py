# ============================================================
# Weather — service layer
# ============================================================
# Owns *how* to reach a weather provider and normalise its response. It
# owns no domain policy: the caller picks the units and decides what
# Candy says about the result.
#
# Primary provider is wttr.in's JSON view (`?format=j1`), the same one
# Jarvis 2 uses in `app/server.py` — free, no API key, no signup, and it
# already returns human-readable descriptions ("Patchy rain nearby") so
# nothing here has to map numeric weather codes to words.
#
# Two things from Jarvis 2 are deliberately NOT carried over:
#   * its regex that strips "weather/forecast/today/in/at..." out of the
#     query to guess a location. Candy gets a clean city name from the
#     model's tool call, so there is nothing to strip.
#   * its placement inside a general web-search function. Weather is its
#     own capability here, callable on its own.
#
# Open-Meteo is kept as a fallback because wttr.in rate-limits under load
# and a demo that dies mid-question is worse than a second provider. This
# mirrors the model fallback already in `litellm_router`.

import logging
from dataclasses import dataclass

import httpx

log = logging.getLogger(__name__)

WTTR_URL = "https://wttr.in/{city}?format=j1"
OPEN_METEO_GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_S = 12.0

# wttr.in serves an ASCII art page to unknown agents and JSON to curl.
_HEADERS = {"User-Agent": "curl/8"}


@dataclass(frozen=True)
class WeatherResult:
    """
    Callers branch on `ok`. `error` is operator-facing and never spoken.
    `place` echoes the location the provider actually resolved, so Candy
    can name it back and the user can catch a wrong "Springfield".
    """

    ok: bool
    place: str | None = None
    current: dict | None = None
    tomorrow: dict | None = None
    source: str | None = None
    error: str | None = None


def _wttr(city: str, fahrenheit: bool) -> WeatherResult:
    r = httpx.get(WTTR_URL.format(city=city), headers=_HEADERS, timeout=TIMEOUT_S)
    r.raise_for_status()
    d = r.json()

    area = (d.get("nearest_area") or [{}])[0]
    def _first(key):
        return (area.get(key) or [{}])[0].get("value", "")
    place = ", ".join(p for p in (_first("areaName"), _first("region"), _first("country")) if p)

    cur = (d.get("current_condition") or [{}])[0]
    t, feels, wind = ("temp_F", "FeelsLikeF", "windspeedMiles") if fahrenheit \
        else ("temp_C", "FeelsLikeC", "windspeedKmph")
    current = {
        "temperature": cur.get(t),
        "feels_like": cur.get(feels),
        "conditions": (cur.get("weatherDesc") or [{}])[0].get("value", ""),
        "humidity": cur.get("humidity"),
        "wind": cur.get("windspeedMiles" if fahrenheit else "windspeedKmph"),
        "unit": "F" if fahrenheit else "C",
    }

    days = d.get("weather") or []
    tomorrow = None
    if len(days) > 1:
        day = days[1]
        hourly = day.get("hourly") or []
        # Index 4 is midday on wttr's 3-hourly grid (00,03,...,21) — the
        # single slot that best characterises "what tomorrow is like".
        midday = hourly[4] if len(hourly) > 4 else (hourly[0] if hourly else {})
        rain = [int(h.get("chanceofrain", 0) or 0) for h in hourly] or [0]
        tomorrow = {
            "date": day.get("date"),
            "high": day.get("maxtempF" if fahrenheit else "maxtempC"),
            "low": day.get("mintempF" if fahrenheit else "mintempC"),
            "conditions": (midday.get("weatherDesc") or [{}])[0].get("value", ""),
            "precipitation_chance": max(rain),
            "unit": "F" if fahrenheit else "C",
        }

    return WeatherResult(ok=True, place=place or city, current=current,
                         tomorrow=tomorrow, source="wttr.in")


_WMO = {
    0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "freezing fog", 51: "light drizzle", 53: "drizzle",
    55: "heavy drizzle", 56: "freezing drizzle", 57: "heavy freezing drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain",
    67: "heavy freezing rain", 71: "light snow", 73: "snow", 75: "heavy snow",
    77: "snow grains", 80: "light showers", 81: "showers",
    82: "violent showers", 85: "light snow showers", 86: "snow showers",
    95: "a thunderstorm", 96: "a thunderstorm with hail",
    99: "a thunderstorm with heavy hail",
}


def _open_meteo(city: str, fahrenheit: bool) -> WeatherResult:
    g = httpx.get(OPEN_METEO_GEOCODE,
                  params={"name": city, "count": 1, "language": "en", "format": "json"},
                  timeout=TIMEOUT_S)
    g.raise_for_status()
    hits = g.json().get("results") or []
    if not hits:
        return WeatherResult(ok=False, error=f"no place matched {city!r}")
    top = hits[0]
    place = ", ".join(p for p in (top.get("name"), top.get("admin1"), top.get("country")) if p)

    f = httpx.get(OPEN_METEO_FORECAST, params={
        "latitude": top["latitude"], "longitude": top["longitude"],
        "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,relative_humidity_2m",
        "daily": "temperature_2m_max,temperature_2m_min,weather_code,precipitation_probability_max",
        "timezone": "auto", "forecast_days": 2,
        "temperature_unit": "fahrenheit" if fahrenheit else "celsius",
        "wind_speed_unit": "mph" if fahrenheit else "kmh",
    }, timeout=TIMEOUT_S)
    f.raise_for_status()
    data = f.json()
    cur, daily = data.get("current", {}), data.get("daily", {})
    unit = "F" if fahrenheit else "C"

    def day(key, i=1):
        vals = daily.get(key) or []
        return vals[i] if len(vals) > i else None

    return WeatherResult(
        ok=True, place=place, source="open-meteo",
        current={
            "temperature": cur.get("temperature_2m"),
            "feels_like": cur.get("apparent_temperature"),
            "conditions": _WMO.get(cur.get("weather_code"), "unsettled"),
            "humidity": cur.get("relative_humidity_2m"),
            "wind": cur.get("wind_speed_10m"),
            "unit": unit,
        },
        tomorrow={
            "date": day("time"),
            "high": day("temperature_2m_max"),
            "low": day("temperature_2m_min"),
            "conditions": _WMO.get(day("weather_code"), "unsettled"),
            "precipitation_chance": day("precipitation_probability_max"),
            "unit": unit,
        },
    )


def get_weather(city: str, *, fahrenheit: bool = True) -> WeatherResult:
    """
    Current conditions plus tomorrow's forecast for a named city.

    Both come from one provider call — a spoken answer shouldn't wait on a
    second round trip when the first response already carries the forecast.
    """
    city = (city or "").strip()
    if not city:
        return WeatherResult(ok=False, error="no city given")

    errors = []
    for name, fetch in (("wttr.in", _wttr), ("open-meteo", _open_meteo)):
        try:
            result = fetch(city, fahrenheit)
            if result.ok:
                return result
            errors.append(f"{name}: {result.error}")
        except Exception as exc:
            log.warning("Weather lookup failed on %s for %r: %s", name, city, exc)
            errors.append(f"{name}: {exc}")

    return WeatherResult(ok=False, error=" | ".join(errors))
