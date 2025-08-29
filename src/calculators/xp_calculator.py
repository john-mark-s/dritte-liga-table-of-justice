"""
Expected Points (xP) calculator using Poisson distribution
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Tuple, Optional, List
from scipy.stats import poisson
import re

from ..utils.config import config
from ..utils.logger import get_logger

class XPCalculator:
    """Calculator for Expected Points based on Expected Goals"""
    
    def __init__(self, max_goals: int = 10):
        self.max_goals = max_goals
        self.logger = get_logger('calculators.xp')
    
    def compute_xp(self, xg_home: float, xg_away: float) -> Tuple[float, float]:
        """
        Calculate expected points (xP) for both teams based on their xG values
        
        Args:
            xg_home: Expected goals for home team
            xg_away: Expected goals for away team
            
        Returns:
            Tuple of (home_xP, away_xP)
        """
        if pd.isna(xg_home) or pd.isna(xg_away):
            return np.nan, np.nan
        
        try:
            xp_home, xp_away, p_draw = 0.0, 0.0, 0.0
            
            for home_goals in range(self.max_goals + 1):
                p_home_goals = poisson.pmf(home_goals, xg_home)
                
                for away_goals in range(self.max_goals + 1):
                    p_away_goals = poisson.pmf(away_goals, xg_away)
                    p_scoreline = p_home_goals * p_away_goals
                    
                    if home_goals > away_goals:
                        xp_home += p_scoreline * 3  # Home win
                    elif home_goals < away_goals:
                        xp_away += p_scoreline * 3  # Away win
                    else:
                        p_draw += p_scoreline  # Draw
            
            # Add draw points
            xp_home += p_draw
            xp_away += p_draw
            
            return round(xp_home, 3), round(xp_away, 3)
            
        except Exception as e:
            self.logger.error(f"❌ Error calculating xP: {e}")
            return np.nan, np.nan
    
    def calculate_match_probabilities(self, xg_home: float, xg_away: float) -> Tuple[float, float, float]:
        """
        Calculate win/draw/loss probabilities
        
        Args:
            xg_home: Expected goals for home team
            xg_away: Expected goals for away team
            
        Returns:
            Tuple of (home_win_prob, draw_prob, away_win_prob)
        """
        if pd.isna(xg_home) or pd.isna(xg_away):
            return np.nan, np.nan, np.nan
        
        try:
            p_home_win, p_draw, p_away_win = 0.0, 0.0, 0.0
            
            for home_goals in range(self.max_goals + 1):
                p_home_goals = poisson.pmf(home_goals, xg_home)
                
                for away_goals in range(self.max_goals + 1):
                    p_away_goals = poisson.pmf(away_goals, xg_away)
                    p_scoreline = p_home_goals * p_away_goals
                    
                    if home_goals > away_goals:
                        p_home_win += p_scoreline
                    elif home_goals < away_goals:
                        p_away_win += p_scoreline
                    else:
                        p_draw += p_scoreline
            
            return (round(p_home_win, 3), 
                   round(p_draw, 3), 
                   round(p_away_win, 3))
            
        except Exception as e:
            self.logger.error(f"❌ Error calculating probabilities: {e}")
            return np.nan, np.nan, np.nan
    
    def process_matches_file(self, file_path: Path) -> Optional[pd.DataFrame]:
        """
        Process a matches CSV file and add xP calculations
        
        Args:
            file_path: Path to CSV file with xG data
            
        Returns:
            DataFrame with xP data added, or None if failed
        """
        try:
            self.logger.info(f"📊 Processing matches: {file_path.name}")
            
            df = pd.read_csv(file_path)
            
            # Check for required columns (try different naming conventions)
            xg_columns = self._find_xg_columns(df.columns)
            if not xg_columns:
                self.logger.warning(f"⚠️ No xG columns found in {file_path.name}")
                return None
            
            home_xg_col, away_xg_col = xg_columns
            
            # Skip if already processed
            if 'home_xP' in df.columns and 'away_xP' in df.columns:
                self.logger.info(f"ℹ️ File already has xP columns, updating")
            
            # Add new columns
            df['home_xP'] = 0.0
            df['away_xP'] = 0.0
            df['home_win_prob'] = 0.0
            df['draw_prob'] = 0.0
            df['away_win_prob'] = 0.0
            
            # Calculate xP for each match
            for idx, row in df.iterrows():
                home_xg = row[home_xg_col]
                away_xg = row[away_xg_col]
                
                # Calculate xP
                home_xp, away_xp = self.compute_xp(home_xg, away_xg)
                df.at[idx, 'home_xP'] = home_xp
                df.at[idx, 'away_xP'] = away_xp
                
                # Calculate probabilities
                home_win_prob, draw_prob, away_win_prob = self.calculate_match_probabilities(home_xg, away_xg)
                df.at[idx, 'home_win_prob'] = home_win_prob
                df.at[idx, 'draw_prob'] = draw_prob
                df.at[idx, 'away_win_prob'] = away_win_prob
            
            self.logger.info(f"✅ Added xP calculations for {len(df)} matches")
            return df
            
        except Exception as e:
            self.logger.error(f"❌ Error processing {file_path}: {e}")
            return None
    
    def _find_xg_columns(self, columns) -> Optional[Tuple[str, str]]:
        """Find xG columns with flexible naming"""
        home_xg_candidates = ['home_xG', 'Home_xG', 'xG_home', 'xg_home']
        away_xg_candidates = ['away_xG', 'Away_xG', 'xG_away', 'xg_away']
        
        home_xg_col = None
        away_xg_col = None
        
        for col in columns:
            if col in home_xg_candidates:
                home_xg_col = col
            elif col in away_xg_candidates:
                away_xg_col = col
        
        if home_xg_col and away_xg_col:
            return home_xg_col, away_xg_col
        
        return None
    
    def batch_process_directory(self, directory: Path) -> None:
        """
        Process all CSV files in a directory that have xG data
        
        Args:
            directory: Directory containing CSV files
        """
        if not directory.exists():
            self.logger.warning(f"⚠️ Directory does not exist: {directory}")
            return
        
        self.logger.info(f"🔄 Batch processing directory: {directory}")
        
        # Find CSV files with xG data
        csv_files = []
        for pattern in ["*xg*.csv", "*spieltag*.csv", "*.csv"]:
            potential_files = list(directory.glob(pattern))
            for f in potential_files:
                if self._has_xg_data(f) and f not in csv_files:
                    csv_files.append(f)
        
        if not csv_files:
            self.logger.warning(f"⚠️ No CSV files with xG data found in {directory}")
            return
        
        processed_count = 0
        for csv_file in csv_files:
            df = self.process_matches_file(csv_file)
            
            if df is not None:
                # Create output filename
                if "_xp" not in csv_file.stem:
                    output_file = csv_file.parent / f"{csv_file.stem}_xp.csv"
                else:
                    output_file = csv_file  # Overwrite if already has _xp suffix
                
                try:
                    df.to_csv(output_file, index=False)
                    self.logger.info(f"💾 Saved: {output_file.name}")
                    processed_count += 1
                except Exception as e:
                    self.logger.error(f"❌ Error saving {output_file}: {e}")
        
        self.logger.info(f"✅ Processed {processed_count}/{len(csv_files)} files")
    
    def _has_xg_data(self, file_path: Path) -> bool:
        """Check if CSV file has xG data"""
        try:
            df = pd.read_csv(file_path, nrows=1)  # Just read header
            xg_columns = self._find_xg_columns(df.columns)
            return xg_columns is not None
        except:
            return False


class SeasonXPProcessor:
    """Processor for creating season-wide xP and xG tables"""
    
    def __init__(self):
        self.logger = get_logger('calculators.season_xp')
    
    def create_season_table(self, directory: Path, metric: str = 'xP') -> Optional[pd.DataFrame]:
        """
        Create season table from individual match files
        
        Args:
            directory: Directory containing match files
            metric: 'xP' or 'xG'
            
        Returns:
            Season table DataFrame or None if failed
        """
        self.logger.info(f"📊 Creating season {metric} table from {directory}")
        
        # Find relevant files - look for files with xp suffix
        files = list(directory.glob("*xp.csv"))
        
        if not files:
            # Fallback: look for any CSV files with required data
            all_files = list(directory.glob("*.csv"))
            files = [f for f in all_files if self._has_required_columns(f, metric)]
        
        if not files:
            self.logger.warning(f"⚠️ No files with {metric} data found in {directory}")
            return None
        
        spieltag_data = {}
        all_teams = set()
        
        for file_path in sorted(files):
            spieltag = self._extract_spieltag_from_filename(file_path.name)
            if spieltag is None:
                continue
            
            self.logger.debug(f"Processing Spieltag {spieltag}: {file_path.name}")
            
            try:
                df = pd.read_csv(file_path)
                team_values = self._extract_team_values(df, metric)
                
                if team_values:
                    spieltag_data[spieltag] = team_values
                    all_teams.update(team_values.keys())
                    
            except Exception as e:
                self.logger.error(f"❌ Error processing {file_path.name}: {e}")
        
        if not spieltag_data:
            self.logger.warning(f"⚠️ No {metric} data extracted")
            return None
        
        # Create season DataFrame
        season_df = self._build_season_dataframe(spieltag_data, sorted(all_teams), metric)
        
        self.logger.info(f"✅ Created season {metric} table: {season_df.shape[0]} teams, {len(spieltag_data)} spieltags")
        return season_df
    
    def _has_required_columns(self, file_path: Path, metric: str) -> bool:
        """Check if file has required columns for the metric"""
        try:
            df = pd.read_csv(file_path, nrows=1)
            if metric == 'xP':
                return any(col in df.columns for col in ['home_xP', 'away_xP'])
            elif metric == 'xG':
                return any(col in df.columns for col in ['home_xG', 'away_xG', 'Home_xG', 'Away_xG'])
            return False
        except:
            return False
    
    def _extract_spieltag_from_filename(self, filename: str) -> Optional[int]:
        """Extract spieltag number from filename with flexible patterns"""
        patterns = [
            r'spieltag[-_](\d+)',  # spieltag-1 or spieltag_1
            r'(\d+)[-_]spieltag',  # 1-spieltag or 1_spieltag
            r'round[-_](\d+)',     # round-1 or round_1
            r'matchday[-_](\d+)',  # matchday-1 or matchday_1
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename.lower())
            if match:
                return int(match.group(1))
        
        return None
    
    def _extract_team_values(self, df: pd.DataFrame, metric: str) -> Dict[str, float]:
        """Extract team values from match DataFrame with flexible column names"""
        team_values = {}
        
        # Find team name columns
        team_cols = self._find_team_columns(df.columns)
        if not team_cols:
            return team_values
        
        home_team_col, away_team_col = team_cols
        
        # Find metric columns
        metric_cols = self._find_metric_columns(df.columns, metric)
        if not metric_cols:
            return team_values
        
        home_metric_col, away_metric_col = metric_cols
        
        for _, row in df.iterrows():
            home_team = row.get(home_team_col)
            away_team = row.get(away_team_col)
            home_value = row.get(home_metric_col)
            away_value = row.get(away_metric_col)
            
            if all(pd.notna([home_team, away_team, home_value, away_value])):
                team_values[home_team] = float(home_value)
                team_values[away_team] = float(away_value)
        
        return team_values
    
    def _find_team_columns(self, columns) -> Optional[Tuple[str, str]]:
        """Find team name columns"""
        home_candidates = ['home_team', 'Home_Team', 'HomeTeam', 'home']
        away_candidates = ['away_team', 'Away_Team', 'AwayTeam', 'away']
        
        home_col = None
        away_col = None
        
        for col in columns:
            if col in home_candidates:
                home_col = col
            elif col in away_candidates:
                away_col = col
        
        if home_col and away_col:
            return home_col, away_col
        
        return None
    
    def _find_metric_columns(self, columns, metric: str) -> Optional[Tuple[str, str]]:
        """Find metric columns"""
        if metric == 'xP':
            home_candidates = ['home_xP', 'Home_xP', 'xP_home']
            away_candidates = ['away_xP', 'Away_xP', 'xP_away']
        elif metric == 'xG':
            home_candidates = ['home_xG', 'Home_xG', 'xG_home']
            away_candidates = ['away_xG', 'Away_xG', 'xG_away']
        else:
            return None
        
        home_col = None
        away_col = None
        
        for col in columns:
            if col in home_candidates:
                home_col = col
            elif col in away_candidates:
                away_col = col
        
        if home_col and away_col:
            return home_col, away_col
        
        return None
    
    def _build_season_dataframe(self, spieltag_data: Dict[int, Dict[str, float]], 
                               teams: List[str], metric: str) -> pd.DataFrame:
        """Build season DataFrame from spieltag data"""
        spieltags = sorted(spieltag_data.keys())
        columns = ['Team'] + [f'spieltag-{st}' for st in spieltags]
        
        data = []
        for team in teams:
            row = [team]
            for spieltag in spieltags:
                value = spieltag_data.get(spieltag, {}).get(team, np.nan)
                row.append(round(value, 3) if pd.notna(value) else np.nan)
            data.append(row)
        
        df = pd.DataFrame(data, columns=columns)
        
        # Add total column
        spieltag_cols = [col for col in df.columns if col.startswith('spieltag-')]
        df[f'Total_{metric}'] = df[spieltag_cols].sum(axis=1, skipna=True).round(3)
        
        # Sort by total
        df = df.sort_values(f'Total_{metric}', ascending=False).reset_index(drop=True)
        
        # Reorder columns
        final_columns = (['Team'] + 
                        sorted(spieltag_cols, key=lambda x: int(x.split('-')[1])) + 
                        [f'Total_{metric}'])
        
        return df[final_columns]
    
    def save_season_table(self, df: pd.DataFrame, directory: Path, metric: str) -> bool:
        """Save season table to CSV"""
        try:
            filename = f"season_{metric.lower()}.csv"
            output_path = directory / filename
            
            df.to_csv(output_path, index=False)
            self.logger.info(f"💾 Saved season {metric} table: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error saving season {metric} table: {e}")
            return False
    
    def process_directory(self, directory: Path) -> None:
        """Process directory for both xP and xG season tables"""
        for metric in ['xP', 'xG']:
            season_df = self.create_season_table(directory, metric)
            if season_df is not None:
                self.save_season_table(season_df, directory, metric)


def main():
    """Main function for running calculators"""
    logger = get_logger('calculators.main')
    
    # Ensure directories exist
    config.ensure_directories()
    
    # Initialize calculators
    xp_calc = XPCalculator()
    season_proc = SeasonXPProcessor()
    
    # Process both data sources
    for source in config.ENABLED_SOURCES:
        source_dir = getattr(config, f"{source.upper()}_DIR")
        
        if source_dir.exists():
            logger.info(f"🔄 Processing {source} data...")
            
            # Calculate xP for individual matches
            xp_calc.batch_process_directory(source_dir)
            
            # Create season tables
            season_proc.process_directory(source_dir)
            
        else:
            logger.warning(f"⚠️ Directory not found: {source_dir}")

if __name__ == "__main__":
    main()