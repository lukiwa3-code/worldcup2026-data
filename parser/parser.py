import json
import hashlib
import time
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests


FIFA_MATCHES_URL = "https://api.fifa.com/api/v3/calendar/matches?language=en&count=500&idSeason=285023"
FIFA_STANDINGS_URL = "https://api.fifa.com/api/v3/calendar/17/285023/289273/standing?language=en&count=200"

OUTPUT_DIR = Path("data")
MATCHES_FILE = OUTPUT_DIR / "matches_clean.json"
METADATA_FILE = OUTPUT_DIR / "metadata.json"
MATCH_DETAILS_DIR = OUTPUT_DIR / "match_details"
STANDINGS_FILE = OUTPUT_DIR / "standings_clean.json"

POLAND_TZ = ZoneInfo("Europe/Warsaw")


def get_description(value):
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
    if side == "home":
        score = match.get("HomeTeamScore")
        team = match.get("Home") or match.get("HomeTeam")
    else:
        score = match.get("AwayTeamScore")
        team = match.get("Away") or match.get("AwayTeam")

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

        "id_competition": match.get("IdCompetition"),
        "id_season": match.get("IdSeason"),
        "id_stage": match.get("IdStage"),
        "id_group": match.get("IdGroup"),

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

        "time_defined": match.get("TimeDefined"),

        "details_file": f"match_details/{match.get('IdMatch')}.json"
    }


def load_previous_metadata():
    if not METADATA_FILE.exists():
        return {}

    try:
        return json.loads(METADATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_text_if_changed(path, text):
    if path.exists():
        old_text = path.read_text(encoding="utf-8")
        if old_text == text:
            return False

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def download_json(url):
    headers = {
        "User-Agent": "Mozilla/5.0 WorldCup2026DataParser/1.0",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.fifa.com/"
    }

    response = requests.get(url, headers=headers, timeout=40)
    response.raise_for_status()
    return response.json()


def save_matches(clean_matches, source_url):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    clean_text = json.dumps(clean_matches, ensure_ascii=False, indent=2)
    clean_text_for_hash = json.dumps(clean_matches, ensure_ascii=False, sort_keys=True)
    data_hash = hashlib.sha256(clean_text_for_hash.encode("utf-8")).hexdigest()

    previous_metadata = load_previous_metadata()
    previous_hash = previous_metadata.get("data_hash")

    matches_changed = previous_hash != data_hash or not MATCHES_FILE.exists()

    if matches_changed:
        MATCHES_FILE.write_text(clean_text, encoding="utf-8")

    now_utc = datetime.now(timezone.utc).isoformat()

    metadata = {
        "updated_at_utc": now_utc,
        "updated_at_poland": datetime.now(POLAND_TZ).isoformat(),
        "matches_count": len(clean_matches),
        "data_hash": data_hash,
        "source": "FIFA",
        "source_url": source_url,
        "match_details_folder": "data/match_details"
    }

    metadata_text = json.dumps(metadata, ensure_ascii=False, indent=2)

    if matches_changed:
        METADATA_FILE.write_text(metadata_text, encoding="utf-8")
        print(f"Saved {len(clean_matches)} matches.")
        print(f"Data hash: {data_hash}")
    else:
        print("No changes in matches_clean.json.")


def build_match_detail_url(match):
    id_competition = match.get("IdCompetition")
    id_season = match.get("IdSeason")
    id_stage = match.get("IdStage")
    id_match = match.get("IdMatch")

    if not id_competition or not id_season or not id_stage or not id_match:
        return None

    return (
        f"https://api.fifa.com/api/v3/live/football/"
        f"{id_competition}/{id_season}/{id_stage}/{id_match}?language=en"
    )


def simplify_player(player):
    return {
        "id_player": player.get("IdPlayer"),
        "id_team": player.get("IdTeam"),
        "shirt_number": player.get("ShirtNumber"),
        "status": player.get("Status"),
        "captain": player.get("Captain"),
        "name": get_description(player.get("PlayerName")),
        "short_name": get_description(player.get("ShortName")),
        "position": player.get("Position"),
        "field_status": player.get("FieldStatus"),
        "lineup_x": player.get("LineupX"),
        "lineup_y": player.get("LineupY")
    }


def simplify_goal(goal):
    return {
        "type": goal.get("Type"),
        "id_player": goal.get("IdPlayer"),
        "minute": goal.get("Minute"),
        "id_assist_player": goal.get("IdAssistPlayer"),
        "period": goal.get("Period"),
        "id_team": goal.get("IdTeam")
    }


def simplify_booking(booking):
    return {
        "card": booking.get("Card"),
        "period": booking.get("Period"),
        "id_player": booking.get("IdPlayer"),
        "id_team": booking.get("IdTeam"),
        "minute": booking.get("Minute"),
        "reason": booking.get("Reason")
    }


def simplify_substitution(substitution):
    return {
        "period": substitution.get("Period"),
        "minute": substitution.get("Minute"),
        "id_team": substitution.get("IdTeam"),
        "id_player_off": substitution.get("IdPlayerOff"),
        "id_player_on": substitution.get("IdPlayerOn"),
        "player_off_name": get_description(substitution.get("PlayerOffName")),
        "player_on_name": get_description(substitution.get("PlayerOnName"))
    }


def simplify_official(official):
    return {
        "id": official.get("OfficialId"),
        "country": official.get("IdCountry"),
        "name": get_description(official.get("Name")),
        "short_name": get_description(official.get("NameShort")),
        "type": get_description(official.get("TypeLocalized")),
        "official_type": official.get("OfficialType")
    }


def simplify_team_detail(team):
    if not isinstance(team, dict):
        return None

    players = team.get("Players") or []
    goals = team.get("Goals") or []
    bookings = team.get("Bookings") or []
    substitutions = team.get("Substitutions") or []

    return {
        "id_team": team.get("IdTeam"),
        "name": get_description(team.get("TeamName")) or team.get("ShortClubName"),
        "short_name": team.get("ShortClubName"),
        "abbr": team.get("Abbreviation"),
        "country": team.get("IdCountry"),
        "score": team.get("Score"),
        "tactics": team.get("Tactics"),
        "flag": make_flag_url(team.get("PictureUrl")),
        "players": [simplify_player(player) for player in players],
        "goals": [simplify_goal(goal) for goal in goals],
        "bookings": [simplify_booking(booking) for booking in bookings],
        "substitutions": [simplify_substitution(sub) for sub in substitutions]
    }


def simplify_match_detail(raw_detail):
    return {
        "id_match": raw_detail.get("IdMatch"),
        "id_competition": raw_detail.get("IdCompetition"),
        "id_season": raw_detail.get("IdSeason"),
        "id_stage": raw_detail.get("IdStage"),
        "id_group": raw_detail.get("IdGroup"),

        "competition": get_description(raw_detail.get("CompetitionName")),
        "season": get_description(raw_detail.get("SeasonName")),
        "stage": get_description(raw_detail.get("StageName")),
        "group": get_description(raw_detail.get("GroupName")),

        "match_number": raw_detail.get("MatchNumber"),
        "date_utc": raw_detail.get("Date"),
        "date_local": raw_detail.get("LocalDate"),
        "date_poland": convert_utc_to_poland(raw_detail.get("Date")),

        "attendance": raw_detail.get("Attendance"),
        "match_time": raw_detail.get("MatchTime"),
        "period": raw_detail.get("Period"),
        "winner": raw_detail.get("Winner"),

        "home_score": raw_detail.get("HomeTeamScore"),
        "away_score": raw_detail.get("AwayTeamScore"),
        "home_penalty_score": raw_detail.get("HomeTeamPenaltyScore"),
        "away_penalty_score": raw_detail.get("AwayTeamPenaltyScore"),

        "stadium": parse_stadium(raw_detail.get("Stadium")),
        "weather": raw_detail.get("Weather"),

        "home_team": simplify_team_detail(raw_detail.get("HomeTeam") or raw_detail.get("Home")),
        "away_team": simplify_team_detail(raw_detail.get("AwayTeam") or raw_detail.get("Away")),

        "officials": [simplify_official(official) for official in (raw_detail.get("Officials") or [])],

        "match_status_code": raw_detail.get("MatchStatus"),
        "result_type": raw_detail.get("ResultType"),
        "officiality_status": raw_detail.get("OfficialityStatus"),
        "time_defined": raw_detail.get("TimeDefined"),

        "raw_available": True
    }


def save_match_details(raw_matches):
    MATCH_DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    saved = 0
    skipped = 0
    failed = 0
    index_entries = []

    for index, match in enumerate(raw_matches, start=1):
        id_match = match.get("IdMatch")
        detail_url = build_match_detail_url(match)

        if not id_match:
            skipped += 1
            continue

        try:
            if detail_url:
                raw_detail = download_json(detail_url)
                clean_detail = simplify_match_detail(raw_detail)
                clean_detail["raw_available"] = True
                clean_detail["details_error"] = None
                print(f"[{index}] Downloaded live detail: {id_match}")
            else:
                raise RuntimeError("Missing detail URL")

        except Exception as error:
            failed += 1

            # Fallback: zapisujemy podstawowe dane z terminarza.
            # Dzięki temu folder match_details pojawi się zawsze,
            # nawet jeśli FIFA nie udostępnia jeszcze składów.
            clean_detail = simplify_match_detail(match)
            clean_detail["raw_available"] = False
            clean_detail["details_error"] = str(error)
            print(f"[{index}] Live detail unavailable, saved fallback: {id_match} | {error}")

        clean_detail["source_url"] = detail_url
        clean_detail["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
        clean_detail["updated_at_poland"] = datetime.now(POLAND_TZ).isoformat()

        detail_text = json.dumps(clean_detail, ensure_ascii=False, indent=2)
        detail_path = MATCH_DETAILS_DIR / f"{id_match}.json"

        changed = write_text_if_changed(detail_path, detail_text)

        if changed:
            saved += 1
        else:
            skipped += 1

        index_entries.append({
            "id_match": id_match,
            "match_number": match.get("MatchNumber"),
            "file": f"match_details/{id_match}.json",
            "source_url": detail_url,
            "raw_available": clean_detail.get("raw_available"),
            "details_error": clean_detail.get("details_error")
        })

        time.sleep(0.15)

    index_text = json.dumps(index_entries, ensure_ascii=False, indent=2)
    write_text_if_changed(OUTPUT_DIR / "match_details_index.json", index_text)

    print(f"Match details summary: saved={saved}, skipped={skipped}, failed={failed}")

def simplify_standing_row(row):
    team = row.get("Team") or {}

    return {
        "id_competition": row.get("IdCompetition"),
        "id_season": row.get("IdSeason"),
        "id_stage": row.get("IdStage"),
        "id_group": row.get("IdGroup"),
        "id_team": row.get("IdTeam"),

        "group": get_description(row.get("Group")),
        "position": row.get("Position"),
        "previous_position": row.get("PreviousPosition"),

        "played": row.get("Played"),
        "won": row.get("Won"),
        "drawn": row.get("Drawn"),
        "lost": row.get("Lost"),

        "goals_for": row.get("For"),
        "goals_against": row.get("Against"),
        "goal_difference": row.get("GoalsDiference"),
        "points": row.get("Points"),

        "home_played": row.get("HomePlayed"),
        "home_won": row.get("HomeWon"),
        "home_drawn": row.get("HomeDrawn"),
        "home_lost": row.get("HomeLost"),
        "home_for": row.get("HomeFor"),
        "home_against": row.get("HomeAgainst"),
        "home_points": row.get("HomePoints"),

        "away_played": row.get("AwayPlayed"),
        "away_won": row.get("AwayWon"),
        "away_drawn": row.get("AwayDrawn"),
        "away_lost": row.get("AwayLost"),
        "away_for": row.get("AwayFor"),
        "away_against": row.get("AwayAgainst"),
        "away_points": row.get("AwayPoints"),

        "qualification_status": row.get("QualificationStatus"),
        "fair_play_coefficient": row.get("FairPlayCoefficient"),
        "is_live": row.get("IsLive"),

        "team": {
            "id": team.get("IdTeam"),
            "name": get_description(team.get("Name")) or team.get("ShortClubName"),
            "short_name": team.get("ShortClubName"),
            "abbr": team.get("Abbreviation"),
            "country": team.get("IdCountry"),
            "confederation": team.get("IdConfederation"),
            "flag": make_flag_url(team.get("PictureUrl"))
        }
    }


def group_sort_key(group_name):
    if not group_name:
        return "Z"

    # "Group A" -> "A"
    parts = group_name.split()
    if len(parts) >= 2:
        return parts[-1]

    return group_name


def save_standings():
    raw_data = download_json(FIFA_STANDINGS_URL)

    if isinstance(raw_data, dict):
        raw_rows = raw_data.get("Results", [])
    elif isinstance(raw_data, list):
        raw_rows = raw_data
    else:
        raise RuntimeError("Unknown standings data format.")

    standings = [simplify_standing_row(row) for row in raw_rows]

    standings.sort(
        key=lambda row: (
            group_sort_key(row.get("group")),
            row.get("position") if row.get("position") is not None else 999,
            row.get("team", {}).get("name") or ""
        )
    )

    standings_text = json.dumps(standings, ensure_ascii=False, indent=2)
    changed = write_text_if_changed(STANDINGS_FILE, standings_text)

    if changed:
        print(f"Saved standings: {len(standings)} rows.")
    else:
        print("No changes in standings_clean.json.")
def main():
    raw_data = download_json(FIFA_MATCHES_URL)

    if isinstance(raw_data, dict):
        raw_matches = raw_data.get("Results", [])
    elif isinstance(raw_data, list):
        raw_matches = raw_data
    else:
        raise RuntimeError("Unknown FIFA data format.")

    clean_matches = [parse_match(match) for match in raw_matches]

    clean_matches.sort(
        key=lambda item: item["match_number"] if item["match_number"] is not None else 9999
    )

    save_matches(clean_matches, FIFA_MATCHES_URL)
    save_match_details(raw_matches)
    save_standings()


if __name__ == "__main__":
    main()
