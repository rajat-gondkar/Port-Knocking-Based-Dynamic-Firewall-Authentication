import json
import urllib.request

_cache = {"127.0.0.1": "🏠 Localhost (Simulated US)"}

def get_location(ip: str) -> str:
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
