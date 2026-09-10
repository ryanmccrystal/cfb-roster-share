import requests
import json
import time
from datetime import datetime, timezone

LEAGUE_ID = "gpn5biw5mrzg1jwn"

# Number of weeks we eventually want
MAX_PERIOD = 14

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
# Function to retrieve one week's data
# --------------------------------------------------

def get_week_data(period):

    print()
    print("=" * 60)
    print(f"PROCESSING WEEK {period}")
    print("=" * 60)

    # ----------------------------------------------
    # Get rosters for this period
    # ----------------------------------------------

    roster_url = "https://www.fantrax.com/fxea/general/getTeamRosters"

    roster_response = requests.get(
        roster_url,
        params={
            "leagueId": LEAGUE_ID,
            "period": period
        },
        timeout=30
    )

    roster_response.raise_for_status()

    roster_data = roster_response.json()
    rosters = roster_data["rosters"]

    print("Fantasy teams:", len(rosters))

    # ----------------------------------------------
    # Count roster share
    # ----------------------------------------------

    player_teams = {}

    for fantasy_team_id, fantasy_team in rosters.items():

        for roster_item in fantasy_team.get("rosterItems", []):

            player_id = roster_item.get("id")

            if not player_id:
                continue

            if player_id not in player_teams:
                player_teams[player_id] = set()

            player_teams[player_id].add(fantasy_team_id)

    print(
        "Unique players on rosters:",
        len(player_teams)
    )

    # ----------------------------------------------
    # Get fantasy points
    # ----------------------------------------------

    player_points = {}

    successful = 0
    hidden_rosters = 0
    failed = 0

    for count, team_id in enumerate(
        rosters.keys(),
        start=1
    ):

        payload = {
            "msgs": [
                {
                    "method": "getTeamRosterInfo",
                    "data": {
                        "leagueId": LEAGUE_ID,
                        "period": str(period),
                        "teamId": team_id,
                        "scoringCategoryType": "5",
                        "statsType": "2"
                    }
                }
            ]
        }

        try:

            response = requests.post(
                "https://www.fantrax.com/fxpa/req",
                params={"leagueId": LEAGUE_ID},
                json=payload,
                timeout=60
            )

            response.raise_for_status()

            response_data = response.json()

            team_data = response_data[
                "responses"
            ][0]["data"]

            successful += 1

            # --------------------------------------
            # Check whether Fantrax is hiding roster
            # --------------------------------------

            misc_data = team_data.get(
                "miscData",
                {}
            )

            above_table_message = misc_data.get(
                "aboveTableMessage",
                ""
            )

            if "rosters of teams you do not own" in \
               above_table_message:

                hidden_rosters += 1

            # --------------------------------------
            # Extract players
            # --------------------------------------

            for table in team_data.get(
                "tables",
                []
            ):

                for row in table.get(
                    "rows",
                    []
                ):

                    scorer = row.get(
                        "scorer",
                        {}
                    )

                    player_id = scorer.get(
                        "scorerId"
                    )

                    name = scorer.get(
                        "name"
                    )

                    if not player_id or not name:
                        continue

                    cells = row.get(
                        "cells",
                        []
                    )

                    # Cell 1 = Fantasy Points
                    if len(cells) <= 1:
                        continue

                    points_text = cells[1].get(
                        "content"
                    )

                    try:

                        points = float(
                            points_text
                        )

                    except (
                        TypeError,
                        ValueError
                    ):

                        continue

                    if player_id not in player_points:

                        player_points[player_id] = points

            print(
                f"{count:2}/{len(rosters)} "
                f"| players with points: "
                f"{len(player_points)}"
            )

        except Exception as e:

            failed += 1

            print(
                f"{count:2}/{len(rosters)} "
                f"| ERROR: {e}"
            )

        time.sleep(0.15)

    # ----------------------------------------------
    # Check whether this period is available
    # ----------------------------------------------

    print()
    print("Successful team requests:", successful)
    print("Failed requests:", failed)
    print("Hidden future rosters:", hidden_rosters)
    print("Players with fantasy points:", len(player_points))

    # If every roster is hidden, this is a future
    # period and we should NOT save it as usable data.
    if hidden_rosters == len(rosters):

        print()
        print(
            f"Week {period} is not available yet."
        )

        return None

    # ----------------------------------------------
    # Build player results
    # ----------------------------------------------

    total_teams = len(rosters)

    players = []

    for player_id, teams in player_teams.items():

        info = player_data.get(
            player_id,
            {}
        )

        if not info.get("name"):
            continue

        teams_rostered = len(teams)

        roster_share = (
            teams_rostered /
            total_teams
        ) * 100

        players.append({
            "Player": info.get(
                "name",
                ""
            ),
            "Team": info.get(
                "team",
                ""
            ),
            "Pos": info.get(
                "position",
                ""
            ),
            "Teams": teams_rostered,
            "League Teams": total_teams,
            "Roster Share": round(
                roster_share,
                1
            ),
            "Fantasy Points": player_points.get(
                player_id
            )
        })

    # ----------------------------------------------
    # Sort by roster share
    # ----------------------------------------------

    players.sort(
        key=lambda x: (
            -x["Roster Share"],
            x["Player"]
        )
    )

    return {
        "league_teams": total_teams,
        "players": players
    }


# --------------------------------------------------
# Retrieve available weeks
# --------------------------------------------------

weeks = {}

for period in range(
    1,
    MAX_PERIOD + 1
):

    week_data = get_week_data(
        period
    )

    if week_data is not None:

        weeks[str(period)] = week_data

    else:

        print(
            f"Skipping Week {period}."
        )

    print()


# --------------------------------------------------
# Create final JSON
# --------------------------------------------------

output = {
    "last_updated": datetime.now(
        timezone.utc
    ).isoformat(),

    "league_teams": 73,

    "weeks": weeks
}

with open(
    "roster_share.json",
    "w"
) as f:

    json.dump(
        output,
        f,
        indent=2
    )


# --------------------------------------------------
# Final summary
# --------------------------------------------------

print()
print("=" * 60)
print("FINAL SUMMARY")
print("=" * 60)

print(
    "Weeks available:",
    ", ".join(
        weeks.keys()
    )
)

for week, data in weeks.items():

    print(
        f"Week {week}: "
        f"{len(data['players'])} players"
    )

print()
print(
    "Created roster_share.json"
)
