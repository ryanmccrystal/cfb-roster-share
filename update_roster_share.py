import requests
import json
import time
import os
from datetime import datetime, timezone

LEAGUE_ID = "gpn5biw5mrzg1jwn"

OUTPUT_FILE = "roster_share.json"

MAX_WEEKS = 14

roster_url = "https://www.fantrax.com/fxea/general/getTeamRosters"
player_url = "https://www.fantrax.com/fxea/general/getPlayerIds"


# --------------------------------------------------
# Get Fantrax player information
# --------------------------------------------------

player_response = requests.get(
    player_url,
    params={"sport": "CFB"},
    timeout=30
)

player_response.raise_for_status()

player_data = player_response.json()

print("Player/team entries:", len(player_data))


# --------------------------------------------------
# Load existing JSON
# --------------------------------------------------

if os.path.exists(OUTPUT_FILE):

    with open(OUTPUT_FILE, "r") as f:
        output = json.load(f)

    print()
    print("Existing roster_share.json found.")

else:

    output = {
        "last_updated": None,
        "league_teams": 0,
        "weeks": {}
    }

    print()
    print("No existing roster_share.json found.")


# --------------------------------------------------
# Convert old single-week format if necessary
# --------------------------------------------------

if "weeks" not in output:

    print()
    print("Converting existing single-week format...")

    old_period = str(output.get("period", 1))

    old_week = {
        "league_teams": output.get("league_teams", 0),
        "players": output.get("players", []),
        "last_updated": output.get(
            "last_updated",
            datetime.now(timezone.utc).isoformat()
        )
    }

    output["weeks"] = {
        old_period: old_week
    }

    output.pop("period", None)
    output.pop("players", None)

    print(
        f"Converted existing data to Week {old_period}."
    )


# --------------------------------------------------
# Function to retrieve one period
# --------------------------------------------------

def get_week_data(period):

    print()
    print("=" * 60)
    print(f"CHECKING WEEK {period}")
    print("=" * 60)


    # ----------------------------------------------
    # Get rosters for this period
    # ----------------------------------------------

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
    # Count roster shares
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


    print("Unique rostered players:", len(player_teams))


    # ----------------------------------------------
    # Get period-specific fantasy points
    # ----------------------------------------------

    player_points = {}

    successful = 0
    failed = 0
    hidden = 0


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


            # --------------------------------------
            # Check for hidden future-period roster
            # --------------------------------------

            message = (
                team_data
                .get("miscData", {})
                .get("aboveTableMessage", "")
            )


            if "hidden" in message.lower():

                hidden += 1

                continue


            # --------------------------------------
            # Extract player fantasy points
            # --------------------------------------

            for table in team_data.get("tables", []):

                for row in table.get("rows", []):

                    scorer = row.get("scorer", {})

                    player_id = scorer.get("scorerId")
                    name = scorer.get("name")


                    if not player_id or not name:
                        continue


                    cells = row.get("cells", [])


                    if len(cells) <= 1:
                        continue


                    points_text = cells[1].get("content")


                    try:
                        points = float(points_text)

                    except (TypeError, ValueError):

                        continue


                    if player_id not in player_points:

                        player_points[player_id] = points


        except Exception as e:

            failed += 1

            print(
                f"ERROR on team {team_id}: {e}"
            )


        time.sleep(0.15)


    print()
    print("Teams successfully queried:", successful)
    print("Teams failed:", failed)
    print("Hidden future rosters:", hidden)
    print("Players with fantasy points:", len(player_points))


    # ----------------------------------------------
    # If Fantrax is hiding the entire period,
    # don't save it.
    # ----------------------------------------------

    if hidden == len(rosters):

        print()
        print(f"Week {period}: NOT AVAILABLE")

        return None


    # ----------------------------------------------
    # Safety check
    # ----------------------------------------------

    missing_points = []

    for player_id in player_teams:

        if player_id not in player_points:

            missing_points.append(player_id)


    print()
    print(
        "Roster players missing points:",
        len(missing_points)
    )


    if missing_points:

        print()
        print("WARNING:")
        print(
            "Not saving this week because some "
            "rostered players are missing fantasy points."
        )

        return None


    # ----------------------------------------------
    # Build player results
    # ----------------------------------------------

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


    players.sort(
        key=lambda x: (
            -x["Roster Share"],
            x["Player"]
        )
    )


    return {
        "league_teams": total_teams,
        "players": players,
        "last_updated": datetime.now(
            timezone.utc
        ).isoformat()
    }


# --------------------------------------------------
# Make sure weeks exists
# --------------------------------------------------

if "weeks" not in output:

    output["weeks"] = {}


# --------------------------------------------------
# Determine the next week to collect
# --------------------------------------------------

saved_weeks = set(output["weeks"].keys())

print()
print(
    "Already saved weeks:",
    sorted(saved_weeks, key=int)
)


next_week = 1

while str(next_week) in output["weeks"]:

    next_week += 1


print(
    "Next week to check:",
    next_week
)


# --------------------------------------------------
# Check the next unsaved week
# --------------------------------------------------

if next_week <= MAX_WEEKS:

    week_data = get_week_data(next_week)


    if week_data is not None:

        output["weeks"][str(next_week)] = week_data

        print()
        print(
            f"SUCCESS: Week {next_week} "
            "was added to the dataset."
        )

    else:

        print()
        print(
            f"Week {next_week} is not available yet."
        )

else:

    print()
    print("All 14 weeks have been collected.")


# --------------------------------------------------
# Update overall metadata
# --------------------------------------------------

output["last_updated"] = datetime.now(
    timezone.utc
).isoformat()


if output["weeks"]:

    first_week_key = sorted(
        output["weeks"].keys(),
        key=int
    )[0]

    output["league_teams"] = (
        output["weeks"][first_week_key]["league_teams"]
    )


# --------------------------------------------------
# Write JSON
# --------------------------------------------------

with open(OUTPUT_FILE, "w") as f:

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
print("FINAL DATASET")
print("=" * 60)


print(
    "Weeks saved:",
    sorted(
        output["weeks"].keys(),
        key=int
    )
)


print(
    "League teams:",
    output["league_teams"]
)


for week in sorted(
    output["weeks"].keys(),
    key=int
):

    data = output["weeks"][week]

    print(
        f"Week {week}: "
        f"{len(data['players'])} players | "
        f"{data['league_teams']} teams"
    )


print()
print("Created:", OUTPUT_FILE)
