"""Parsing of user input, geocoding, timezone lookup and text formatting."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from dateutil import parser as dtparser
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder

USER_AGENT = os.environ.get("GEOCODER_USER_AGENT", "tg-photo-stamp-bot/1.0")
_geocoder = Nominatim(user_agent=USER_AGENT, timeout=15)
_tf = TimezoneFinder()

US_STATES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA",
    "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
    "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH",
    "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY", "North Carolina": "NC",
    "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA",
    "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN",
    "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
    "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY", "District of Columbia": "DC",
    "Puerto Rico": "PR",
}
CA_PROVINCES = {
    "Alberta": "AB", "British Columbia": "BC", "Manitoba": "MB", "New Brunswick": "NB",
    "Newfoundland and Labrador": "NL", "Nova Scotia": "NS", "Ontario": "ON",
    "Prince Edward Island": "PE", "Quebec": "QC", "Québec": "QC", "Saskatchewan": "SK",
    "Northwest Territories": "NT", "Nunavut": "NU", "Yukon": "YT",
}


STREET_ABBR = {
    "Expressway": "Expy", "Street": "St", "Avenue": "Ave", "Boulevard": "Blvd", "Road": "Rd",
    "Drive": "Dr", "Lane": "Ln", "Court": "Ct", "Place": "Pl", "Parkway": "Pkwy",
    "Highway": "Hwy", "Freeway": "Fwy", "Turnpike": "Tpke", "Terrace": "Ter", "Square": "Sq",
    "Circle": "Cir", "North": "N", "South": "S", "East": "E", "West": "W",
}


def abbreviate_street(name: str) -> str:
    return " ".join(STREET_ABBR.get(w, w) for w in name.split())


class InputError(ValueError):
    pass


# ---------------------------------------------------------------- coordinates
_NUM = r"[-+]?\d{1,3}(?:\.\d+)?"
_DEC = r"[-+]?\d{1,3}\.\d+"
_DECIMAL_RE = re.compile(rf"(?<![\d.])({_DEC})\s*[,;\s]\s*({_DEC})(?![\d.])")
_DMS_PART = r"([NSEW])?\s*(\d{1,3})\s*°\s*(?:(\d{1,2})\s*['′]\s*)?(?:(\d{1,2}(?:\.\d+)?)\s*(?:\"|″|''))?\s*([NSEW])?"
_DMS_RE = re.compile(rf"{_DMS_PART}\s*[,;\s]\s*{_DMS_PART}", re.I)


def _dms_to_dec(hemi1, d, m, s, hemi2) -> tuple[float, str]:
    val = float(d) + float(m or 0) / 60 + float(s or 0) / 3600
    hemi = (hemi1 or hemi2 or "").upper()
    if hemi in ("S", "W"):
        val = -val
    return val, hemi


def find_coords(text: str) -> tuple[float, float, str] | None:
    """Return (lat, lon, remaining_text) if text contains coordinates."""
    m = _DMS_RE.search(text)
    if m:
        a, ha = _dms_to_dec(*m.groups()[:5])
        b, hb = _dms_to_dec(*m.groups()[5:])
        lat, lon = (b, a) if ha in ("E", "W") or hb in ("N", "S") else (a, b)
        return lat, lon, text[: m.start()] + text[m.end():]
    for m in _DECIMAL_RE.finditer(text):
        lat, lon = float(m.group(1)), float(m.group(2))
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon, text[: m.start()] + text[m.end():]
    return None


def to_dms(lat: float, lon: float) -> str:
    def one(v: float, pos: str, neg: str) -> str:
        hemi = pos if v >= 0 else neg
        v = abs(v)
        d = int(v)
        m = int((v - d) * 60)
        s = (v - d - m / 60) * 3600
        if round(s, 3) >= 60:
            s, m = 0.0, m + 1
        if m >= 60:
            m, d = 0, d + 1
        return f"{hemi} {d}° {m}' {s:.3f}\""

    return f"{one(lat, 'N', 'S')}, {one(lon, 'E', 'W')}"


# ---------------------------------------------------------------- geocoding
def _address_lines(addr: dict, display_name: str = "") -> list[str]:
    road = addr.get("road") or addr.get("pedestrian") or addr.get("highway") or ""
    if (addr.get("country_code") or "").lower() in ("us", "ca"):
        road = abbreviate_street(road)
        road = re.sub(r"^(I|US) (\d+)", r"\1-\2", road)   # "I 77" -> "I-77"
    if road and addr.get("house_number"):
        road = f"{addr['house_number']} {road}"
    line1 = road or addr.get("neighbourhood") or addr.get("suburb") or ""

    city = (addr.get("city") or addr.get("town") or addr.get("village")
            or addr.get("hamlet") or addr.get("municipality") or addr.get("county") or "")
    if city == "City of New York":
        city = "New York"
    state = addr.get("state", "")
    cc = (addr.get("country_code") or "").lower()
    if cc == "us":
        state = US_STATES.get(state, state)
    elif cc == "ca":
        state = CA_PROVINCES.get(state, state)
    line2 = " ".join(p for p in (city, state, addr.get("postcode", "")) if p)
    line3 = addr.get("country", "")

    lines = [l for l in (line1, line2, line3) if l]
    if not lines and display_name:
        lines = [p.strip() for p in display_name.split(",")][:3]
    return lines


def reverse_geocode(lat: float, lon: float) -> list[str]:
    loc = _geocoder.reverse((lat, lon), language="en", addressdetails=True, zoom=18)
    if loc is None:
        return []
    return _address_lines(loc.raw.get("address", {}), loc.address)


def forward_geocode(query: str) -> tuple[float, float, list[str]] | None:
    loc = _geocoder.geocode(query, language="en", addressdetails=True)
    if loc is None:
        return None
    return loc.latitude, loc.longitude, _address_lines(loc.raw.get("address", {}), loc.address)


def timezone_at(lat: float, lon: float) -> ZoneInfo:
    name = _tf.timezone_at(lat=lat, lng=lon) or _tf.certain_timezone_at(lat=lat, lng=lon)
    return ZoneInfo(name or "UTC")


# ---------------------------------------------------------------- time
def parse_time(text: str, tz: ZoneInfo) -> datetime:
    text = text.strip().replace(" at ", " ")
    if not text or text.lower() == "now":
        return datetime.now(tz)
    try:
        dt = dtparser.parse(text, fuzzy=True)
    except (ValueError, OverflowError) as e:
        raise InputError(f"Could not understand the time: {text!r}") from e
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)          # time given in the location's local time
    return dt.astimezone(tz)                  # time with an explicit zone -> convert


def tz_abbrev(dt: datetime) -> str:
    abbr = dt.strftime("%Z")
    if not abbr or abbr[0] in "+-":           # zoneinfo has no letters for some zones
        off = dt.utcoffset()
        mins = int(off.total_seconds() // 60) if off else 0
        sign = "+" if mins >= 0 else "-"
        h, m = divmod(abs(mins), 60)
        abbr = f"GMT{sign}{h}" + (f":{m:02d}" if m else "")
    return abbr


def format_time(dt: datetime) -> str:
    hour = dt.hour % 12 or 12
    return f"{dt:%b} {dt.day}, {dt.year} at {hour}:{dt:%M:%S} {dt:%p} {tz_abbrev(dt)}"


# ---------------------------------------------------------------- main entry
_LABEL_RE = re.compile(r"^\s*(time|date|datetime|location|address|coords?|coordinates|gps)\s*[:=-]\s*", re.I)


@dataclass
class Stamp:
    lines: list[str]
    tz_name: str


def build_stamp(text: str) -> Stamp:
    """Turn the user's text into the overlay lines.

    Coordinates given  -> time, time, DMS coordinates, reverse-geocoded address.
    Address given      -> time, time, address (no coordinates).
    """
    raw_lines = [_LABEL_RE.sub("", l).strip() for l in text.strip().splitlines() if l.strip()]
    if not raw_lines:
        raise InputError("Please send the time and a location.")
    joined = "\n".join(raw_lines)

    coords = find_coords(joined)
    if coords:
        lat, lon, rest = coords
        tz = timezone_at(lat, lon)
        dt = parse_time(" ".join(rest.split()), tz)
        address = reverse_geocode(lat, lon)
        lines = [f"Network:{format_time(dt)}", f"Local:{format_time(dt)}", to_dms(lat, lon), *address]
        return Stamp(lines, tz.key)

    if re.search(r"[-+]?\d+\.\d+\s*[,;]\s*[-+]?\d{4,}\b|[-+]?\d{4,}\s*[,;]\s*[-+]?\d+\.\d+", joined):
        raise InputError(
            "The coordinates look incomplete (missing decimal point?). "
            "Example: 35.779173, -80.863518"
        )
    if len(raw_lines) < 2:
        raise InputError(
            "Send the time on the first line and the address (or coordinates) on the next line."
        )
    time_text, addr_text = raw_lines[0], ", ".join(raw_lines[1:])
    found = forward_geocode(addr_text)
    if not found:
        raise InputError(f"Address not found: {addr_text!r}")
    lat, lon, geo_lines = found
    tz = timezone_at(lat, lon)
    dt = parse_time(time_text, tz)
    # Keep the address exactly as the user typed it if they wrote it on several lines
    address = raw_lines[1:] if len(raw_lines) > 2 else geo_lines
    lines = [f"Network:{format_time(dt)}", f"Local:{format_time(dt)}", *address]
    return Stamp(lines, tz.key)
