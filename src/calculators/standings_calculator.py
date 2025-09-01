import os
import pandas as pd

def calculate_points_per_spieltag(csv_folder):
    spieltag_files = sorted([f for f in os.listdir(csv_folder) if f.endswith('.csv')])
    team_points = {}

    for idx, file in enumerate(spieltag_files, start=1):
        df = pd.read_csv(os.path.join(csv_folder, file))
        points_this_spieltag = {}

        for _, row in df.iterrows():
            # Home team
            home, away = row['home_team'], row['away_team']
            home_goals, away_goals = row['home_goals'], row['away_goals']

            if home_goals > away_goals:
                points_this_spieltag[home] = points_this_spieltag.get(home, 0) + 3
                points_this_spieltag[away] = points_this_spieltag.get(away, 0) + 0
            elif home_goals == away_goals:
                points_this_spieltag[home] = points_this_spieltag.get(home, 0) + 1
                points_this_spieltag[away] = points_this_spieltag.get(away, 0) + 1
            else:
                points_this_spieltag[home] = points_this_spieltag.get(home, 0) + 0
                points_this_spieltag[away] = points_this_spieltag.get(away, 0) + 3

        # Add points for this spieltag to each team
        for team in points_this_spieltag:
            if team not in team_points:
                team_points[team] = []
            team_points[team].append(points_this_spieltag[team])

        # Ensure all teams have a value for this spieltag (even if 0)
        for team in team_points:
            if len(team_points[team]) < idx:
                team_points[team].append(0)

    # Print results
    header = ['Team'] + [f'points_spieltag{i}' for i in range(1, len(spieltag_files)+1)]
    print(', '.join(header))
    for team, points in team_points.items():
        print(f"{team}, " + ', '.join(str(p) for p in points))

calculate_points_per_spieltag('data/soccerway')