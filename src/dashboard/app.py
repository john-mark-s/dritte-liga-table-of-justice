#!/usr/bin/env python3
"""
3. Liga Table of Justice - Interactive Dashboard
"""

import sys
import dash
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
from pathlib import Path
from datetime import datetime
from plotly.subplots import make_subplots
from dash import dcc, html, Input, Output, callback, dash_table

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.config import config
from utils.logger import get_logger

logger = get_logger('dashboard')

class DashboardDataLoader:
    """Load and process data for dashboard"""
    
    def __init__(self):
        self.data = {}
        self.load_all_data()
    
    def load_all_data(self):
        """Load all available data from sources"""
        for source in config.ENABLED_SOURCES:
            try:
                source_dir = getattr(config, f"{source.upper()}_DIR")
                self.data[source] = self._load_source_data(source_dir, source)
                logger.info(f"✅ Loaded {source} data")
            except Exception as e:
                logger.warning(f"⚠️ Failed to load {source} data: {e}")
                self.data[source] = {}
    
    def _load_source_data(self, source_dir: Path, source: str):
        """Load data from a specific source directory"""
        data = {}
        
        # Load season xP table
        xp_files = list(source_dir.glob("*season_xp*.csv"))
        if xp_files:
            df = pd.read_csv(xp_files[0])
            # Convert to expected format
            season_df = self._convert_season_xp_to_table_format(df)
            data['season'] = season_df
            logger.info(f"Loaded season xP table with {len(season_df)} teams")
        
        # Load season xG table for additional metrics
        xg_files = list(source_dir.glob("*season_xg*.csv"))
        if xg_files:
            xg_df = pd.read_csv(xg_files[0])
            if 'season' in data:
                data['season'] = self._merge_xg_data(data['season'], xg_df)
        
        # Load classical league table if available (now in season format)
        classical_files = list(source_dir.glob("season_classic*.csv"))
        if classical_files:
            classic_df = pd.read_csv(classical_files[0])

            # Convert to expected format ()
            classic_season_df = self._convert_season_classic_to_table_format(classic_df)
            
            data['classical'] = classic_season_df
            # Merge classical standings into season data if available
            if 'season' in data:
                data['season'] = self._merge_classical_standings(data['season'], classic_season_df)
            
            logger.info(f"Loaded classical standings with {len(classic_season_df)} teams")
            
        else:
            logger.warning(f"No classical standings file found in {source_dir}")
            logger.info("Expected filename pattern: classic_standings_spieltag-*.csv")
        
        return data
    
    def _merge_classical_standings(self, season_df: pd.DataFrame, standings_df: pd.DataFrame) -> pd.DataFrame:
        """Merge classical standings data (actual points) into season dataframe"""
        if 'Actual_Points' not in standings_df.columns:
            return season_df
        
        try:
            # Merge with season data
            season_df = season_df.merge(standings_df[['Team', 'Actual_Points']], 
                                        on='Team', how='left')
            
            # Fill NaN values
            season_df['Actual_Points'] = season_df['Actual_Points'].fillna(0)
            
            logger.info(f"Successfully merged classical points for {len(season_df)} teams")
            
        except Exception as e:
            logger.warning(f"Failed to merge classical standings: {e}")
            season_df['Actual_Points'] = 0
        
        return season_df

    def _convert_season_xp_to_table_format(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert season xP table to dashboard format"""
        if 'Total_xP' not in df.columns:
            logger.warning("No Total_xP column found")
            return df
        
        # Create the expected format
        result_df = pd.DataFrame()
        result_df['Team'] = df['Team']
        result_df['xP'] = df['Total_xP'].round(1)
        
        # Calculate matches played (count non-null spieltag columns)
        spieltag_cols = [col for col in df.columns if col.startswith('spieltag-')]
        result_df['Matches_Played'] = df[spieltag_cols].notna().sum(axis=1)
        
        # Sort by xP descending for initial positioning
        result_df = result_df.sort_values('xP', ascending=False).reset_index(drop=True)
        result_df['Position'] = range(1, len(result_df) + 1)
        
        return result_df
    
    def _convert_season_classic_to_table_format(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert classical standings CSV to expected dashboard format"""
        
        # Standardize column names
        df = df.rename(columns={
            'total_points': 'Actual_Points',
        })

        # Calculate matches played (count non-null spieltag columns)
        spieltag_cols = [col for col in df.columns if col.startswith('spieltag-')]
        result_df = pd.DataFrame()
        result_df['Team'] = df['Team']
        result_df['Actual_Points'] = df['Actual_Points']
        result_df['Matches_Played'] = df[spieltag_cols].notna().sum(axis=1)
        
        # Sort by Actual_Points descending for initial positioning
        result_df = result_df.sort_values('Actual_Points', ascending=False).reset_index(drop=True)
        result_df['Position'] = range(1, len(result_df) + 1)
        
        return result_df
    
    def _merge_xg_data(self, season_df: pd.DataFrame, xg_df: pd.DataFrame) -> pd.DataFrame:
        """Merge xG data into season dataframe - only keeping xGF"""
        if 'Total_xG' not in xg_df.columns:
            return season_df
        
        try:
            # Create temporary dataframe for merging
            xg_summary = pd.DataFrame()
            xg_summary['Team'] = xg_df['Team']
            
            # Only extract xGF (Goals For) - assuming Total_xG represents this
            if 'xGF' in xg_df.columns:
                xg_summary['xGF'] = xg_df['xGF']
            elif 'Goals_For_xG' in xg_df.columns:
                xg_summary['xGF'] = xg_df['Goals_For_xG']
            else:
                # Fallback: use Total_xG as approximation for xGF
                xg_summary['xGF'] = xg_df['Total_xG']
            
            # Round to 1 decimal place
            xg_summary['xGF'] = xg_summary['xGF'].round(1)
            
            # Merge with season data
            season_df = season_df.merge(xg_summary[['Team', 'xGF']], 
                                       on='Team', how='left')
            
            # Fill NaN values
            season_df['xGF'] = season_df['xGF'].fillna(0.0)
            
            logger.info(f"Successfully merged xGF data for {len(season_df)} teams")
            
        except Exception as e:
            logger.warning(f"Failed to merge xG data: {e}")
            season_df['xGF'] = 0.0
        
        return season_df


class Dashboard:
    """Dashboard wrapper class"""
    
    def __init__(self):
        self.app = app
        self.data_loader = data_loader
    
    def run(self, host=None, port=None, debug=None):
        """Run the dashboard"""
        # Use config defaults if not specified
        host = host or config.DASHBOARD_HOST
        port = port or config.DASHBOARD_PORT
        debug = debug if debug is not None else config.DASHBOARD_DEBUG
        
        logger.info(f"🌐 Dashboard running at http://{host}:{port}")
        
        try:
            self.app.run_server(host=host, port=port, debug=debug)  # Changed from run()
        except Exception as e:
            logger.error(f"💥 Dashboard failed: {e}")
            raise


def render_league_table_component(source, selected_teams=None):
    """Render the league table component"""
    source_data = data_loader.data.get(source, {})
    
    if 'season' not in source_data:
        return dbc.Alert("No season data available", color="warning")
    
    df = source_data['season'].copy()

        # Calculate Points Diff (Actual_Points - xP)
    if 'Actual_Points' in df.columns and 'xP' in df.columns:
        df['Points Diff'] = (df['Actual_Points'] - df['xP']).round(1)
    
    # Filter by selected teams if any
    if selected_teams:
        df = df[df['Team'].isin(selected_teams)]
    
    # Prepare table columns based on your requirements
    columns = [
        {"name": "Pos", "id": "Position", "type": "numeric"},
        {"name": "Team", "id": "Team"},
        {"name": "MP", "id": "Matches_Played", "type": "numeric"},
        {"name": "Actual P", "id": "Actual_Points", "type": "numeric"},
        {"name": "xP", "id": "xP", "type": "numeric", "format": {"specifier": ".1f"}},
        {"name": "Points Diff", "id": "Points Diff", "type": "numeric", "format": {"specifier": ".1f"}}
    ]
    
    
    filter_text = f" (Filtered: {len(df)} teams)" if selected_teams else f" (All {len(df)} teams)"
    
    return dbc.Card([
        dbc.CardHeader([
            html.H4(f"xP-Based League Table")
        ]),
        dbc.CardBody([
            dash_table.DataTable(
                data=df.to_dict('records'),
                columns=columns,
                style_cell={'textAlign': 'center', 'padding': '8px', 'fontSize': '12px'},
                style_header={'backgroundColor': 'rgb(230, 230, 230)', 'fontWeight': 'bold', 'fontSize': '12px'},
                sort_action="native",
                page_size=20,
            )
        ])
    ])


def render_performance_plot_component(source, selected_teams=None):
    """Show dots only, team names on hover with enhanced styling"""
    source_data = data_loader.data.get(source, {})
    
    if 'season' not in source_data:
        return dbc.Alert("No season data available", color="warning")
    
    df = source_data['season'].copy()
    
    if 'Actual_Points' in df.columns and not df['Actual_Points'].isna().all():
        
        # Add jitter
        np.random.seed(42)
        jitter_amount = 0.05
        df['Actual_Points_Jittered'] = df['Actual_Points'] + np.random.uniform(-jitter_amount, jitter_amount, len(df))
        
        # Calculate performance difference for color coding
        df['Performance_Diff'] = df['Actual_Points'] - df['xP']
        
        if selected_teams:
            df['Color'] = df['Team'].apply(lambda x: 'Highlighted' if x in selected_teams else 'Other')
            df_filtered = df[df['Team'].isin(selected_teams)]
            df_other = df[~df['Team'].isin(selected_teams)]
        else:
            df['Color'] = 'All Teams'
        
        # Create scatter plot with NO TEXT labels, only hover
        if selected_teams:
            # Other teams (background)
            fig_scatter = px.scatter(
                df_other, x='xP', y='Actual_Points_Jittered',
                hover_name='Team',
                hover_data={
                    'xP': ':.1f',  # 1 decimal place for xP
                    'Actual_Points': ':.0f',  # 0 decimals for actual points (original, non-jittered)
                    'Performance_Diff': ':.1f',  # 1 decimal for performance difference
                    'Actual_Points_Jittered': False  # Hide the jittered y-axis value
                },
                title=f"Expected vs Actual Points (Hover for team names)",
                height=500,
                opacity=0.4,
                labels={
                    'xP': 'Expected Points',
                    'Actual_Points': 'Points',
                    'Performance_Diff': 'Difference',
                    'Actual_Points_Jittered': 'Actual Points'
                }
            )
            
            # Highlighted teams
            fig_highlight = px.scatter(
                df_filtered, x='xP', y='Actual_Points_Jittered',
                hover_name='Team',
                hover_data={
                    'xP': ':.1f',
                    'Actual_Points': ':.0f', 
                    'Performance_Diff': ':.1f',
                    'Actual_Points_Jittered': False  # Hide the jittered y-axis value
                },
                labels={
                    'xP': 'Expected Points',
                    'Actual_Points': 'Points',
                    'Performance_Diff': 'Difference',
                    'Actual_Points_Jittered': 'Actual Points'
                }
            )
            
            for trace in fig_highlight.data:
                trace.marker.size = 12
                trace.marker.color = 'red'
                trace.marker.line = dict(width=2, color='darkred')
                fig_scatter.add_trace(trace)
        else:
            # Color code by performance (overperforming = green, underperforming = red)
            fig_scatter = px.scatter(
                df, x='xP', y='Actual_Points_Jittered',
                color='Performance_Diff',
                hover_name='Team',
                hover_data={
                    'xP': ':.1f',
                    'Actual_Points': ':.0f', 
                    'Performance_Diff': ':.1f',
                    'Actual_Points_Jittered': False  # Hide the jittered y-axis value
                },
                color_continuous_scale=['red', 'lightgray', 'green'],
                color_continuous_midpoint=0,
                title=f"Expected vs Actual Points (Color = Performance)",
                height=500,
                labels={
                    'xP': 'Expected Points',
                    'Actual_Points': 'Points',
                    'Performance_Diff': 'Difference',
                    'Actual_Points_Jittered': 'Actual Points'
                }
            )
            fig_scatter.update_traces(marker=dict(size=10, line=dict(width=1, color='black')))
        
        # Add diagonal line and styling as before
        min_val = min(df['xP'].min(), df['Actual_Points'].min()) - 1
        max_val = max(df['xP'].max(), df['Actual_Points'].max()) + 1
        fig_scatter.add_shape(
            type="line", line=dict(dash="dash", color="gray", width=2),
            x0=min_val, y0=min_val, x1=max_val, y1=max_val
        )
        
        fig_scatter.update_layout(
            showlegend=False,
            plot_bgcolor='white',
            xaxis=dict(gridcolor='lightgray'),
            yaxis=dict(gridcolor='lightgray', title='Actual Points'),
            margin=dict(l=40, r=40, t=40, b=40)
        )
        
        filter_note = ""
        if selected_teams:
            filter_note = f" Showing {len(selected_teams)} selected team(s) in red."
        
        return dbc.Card([
            dbc.CardBody([
                dcc.Graph(figure=fig_scatter),
                html.Div([
                    html.P([
                        "Teams above the red line are overperforming their expected points, ",
                        "while teams below are underperforming. ",
                        "Actual points are slightly jittered to better show overlapping values.",
                        filter_note
                    ], className="text-muted small mt-2")
                ])
            ])
        ])
    else:
        return dbc.Alert(
            "Actual points data not available. This analysis requires both expected points (xP) and actual points data.",
            color="info"
        )


# Initialize data loader
data_loader = DashboardDataLoader()

# Initialize Dash app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = "3. Liga Table of Justice"

# Make server accessible for WSGI
server = app.server

# App layout
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.Div([
                html.H1("3. Liga Table of Justice", className="text-center mb-0"),
                html.P("Expected Goals (xG) and Expected Points (xP) Analytics", 
                      className="text-center text-muted mb-4"),
            ])
        ])
    ]),
    
    # Data source tabs
    dbc.Tabs([
        dbc.Tab(label="FootyStats", tab_id="footystats"),
        dbc.Tab(label="Soccerway", tab_id="soccerway"),
    ], id="source-tabs", active_tab="footystats"),

    # Controls
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H5("Filter by Team:", className="card-title"),
                    dbc.Row([
                        dbc.Col([
                            dcc.Dropdown(
                                id='team-filter-dropdown',
                                placeholder="Select teams to highlight (leave empty to show all)",
                                multi=True,
                                clearable=True
                            )
                        ], width=12)
                    ])
                ])
            ])
        ])
    ], className="mb-4"),
    
    # Main content - side by side layout
    html.Div(id="main-content", className="mt-4"),
    
    # Footer
    html.Hr(),
    html.Footer([
        html.P([
            "Data scraped from FootyStats and Soccerway • ",
            f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        ], className="text-center text-muted small")
    ])
], fluid=True)


# Callbacks for main content and team filter
@callback(
    Output("team-filter-dropdown", "options"),
    [Input("source-tabs", "active_tab")]
)
def update_team_filter_options(source):
    """Update team filter options based on selected data source"""
    if not source or source not in data_loader.data:
        return []
    
    source_data = data_loader.data.get(source, {})
    if 'season' not in source_data:
        return []
    
    teams = source_data['season']['Team'].tolist()
    return [{'label': team, 'value': team} for team in sorted(teams)]

@callback(
    Output("main-content", "children"),
    [Input("source-tabs", "active_tab"),
     Input("team-filter-dropdown", "value")]
)
def render_main_content(source, selected_teams):
    if not source or source not in data_loader.data:
        return dbc.Alert("No data available. Run the pipeline first.", color="warning")
    
    # Get the league table and performance plot components
    league_table = render_league_table_component(source, selected_teams)
    performance_plot = render_performance_plot_component(source, selected_teams)
    
    # Return side-by-side layout
    return dbc.Row([
        dbc.Col([league_table], width=6),
        dbc.Col([performance_plot], width=6)
    ])


# Create dashboard instance
dashboard = Dashboard()

if __name__ == "__main__":
    dashboard.run(debug=True)