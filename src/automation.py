"""
Weekly automation script for 3. Liga Table of Justice
Runs the complete pipeline: fixtures -> xG -> xP -> season table -> dashboard
"""
import os
import sys
import time
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

from .scrapers.footystats_scraper import FootyStatsScraper, FootyStatsXGScraper
from .scrapers.soccerway_scraper import SoccerwayFixturesScraper, SoccerwayXGScraper
from .calculators.xp_calculator import XPCalculator, SeasonXPProcessor
from .calculators.standings_calculator import GenerateClassicStandings
from .utils.config import config
from .utils.logger import get_logger

class WeeklyUpdateManager:
    """Manages the complete weekly update pipeline"""
    
    def __init__(self):
        self.logger = get_logger('automation')
        
        # Initialize components
        self.fs_scraper = FootyStatsScraper()
        self.fs_xg_scraper = FootyStatsXGScraper()
        self.sw_scraper = SoccerwayFixturesScraper()
        self.sw_xg_scraper = SoccerwayXGScraper()
        self.xp_calculator = XPCalculator()
        self.season_processor = SeasonXPProcessor()
        self.standard_standings = GenerateClassicStandings
        
        # Ensure directories exist
        config.ensure_directories()
    
    def get_current_spieltag(self) -> Optional[int]:
        """
        Determine the current Spieltag based on today's date
        
        Returns:
            Current spieltag number or None if no active spieltag
        """
        now = datetime.now()
        current_spieltag = None
        
        for spieltag_number, (_, match_datetime_str) in config.SPIELTAG_MAP.items():
            try:
                match_datetime = datetime.strptime(match_datetime_str, "%Y-%m-%d %H:%M:%S")
                if now >= match_datetime:
                    current_spieltag = spieltag_number
                else:
                    break
            except ValueError as e:
                self.logger.warning(f"⚠️ Invalid date format for Spieltag {spieltag_number}: {e}")
                continue
        
        return current_spieltag
    
    def get_spieltags_to_process(self, lookback_days: int = 7) -> List[int]:
        """
        Get list of spieltags that need processing based on lookback period
        
        Args:
            lookback_days: How many days to look back for matches
            
        Returns:
            List of spieltag numbers to process
        """
        now = datetime.now()
        cutoff_date = now - timedelta(days=lookback_days)
        spieltags_to_process = []
        
        for spieltag_number, (_, match_datetime_str) in config.SPIELTAG_MAP.items():
            try:
                match_datetime = datetime.strptime(match_datetime_str, "%Y-%m-%d %H:%M:%S")
                
                # Include if match is within lookback period and not in future
                if cutoff_date <= match_datetime <= now:
                    # Check if we already have processed data
                    if not self._is_spieltag_processed(spieltag_number):
                        spieltags_to_process.append(spieltag_number)
                        
            except ValueError:
                continue
        
        return sorted(spieltags_to_process)
    
    def _is_spieltag_processed(self, spieltag: int) -> bool:
        """Check if a spieltag has already been fully processed"""
        for source in config.ENABLED_SOURCES:
            source_dir = getattr(config, f"{source.upper()}_DIR")
            
            # Check for xP file (final step)
            xp_pattern = f"*spieltag-{spieltag}_xp.csv"
            xp_files = list(source_dir.glob(xp_pattern))
            
            if not xp_files:
                return False
        
        return True
    
    def step1_scrape_fixtures(self, spieltag: int) -> bool:
        """
        Step 1: Scrape fixtures for the given Spieltag
        
        Returns:
            True if at least one source succeeded
        """
        self.logger.info(f"🏈 STEP 1: Scraping fixtures for Spieltag {spieltag}")
        success = False
        
        for source in config.ENABLED_SOURCES:
            try:
                self.logger.info(f"--- {source.title()} fixtures ---")
                
                if source == 'footystats':
                    fixtures = self.fs_scraper.scrape_fixtures(spieltag)
                    if fixtures:
                        filepath = self.fs_scraper.save_fixtures_to_csv(fixtures, spieltag)
                        if filepath:
                            success = True
                
                elif source == 'soccerway':
                    fixtures = self.sw_scraper.scrape_fixtures(spieltag)
                    if fixtures:
                        filepath = self.sw_scraper.save_fixtures_to_csv(fixtures, spieltag)
                        if filepath:
                            success = True
                
                # Brief delay between sources
                time.sleep(2)
                
            except Exception as e:
                self.logger.error(f"❌ Error scraping {source} fixtures: {e}")
        
        return success
    
    def step2_scrape_xg(self, spieltag: int) -> bool:
        """
        Step 2: Scrape xG data for fixtures
        
        Returns:
            True if at least one source succeeded
        """
        self.logger.info(f"🎯 STEP 2: Scraping xG data for Spieltag {spieltag}")
        success = False
        
        for source in config.ENABLED_SOURCES:
            try:
                self.logger.info(f"--- {source.title()} xG ---")
                source_dir = getattr(config, f"{source.upper()}_DIR")
                
                # Find fixtures file for this spieltag
                fixtures_pattern = f"*spieltag-{spieltag}.csv"
                fixtures_files = list(source_dir.glob(fixtures_pattern))
                
                if not fixtures_files:
                    self.logger.warning(f"⚠️ No fixtures file found for {source} Spieltag {spieltag}")
                    continue
                
                fixtures_file = fixtures_files[0]
                
                # Check if we already have xG data
                xg_file = fixtures_file.parent / f"{fixtures_file.stem}_xg.csv"
                if xg_file.exists():
                    self.logger.info(f"ℹ️ xG file already exists: {xg_file.name}")
                    success = True
                    continue
                
                # Load fixtures and scrape xG
                df = pd.read_csv(fixtures_file)
                
                if 'stats_link' not in df.columns and 'url' not in df.columns:
                    self.logger.warning(f"⚠️ No match URLs found in {fixtures_file}")
                    continue
                
                # Add xG columns
                df['home_xG'] = None
                df['away_xG'] = None
                
                url_column = 'stats_link' if 'stats_link' in df.columns else 'url'
                
                for idx, row in df.iterrows():
                    url = row.get(url_column)
                    if not url or pd.isna(url):
                        continue

                    self.logger.info(f"Scraping xG for fixture: idx={idx}, home='{row.get('home_team')}', away='{row.get('away_team')}', url='{url}'")

                    try:
                        if source == 'footystats':
                            result = self.fs_xg_scraper.scrape_match_xg(url)
                        elif source == 'soccerway':
                            result = self.sw_xg_scraper.scrape_match_xg(url)
                        else:
                            continue

                        self.logger.info(f"xG result for idx={idx}: {result}")

                        if result:
                            if source == 'footystats':
                                home_team = row['home_team']
                                if home_team.lower().replace(' ', '') in result['team_2_name'].lower().replace(' ', ''):
                                    df.at[idx, 'home_xG'] = result['team_2_xG']
                                    df.at[idx, 'away_xG'] = result['team_1_xG']
                                else:
                                    df.at[idx, 'home_xG'] = result['team_1_xG']
                                    df.at[idx, 'away_xG'] = result['team_2_xG']
                            else:  # soccerway
                                df.at[idx, 'home_xG'] = result['home_xG']
                                df.at[idx, 'away_xG'] = result['away_xG']

                        self.logger.info(f"Fixture after xG: idx={idx}, home='{df.at[idx, 'home_team']}', away='{df.at[idx, 'away_team']}', home_xG='{df.at[idx, 'home_xG']}', away_xG='{df.at[idx, 'away_xG']}'")

                    except Exception as e:
                        self.logger.error(f"❌ Error scraping xG for match {idx + 1}: {e}")

                    time.sleep(2)

                # Log each row before saving
                for idx, row in df.iterrows():
                    self.logger.info(f"Saving row to CSV: idx={idx}, home='{row.get('home_team')}', away='{row.get('away_team')}', home_xG='{row.get('home_xG')}', away_xG='{row.get('away_xG')}'")

                df.to_csv(xg_file, index=False)
                self.logger.info(f"💾 Saved xG data: {xg_file}")
                success = True
                
            except Exception as e:
                self.logger.error(f"❌ Error scraping {source} xG: {e}")
        
        return success
    
    def step3_calculate_xp(self, spieltag: int) -> bool:
        """
        Step 3: Calculate xP from xG data
        
        Returns:
            True if successful
        """
        self.logger.info(f"📊 STEP 3: Calculating xP for Spieltag {spieltag}")
        success = False
        
        for source in config.ENABLED_SOURCES:
            try:
                source_dir = getattr(config, f"{source.upper()}_DIR")
                
                # Find xG file
                xg_pattern = f"*spieltag-{spieltag}_xg.csv"
                xg_files = list(source_dir.glob(xg_pattern))
                
                if not xg_files:
                    self.logger.warning(f"⚠️ No xG file found for {source} Spieltag {spieltag}")
                    continue
                
                xg_file = xg_files[0]
                xp_file = xg_file.parent / f"{xg_file.stem.replace('_xg', '_xp')}.csv"
                
                # Process file
                df = self.xp_calculator.process_matches_file(xg_file)
                if df is not None:
                    df.to_csv(xp_file, index=False)
                    self.logger.info(f"💾 Saved xP data: {xp_file}")
                    success = True
                
            except Exception as e:
                self.logger.error(f"❌ Error calculating xP for {source}: {e}")
        
        return success
    
    def step4_update_season_tables(self) -> bool:
        """
        Step 4: Update season xP and xG tables
        
        Returns:
            True if successful
        """
        self.logger.info("📈 STEP 4: Updating season tables")
        success = False
        
        for source in config.ENABLED_SOURCES:
            try:
                source_dir = getattr(config, f"{source.upper()}_DIR")
                self.season_processor.process_directory(source_dir)
                success = True
                
            except Exception as e:
                self.logger.error(f"❌ Error updating {source} season tables: {e}")
        
        return success
    
    def step5_create_standard_standings(self) -> bool:  
        self.logger.info("STEP 5: Creating standard league standings")  
        success = False  
    
        source_dir = config.SOCCERWAY_DIR  
        try:  
            # Call the method and let it determine the latest spieltag  
            self.standard_standings.calculate_classic_standings(source_dir)  
            success = True  
        except Exception as e:  
            self.logger.error(f"❌ Error creating standard standings for {source_dir}: {e}")  
        
        return success

    def run_pipeline_for_spieltag(self, spieltag: int) -> bool:
        """
        Run the complete pipeline for a specific spieltag
        
        Args:
            spieltag: Spieltag number to process
            
        Returns:
            True if pipeline completed successfully
        """
        self.logger.info(f"🚀 Running pipeline for Spieltag {spieltag}")
        
        steps = [
            ("Scrape Fixtures", lambda: self.step1_scrape_fixtures(spieltag)),
            ("Scrape xG", lambda: self.step2_scrape_xg(spieltag)),
            ("Calculate xP", lambda: self.step3_calculate_xp(spieltag)),
            ("Create Standard Standings", self.step5_create_standard_standings)
        ]
        
        for step_name, step_func in steps:
            self.logger.info(f"\n--- {step_name} ---")
            
            if not step_func():
                self.logger.error(f"❌ Failed at step: {step_name}")
                return False
            
            self.logger.info(f"✅ Completed: {step_name}")
        
        return True
    
    def run_full_pipeline(self, force_current: bool = False) -> bool:
        """
        Run the complete pipeline for all relevant spieltags
        
        Args:
            force_current: If True, process current spieltag even if already processed
            
        Returns:
            True if successful
        """
        self.logger.info("🚀 Starting full pipeline")
        
        if force_current:
            current_spieltag = self.get_current_spieltag()
            if current_spieltag:
                spieltags = [current_spieltag]
            else:
                self.logger.warning("⚠️ No current spieltag found")
                return False
        else:
            # Get spieltags that need processing
            lookback_days = int(os.getenv('LOOKBACK_DAYS', 7))
            spieltags = self.get_spieltags_to_process(lookback_days)
        
        if not spieltags:
            self.logger.info("ℹ️ No spieltags need processing")
            return True
        
        self.logger.info(f"📋 Processing {len(spieltags)} spieltags: {spieltags}")
        
        success_count = 0
        for spieltag in spieltags:
            if self.run_pipeline_for_spieltag(spieltag):
                success_count += 1
            else:
                self.logger.error(f"❌ Pipeline failed for Spieltag {spieltag}")
        
        # Update season tables after processing all spieltags
        if success_count > 0:
            self.logger.info("\n--- Updating Season Tables ---")
            self.step4_update_season_tables()
        
        self.logger.info(f"🏁 Pipeline completed: {success_count}/{len(spieltags)} spieltags successful")
        return success_count == len(spieltags)
    
    def run_dashboard_update(self) -> None:
        """Update dashboard data (placeholder for now)"""
        self.logger.info("🖥️ Dashboard data is automatically updated from CSV files")


def main():
    """Main entry point"""
    import argparse
    import os
    
    parser = argparse.ArgumentParser(description='3. Liga Table of Justice - Weekly Update')
    parser.add_argument('--spieltag', type=int, help='Process specific spieltag')
    parser.add_argument('--force-current', action='store_true', 
                       help='Force processing of current spieltag')
    parser.add_argument('--dashboard-only', action='store_true',
                       help='Only update dashboard data')
    
    args = parser.parse_args()
    
    manager = WeeklyUpdateManager()
    
    try:
        if args.dashboard_only:
            manager.run_dashboard_update()
            success = True
        elif args.spieltag:
            success = manager.run_pipeline_for_spieltag(args.spieltag)
        else:
            success = manager.run_full_pipeline(force_current=args.force_current)
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        manager.logger.info("⏹️ Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        manager.logger.error(f"💥 Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()