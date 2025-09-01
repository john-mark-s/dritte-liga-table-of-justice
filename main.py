#!/usr/bin/env python3
"""
3. Liga Table of Justice - Main CLI Entry Point
"""

import argparse
import sys
from pathlib import Path

from src.automation import WeeklyUpdateManager
from src.dashboard.app import dashboard
from src.utils.config import config
from src.utils.logger import get_logger
from src.calculators.standings_calculator import GenerateClassicStandings  

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(
        description='3. Liga Table of Justice - xG/xP Analytics Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py run                    # Run full pipeline
  python main.py run --spieltag 5       # Process specific spieltag
  python main.py dashboard              # Start dashboard
  python main.py dashboard --port 8080  # Start dashboard on different port
  python main.py setup                  # Setup directories and config
  python main.py standings              # Calculate classic standings  

        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run data pipeline')
    run_parser.add_argument('--spieltag', type=int, help='Process specific spieltag')
    run_parser.add_argument('--force-current', action='store_true',
                           help='Force processing current spieltag')
    run_parser.add_argument('--sources', nargs='+', 
                           choices=['footystats', 'soccerway'],
                           help='Specific sources to process')
    
    # Dashboard command
    dash_parser = subparsers.add_parser('dashboard', help='Start dashboard')
    dash_parser.add_argument('--host', default=None, help='Dashboard host')
    dash_parser.add_argument('--port', type=int, default=None, help='Dashboard port')
    dash_parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    # Setup command
    setup_parser = subparsers.add_parser('setup', help='Setup directories and config')
    setup_parser.add_argument('--force', action='store_true', 
                             help='Overwrite existing files')
    
    # Scrape command (individual operations)
    scrape_parser = subparsers.add_parser('scrape', help='Individual scraping operations')
    scrape_parser.add_argument('type', choices=['fixtures', 'xg'], 
                              help='What to scrape')
    scrape_parser.add_argument('--source', choices=['footystats', 'soccerway'],
                              required=True, help='Data source')
    scrape_parser.add_argument('--spieltag', type=int, required=True,
                              help='Spieltag to scrape')
    
    # Calculate command
    calc_parser = subparsers.add_parser('calculate', help='Calculate xP/xG tables')
    calc_parser.add_argument('type', choices=['xp', 'season'], 
                            help='What to calculate')
    calc_parser.add_argument('--source', choices=['footystats', 'soccerway'],
                            help='Specific source (optional)')
    
    # Standings command  
    standings_parser = subparsers.add_parser('standings', help='Calculate classic league standings')  
    standings_parser.add_argument('--csv-folder', type=str, default=config.SOCCERWAY_DIR,  
                                  help='CSV folder for standings calculation')  
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    logger = get_logger('main')
    
    try:
        if args.command == 'setup':
            setup_project(args.force)
        
        elif args.command == 'run':
            run_pipeline(args)
        
        elif args.command == 'dashboard':
            start_dashboard(args)
        
        elif args.command == 'scrape':
            run_scraping(args)
        
        elif args.command == 'calculate':
            run_calculation(args)
            
        elif args.command == 'standings':  
            calculate_standings(args)
        
    except KeyboardInterrupt:
        logger.info("⏹️ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"💥 Error: {e}")
        sys.exit(1)


def setup_project(force: bool = False):
    """Setup project directories and configuration"""
    logger = get_logger('setup')
    
    logger.info("🔧 Setting up 3. Liga Table of Justice")
    
    # Create directories
    config.ensure_directories()
    logger.info("✅ Created directories")
    
    # Create .env file if it doesn't exist
    env_file = Path('.env')
    env_example = Path('.env.example')
    
    if not env_file.exists() or force:
        if env_example.exists():
            import shutil
            shutil.copy(env_example, env_file)
            logger.info("✅ Created .env file from .env.example")
        else:
            logger.warning("⚠️ .env.example not found, skipping .env creation")
    
    logger.info("🎉 Setup complete!")
    print("\n📋 Next steps:")
    print("1. Edit .env file with your settings")
    print("2. Run: python main.py run --spieltag 1")
    print("3. Run: python main.py dashboard")


def run_pipeline(args):
    """Run the data processing pipeline"""
    logger = get_logger('pipeline')
    
    manager = WeeklyUpdateManager()
    
    if args.sources:
        # Temporarily override enabled sources
        original_sources = config.ENABLED_SOURCES.copy()
        config.ENABLED_SOURCES[:] = args.sources
        logger.info(f"🎯 Processing only sources: {args.sources}")
    
    try:
        if args.spieltag:
            success = manager.run_pipeline_for_spieltag(args.spieltag)
        else:
            success = manager.run_full_pipeline(force_current=args.force_current)
        
        if success:
            logger.info("✅ Pipeline completed successfully!")
        else:
            logger.error("❌ Pipeline failed!")
            sys.exit(1)
            
    finally:
        if args.sources:
            # Restore original sources
            config.ENABLED_SOURCES[:] = original_sources


def start_dashboard(args):
    """Start the dashboard"""
    logger = get_logger('dashboard')
    
    logger.info("🚀 Starting 3. Liga Table of Justice Dashboard")
    
    # Check if data files exist
    data_found = False
    for source in config.ENABLED_SOURCES:
        source_dir = getattr(config, f"{source.upper()}_DIR")
        season_files = list(source_dir.glob("*season*.csv"))
        if season_files:
            data_found = True
            break
    
    if not data_found:
        logger.warning("⚠️ No data files found. Run the pipeline first:")
        logger.warning("   python main.py run")
    
    try:
        dashboard.run(
            host=args.host,
            port=args.port,
            debug=args.debug
        )
    except Exception as e:
        logger.error(f"❌ Dashboard failed to start: {e}")
        sys.exit(1)


def run_scraping(args):
    """Run individual scraping operations"""
    logger = get_logger('scraping')
    
    manager = WeeklyUpdateManager()
    
    if args.type == 'fixtures':
        logger.info(f"🏈 Scraping {args.source} fixtures for Spieltag {args.spieltag}")
        success = manager.step1_scrape_fixtures(args.spieltag)
    
    elif args.type == 'xg':
        logger.info(f"🎯 Scraping {args.source} xG for Spieltag {args.spieltag}")
        success = manager.step2_scrape_xg(args.spieltag)
    
    else:
        logger.error(f"❌ Unknown scraping type: {args.type}")
        sys.exit(1)
    
    if success:
        logger.info("✅ Scraping completed successfully!")
    else:
        logger.error("❌ Scraping failed!")
        sys.exit(1)


def run_calculation(args):
    """Run calculation operations"""
    logger = get_logger('calculation')
    
    if args.type == 'xp':
        from src.calculators.xp_calculator import XPCalculator
        
        calculator = XPCalculator()
        sources = [args.source] if args.source else config.ENABLED_SOURCES
        
        for source in sources:
            source_dir = getattr(config, f"{source.upper()}_DIR")
            logger.info(f"📊 Calculating xP for {source}")
            calculator.batch_process_directory(source_dir)
    
    elif args.type == 'season':
        from src.calculators.xp_calculator import SeasonXPProcessor
        
        processor = SeasonXPProcessor()
        sources = [args.source] if args.source else config.ENABLED_SOURCES
        
        for source in sources:
            source_dir = getattr(config, f"{source.upper()}_DIR")
            logger.info(f"📈 Creating season tables for {source}")
            processor.process_directory(source_dir)
    
    else:
        logger.error(f"❌ Unknown calculation type: {args.type}")
        sys.exit(1)
    
    logger.info("✅ Calculation completed successfully!")


def calculate_standings(args):  
    """Calculate classic league standings"""  
    logger = get_logger('standings')  
    source_dir = config.SOCCERWAY_DIR  
    csv_folder = source_dir
  
    try:  
        logger.info(f"📊 Calculating classic standings from {csv_folder}")  
        GenerateClassicStandings().calculate_classic_standings(csv_folder)  
        logger.info("✅ Classic standings calculation completed successfully!")  
    except Exception as e:  
        logger.error(f"❌ Error calculating classic standings: {e}")  
        sys.exit(1)  

if __name__ == "__main__":
    main()