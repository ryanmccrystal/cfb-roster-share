import requests
import json
from datetime import datetime, timezone


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
    params={
        "sport": "CFB"
    },
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

    for roster_item in fantasy_team["rosterItems"]:

        player_id = roster_item["id"]

        if player_id not in player_teams:
            player_teams[player_id] = set()

        player_teams[player_id].add(fantasy_team_id)


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
        "Roster Share": round(roster_share, 1)
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
# Create JSON file
# --------------------------------------------------

output = {
    "last_updated": datetime.now(timezone.utc).isoformat(),
    "period": PERIOD,
    "league_teams": total_teams,
    "players": players
}


with open("roster_share.json", "w") as f:
    json.dump(output, f, indent=2)


print()
print("Created roster_share.json")
print("Players:", len(players))
print("League teams:", total_teams)
