import json
import urllib.request

_cache = {}
LOCALHOST_VALID = True

def is_valid_location(ip: str) -> bool:
    if ip == "127.0.0.1":
        return LOCALHOST_VALID
    loc = get_location(ip)
    # Consider "Unknown" or "Blocked" as invalid.
    if "Unknown" in loc or "Blocked" in loc or "Invalid" in loc:
        return False
    return True

def get_location(ip: str) -> str:
    if ip == "127.0.0.1":
        if LOCALHOST_VALID:
            return "🏠 Localhost (Simulated US)"
        else:
            return "🛑 Localhost (Simulated Blocked Region)"
    if ip in _cache:
        return _cache[ip]
    try:
        req = urllib.request.Request(f"http://ip-api.com/json/{ip}?fields=country,city")
        with urllib.request.urlopen(req, timeout=1) as response:
            data = json.loads(response.read())
            loc = f"🌍 {data.get('city', 'Unknown')}, {data.get('country', 'Unknown')}"
            _cache[ip] = loc
            return loc
    except Exception:
        _cache[ip] = "❓ Unknown Location"
        return "❓ Unknown Location"

