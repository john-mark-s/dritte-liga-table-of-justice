import re
import os
import pandas as pd
from ..utils.config import config
  
class GenerateClassicStandings:  
    @staticmethod  
    def calculate_points_per_spieltag(csv_folder):  
        
        # Filter and sort CSV files  
        spieltag_files = [
            f for f in os.listdir(csv_folder)
            if (
            f.endswith('.csv')
            and not f.endswith('_xg.csv')
            and not f.endswith('_xp.csv')
            and ('soccerway' in f or 'footystats' in f)
            )
        ]
          
        print(f"Filtered and sorted files: {spieltag_files}")  
          
        team_points = {}  
          
        for idx, file in enumerate(spieltag_files, start=1):  
            try:  
                file_path = os.path.join(csv_folder, file)  
                print(f"Processing file: {file_path}")  
                df = pd.read_csv(file_path)  
  
                points_this_spieltag = {}  
                  
                # Iterate over each row in the DataFrame  
                for _, row in df.iterrows():  
                    # Home team and Away team  
                    home, away = row['home_team'], row['away_team']  
                    home_goals, away_goals = row['home_goals'], row['away_goals']  
                      
                    print(f"Match: {home} vs {away} | Score: {home_goals}-{away_goals}")  
                      
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
                        team_points[team].append(None)
                            
            except Exception as e:  
                print(f"Error processing file {file}: {e}")  
                continue  
  
        # Create DataFrame  
        df_points = pd.DataFrame.from_dict(team_points, orient='index')  
        df_points.columns = [f'points_spieltag{i}' for i in range(1, len(spieltag_files) + 1)]  
        df_points.index.name = 'Team'  
        df_points.reset_index(inplace=True)  
          
        # Save to CSV  
        output_path = os.path.join(csv_folder, 'points_per_spieltag.csv')  
        df_points.to_csv(output_path, index=False)  
        print(f"Standings saved to {output_path}")  
          
        return df_points  
    
    def calculate_classic_standings(self, csv_folder):
        csv_folder = config.FOOTYSTATS_DIR

        # Load the points per spieltag data  
        df_points = self.calculate_points_per_spieltag(csv_folder)

        # Extract spieltag numbers from columns
        spieltag_columns = [col for col in df_points.columns if col.startswith('points_spieltag')]
        spieltags = sorted(
            [int(col.split('points_spieltag')[1]) for col in spieltag_columns]
        )
        spieltag_columns_sorted = [f'points_spieltag{i}' for i in spieltags]

        # Rename columns to match 'spieltag-{n}' format
        rename_map = {f'points_spieltag{i}': f'spieltag-{i}' for i in spieltags}
        df_points = df_points.rename(columns=rename_map)

        spieltag_cols = [f'spieltag-{i}' for i in spieltags]

        # Add total_points column at the end
        df_points['total_points'] = df_points[spieltag_cols].sum(axis=1, skipna=True)

        # Sort by total_points descending
        df_points = df_points.sort_values('total_points', ascending=False).reset_index(drop=True)

        # Reorder columns: Team, spieltag-1, ..., spieltag-N, total_points
        final_columns = ['Team'] + spieltag_cols + ['total_points']
        df_final = df_points[final_columns]

        # Save to CSV (like season_xp)
        output_filename = 'season_classic_table.csv'
        output_path = os.path.join(csv_folder, output_filename)
        df_final.to_csv(output_path, index=False)

        print(f"Classic season standings saved to {output_path}")
