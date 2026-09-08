import requests
import json
import time
from datetime import datetime, timezone
from collections import defaultdict

LEAGUE_ID = "gpn5biw5mrzg1jwn"

# Week/period to retrieve
PERIOD = 1

# --------------------------------------------------
# Get Fantrax rosters
# --------------------------------------------------

roster_url = "https://www.fantrax.com/fxea/general/getTeamRosters"

roster_response = requests.get(
    roster_url,
    params={
        "leagueId": LEAGUE_ID,
        "period": PERIOD
    },
    timeout=30
)

roster_response.raise_for_status()

roster_data = roster_response.json()
rosters = roster_data["rosters"]

print("Fantasy teams:", len(rosters))

# --------------------------------------------------
# Get Fantrax player information
# --------------------------------------------------

player_url = "https://www.fantrax.com/fxea/general/getPlayerIds"

player_response = requests.get(
    player_url,
    params={"sport": "CFB"},
    timeout=30
)

player_response.raise_for_status()

player_data = player_response.json()

print("Player/team entries:", len(player_data))

# --------------------------------------------------
# Count how many fantasy teams roster each player
# --------------------------------------------------

player_teams = {}

for fantasy_team_id, fantasy_team in rosters.items():

    for roster_item in fantasy_team.get("rosterItems", []):

        player_id = roster_item.get("id")

        if not player_id:
            continue

        if player_id not in player_teams:
            player_teams[player_id] = set()

        player_teams[player_id].add(fantasy_team_id)

print("Unique rostered players:", len(player_teams))

# --------------------------------------------------
# Get Period 1 fantasy points
#
# We cannot use getPlayerStats here because that
# endpoint returns YTD fantasy points.
#
# Instead, getTeamRosterInfo for each fantasy team.
# This returns the player's fantasy points for the
# requested period.
# --------------------------------------------------

player_points = {}

successful = 0
failed = 0

for count, team_id in enumerate(rosters.keys(), start=1):

    payload = {
        "msgs": [
            {
                "method": "getTeamRosterInfo",
                "data": {
                    "leagueId": LEAGUE_ID,
                    "period": str(PERIOD),
                    "teamId": team_id,
                    "scoringCategoryType": "5",
                    "statsType": "2"
                }
            }
        ]
    }

    try:

        points_response = requests.post(
            "https://www.fantrax.com/fxpa/req",
            params={"leagueId": LEAGUE_ID},
            json=payload,
            timeout=60
        )

        points_response.raise_for_status()

        points_data = points_response.json()
        team_data = points_data["responses"][0]["data"]

        successful += 1

        # ------------------------------------------
        # Extract players from the roster tables
        # ------------------------------------------

        for table in team_data.get("tables", []):

            for row in table.get("rows", []):

                scorer = row.get("scorer", {})

                player_id = scorer.get("scorerId")
                name = scorer.get("name")

                if not player_id or not name:
                    continue

                cells = row.get("cells", [])

                # Cell 1 = Fantasy Points
                if len(cells) <= 1:
                    continue

                points_text = cells[1].get("content")

                try:
                    points = float(points_text)
                except (TypeError, ValueError):
                    continue

                # Save the first occurrence.
                #
                # The verification test showed that Fantrax
                # returns the same Period 1 value regardless
                # of which fantasy team we retrieve it from.
                if player_id not in player_points:

                    player_points[player_id] = points

        print(
            f"{count:2}/{len(rosters)} "
            f"| team {team_id} "
            f"| players with points: {len(player_points)}"
        )

    except Exception as e:

        failed += 1

        print(
            f"{count:2}/{len(rosters)} "
            f"| ERROR on {team_id}: {e}"
        )

    # Small pause between requests
    time.sleep(0.15)

print()
print("Teams successfully queried:", successful)
print("Teams failed:", failed)
print("Players with fantasy points:", len(player_points))

# --------------------------------------------------
# Build player results
# --------------------------------------------------

total_teams = len(rosters)

players = []

for player_id, teams in player_teams.items():

    info = player_data.get(player_id, {})

    if not info.get("name"):
        continue

    teams_rostered = len(teams)

    roster_share = (
        teams_rostered / total_teams
    ) * 100

    players.append({
        "Player": info.get("name", ""),
        "Team": info.get("team", ""),
        "Pos": info.get("position", ""),
        "Teams": teams_rostered,
        "League Teams": total_teams,
        "Roster Share": round(roster_share, 1),
        "Fantasy Points": player_points.get(player_id)
    })

# --------------------------------------------------
# Sort by roster share
# --------------------------------------------------

players.sort(
    key=lambda x: (
        -x["Roster Share"],
        x["Player"]
    )
)

# --------------------------------------------------
# Create JSON
# --------------------------------------------------

output = {
    "last_updated": datetime.now(timezone.utc).isoformat(),
    "period": PERIOD,
    "league_teams": total_teams,
    "players": players
}

with open("roster_share.json", "w") as f:

    json.dump(
        output,
        f,
        indent=2
    )

# --------------------------------------------------
# Final verification
# --------------------------------------------------

print()
print("=" * 60)
print("FINAL RESULTS")
print("=" * 60)

print("Players:", len(players))
print("League teams:", total_teams)
print("Players with fantasy points:", len(player_points))

missing = []

for player_id in player_teams:

    if player_id not in player_points:
        missing.append(player_id)

print("Roster players missing points:", len(missing))

if missing:
    print()
    print("WARNING: Some roster players are missing fantasy points.")

else:
    print()
    print("SUCCESS: Every rostered player has fantasy points.")

print()
print("Created roster_share.json")
