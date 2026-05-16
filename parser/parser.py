import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests


# Public FIFA endpoint found in Chrome DevTools / Network.
# If FIFA changes the endpoint later, update this URL.
FIFA_MATCHES_URL = "https://api.fifa.com/api/v3/calendar/matches?language=en&count=500&idSeason=285023"

OUTPUT_DIR = Path("data")
MATCHES_FILE = OUTPUT_DIR / "matches_clean.json"
METADATA_FILE = OUTPUT_DIR / "metadata.json"

POLAND_TZ = ZoneInfo("Europe/Warsaw")


def get_description(value):
    """
    FIFA often stores names like:
    [
      {"Locale": "en-GB", "Description": "Mexico"}
    ]
    This function returns only the Description.
    """
    if isinstance(value, list) and len(value) > 0:
        return value[0].get("Description")
    return None


def convert_utc_to_poland(value):
    if not value:
        return None

    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(POLAND_TZ).isoformat()
    except Exception:
        return None


def make_flag_url(url):
    if not url:
        return None

    return url.replace("{format}", "sq").replace("{size}", "3")


def parse_team(team_data, placeholder):
    """
    If a team is known, use team details.
    If not known yet, for example knockout stage placeholders, use PlaceHolderA / PlaceHolderB.
    """
    if team_data is None:
        return {
            "id": None,
            "name": placeholder,
            "abbr": placeholder,
            "country": None,
            "flag": None,
            "is_placeholder": True
        }

    name = get_description(team_data.get("TeamName")) or team_data.get("ShortClubName")

    return {
        "id": team_data.get("IdTeam"),
        "name": name,
        "abbr": team_data.get("Abbreviation"),
        "country": team_data.get("IdCountry"),
        "flag": make_flag_url(team_data.get("PictureUrl")),
        "is_placeholder": False
    }


def parse_stadium(stadium_data):
    if stadium_data is None:
        return {
            "id": None,
            "name": None,
            "city": None,
            "country": None
        }

    return {
        "id": stadium_data.get("IdStadium"),
        "name": get_description(stadium_data.get("Name")),
        "city": get_description(stadium_data.get("CityName")),
        "country": stadium_data.get("IdCountry")
    }


def get_score(match, side):
    """
    Main source: HomeTeamScore / AwayTeamScore.
    Backup source: Home.Score / Away.Score.
    """
    if side == "home":
        score = match.get("HomeTeamScore")
        team = match.get("Home")
    else:
        score = match.get("AwayTeamScore")
        team = match.get("Away")

    if score is not None:
        return score

    if isinstance(team, dict):
        return team.get("Score")

    return None


def parse_match(match):
    group_name = get_description(match.get("GroupName"))
    stage_name = get_description(match.get("StageName"))

    return {
        "match_number": match.get("MatchNumber"),
        "id_match": match.get("IdMatch"),

        "competition": get_description(match.get("CompetitionName")),
        "season": get_description(match.get("SeasonName")),
        "stage": stage_name,
        "group": group_name,
        "is_group_stage": bool(group_name),

        "date_utc": match.get("Date"),
        "date_local": match.get("LocalDate"),
        "date_poland": convert_utc_to_poland(match.get("Date")),

        "home": parse_team(match.get("Home"), match.get("PlaceHolderA")),
        "away": parse_team(match.get("Away"), match.get("PlaceHolderB")),

        "home_score": get_score(match, "home"),
        "away_score": get_score(match, "away"),
        "home_penalty_score": match.get("HomeTeamPenaltyScore"),
        "away_penalty_score": match.get("AwayTeamPenaltyScore"),

        "stadium": parse_stadium(match.get("Stadium")),

        "match_status_code": match.get("MatchStatus"),
        "result_type": match.get("ResultType"),
        "winner": match.get("Winner"),

        "placeholder_home": match.get("PlaceHolderA"),
        "placeholder_away": match.get("PlaceHolderB"),

        "time_defined": match.get("TimeDefined")
    }


def load_previous_metadata():
    if not METADATA_FILE.exists():
        return {}

    try:
        return json.loads(METADATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_json_if_changed(clean_matches, source_url):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    clean_text_for_hash = json.dumps(clean_matches, ensure_ascii=False, sort_keys=True)
    data_hash = hashlib.sha256(clean_text_for_hash.encode("utf-8")).hexdigest()

    previous_metadata = load_previous_metadata()
    previous_hash = previous_metadata.get("data_hash")

    if previous_hash == data_hash and MATCHES_FILE.exists():
        print("No data changes. Files were not overwritten.")
        return

    now_utc = datetime.now(timezone.utc).isoformat()

    metadata = {
        "updated_at_utc": now_utc,
        "updated_at_poland": datetime.now(POLAND_TZ).isoformat(),
        "matches_count": len(clean_matches),
        "data_hash": data_hash,
        "source": "FIFA",
        "source_url": source_url
    }

    MATCHES_FILE.write_text(
        json.dumps(clean_matches, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    METADATA_FILE.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"Saved {len(clean_matches)} matches.")
    print(f"Data hash: {data_hash}")


def main():
    headers = {
        "User-Agent": "Mozilla/5.0 WorldCup2026DataParser/1.0",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.fifa.com/"
    }

    response = requests.get(FIFA_MATCHES_URL, headers=headers, timeout=40)
    response.raise_for_status()

    raw_data = response.json()

    if isinstance(raw_data, dict):
        matches = raw_data.get("Results", [])
    elif isinstance(raw_data, list):
        matches = raw_data
    else:
        raise RuntimeError("Unknown FIFA data format.")

    clean_matches = [parse_match(match) for match in matches]

    clean_matches.sort(
        key=lambda item: item["match_number"] if item["match_number"] is not None else 9999
    )

    save_json_if_changed(clean_matches, FIFA_MATCHES_URL)


if __name__ == "__main__":
    main()
