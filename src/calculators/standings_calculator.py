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
        
        csv_folder = config.SOCCERWAY_DIR
        export_folder2 = config.FOOTYSTATS_DIR

        # Load the points per spieltag data  
        df_points = self.calculate_points_per_spieltag(csv_folder)
        
        # Extract spieltag numbers from filenames in the folder
        spieltag_files = [
            f for f in os.listdir(csv_folder)
            if f.endswith('.csv') and not f.endswith('_xg.csv') and not f.endswith('_xp.csv')
        ]
        spieltag_numbers = []
        for f in spieltag_files:
            match = re.search(r'spieltag-(\d+)', f)
            if match:
                spieltag_numbers.append(int(match.group(1)))
        if spieltag_numbers:
            latest_spieltag = max(spieltag_numbers)
        else:
            latest_spieltag = len(spieltag_columns)
            
        spieltag_columns = [col for col in df_points.columns if col.startswith('points_spieltag')]
        
        # Calculate total points up to the latest spieltag  
        df_points['Total Points'] = df_points[spieltag_columns].sum(axis=1)  
          
        # Sort by total points in descending order  
        df_standings = df_points[['Team', 'Total Points']].sort_values(by='Total Points', ascending=False)  
          
        # Save the standings to a CSV file  
        output_filename = f'classic_standings_spieltag-{latest_spieltag}.csv'  
        output_path = os.path.join(csv_folder, output_filename)  
        df_standings.to_csv(output_path, index=False)
        
        output_filename2 = f'classic_standings_spieltag-{latest_spieltag}.csv'  
        output_path2 = os.path.join(export_folder2, output_filename2)
        df_standings.to_csv(output_path2, index=False)

        print(f"Classic standings saved to {output_path}")