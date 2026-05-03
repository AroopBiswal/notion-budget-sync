"""LLM-based column mapping with named profile persistence."""
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

CACHE_DIR = Path(".schema_cache")
PROFILES_FILE = CACHE_DIR / "profiles.json"

_MAPPING_FIELDS = ("date_col", "merchant_col", "amount_col", "category_col", "txn_id_col", "amount_sign")


def _headers_hash(headers: List[str]) -> str:
    key = "|".join(sorted(headers))
    return hashlib.sha1(key.encode()).hexdigest()[:8]


def load_profiles() -> Dict:
    if not PROFILES_FILE.exists():
        return {}
    return json.loads(PROFILES_FILE.read_text())


def save_profiles(profiles: Dict) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    PROFILES_FILE.write_text(json.dumps(profiles, indent=2))


def get_profile(name: str) -> Optional[Dict]:
    return load_profiles().get(name)


def find_cached_by_headers(headers: List[str]) -> Tuple[Optional[str], Optional[Dict]]:
    """Return (profile_name, mapping) if a profile matching these headers exists."""
    h = _headers_hash(headers)
    for name, profile in load_profiles().items():
        if profile.get("_hash") == h:
            return name, {k: profile[k] for k in _MAPPING_FIELDS if k in profile}
    return None, None


def infer_mapping(headers: List[str], rows: List[Dict]) -> Dict:
    """Call the LLM to infer the column mapping from headers + sample rows."""
    from ..llm.factory import get_provider
    provider = get_provider()

    sample = json.dumps(rows[:2], default=str)
    system = "Identify column roles in bank transaction data."
    user = (
        f"Headers: {headers}\n"
        f"Rows: {sample}\n\n"
        'Return: {"date_col":..., "merchant_col":..., "amount_col":..., '
        '"category_col":null, "txn_id_col":null, '
        '"amount_sign":"positive_is_charge"|"negative_is_charge"}\n'
        "amount_sign is negative_is_charge if purchases are negative numbers."
    )
    return provider.complete_json(system, user)


def save_profile(name: str, mapping: Dict, headers: List[str]) -> str:
    """Save a profile. Returns the actual name used (may be auto-numbered if duplicate)."""
    profiles = load_profiles()
    base = name
    counter = 2
    while name in profiles:
        name = f"{base} {counter}"
        counter += 1

    profiles[name] = {
        **{k: mapping.get(k) for k in _MAPPING_FIELDS},
        "_hash": _headers_hash(headers),
        "headers_preview": headers[:6],
        "saved": str(date.today()),
    }
    save_profiles(profiles)
    return name


def delete_profile(name: str) -> bool:
    profiles = load_profiles()
    if name not in profiles:
        return False
    del profiles[name]
    save_profiles(profiles)
    return True


def update_profile_fields(name: str, fields: Dict) -> bool:
    profiles = load_profiles()
    if name not in profiles:
        return False
    for k, v in fields.items():
        if k in _MAPPING_FIELDS:
            profiles[name][k] = v
    save_profiles(profiles)
    return True
