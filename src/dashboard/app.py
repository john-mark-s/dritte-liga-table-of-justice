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
        
        return data
    
    def _convert_season_xp_to_table_format(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert season xP table to dashboard format"""
        if 'Total_xP' not in df.columns:
            logger.warning("No Total_xP column found")
            return df
        
        # Create the expected format
        result_df = pd.DataFrame()
        result_df['Team'] = df['Team']
        result_df['xP'] = df['Total_xP']
        
        # Calculate matches played (count non-null spieltag columns)
        spieltag_cols = [col for col in df.columns if col.startswith('spieltag-')]
        result_df['Matches_Played'] = df[spieltag_cols].notna().sum(axis=1)
        
        # Add placeholder for actual points (would need to be loaded from actual results)
        result_df['Actual_Points'] = result_df['xP']  # Placeholder - replace with actual data
        
        # Sort by xP descending
        result_df = result_df.sort_values('xP', ascending=False).reset_index(drop=True)
        result_df['Position'] = range(1, len(result_df) + 1)
        
        return result_df
    
    def _merge_xg_data(self, season_df: pd.DataFrame, xg_df: pd.DataFrame) -> pd.DataFrame:
        """Merge xG data into season dataframe"""
        if 'Total_xG' not in xg_df.columns:
            return season_df
        
        # Create temporary dataframe for merging
        xg_summary = pd.DataFrame()
        xg_summary['Team'] = xg_df['Team']
        xg_summary['Total_xG'] = xg_df['Total_xG']
        
        # For goals for/against, we need to process match data
        # For now, create placeholder values
        xg_summary['xGF'] = xg_summary['Total_xG'] / 2  # Placeholder
        xg_summary['xGA'] = xg_summary['Total_xG'] / 2  # Placeholder
        xg_summary['xGD'] = xg_summary['xGF'] - xg_summary['xGA']
        
        # Merge with season data
        season_df = season_df.merge(xg_summary[['Team', 'xGF', 'xGA', 'xGD']], 
                                   on='Team', how='left')
        
        # Fill NaN values
        season_df['xGF'] = season_df['xGF'].fillna(0)
        season_df['xGA'] = season_df['xGA'].fillna(0)
        season_df['xGD'] = season_df['xGD'].fillna(0)
        
        return season_df

# Initialize data loader
data_loader = DashboardDataLoader()

# Initialize Dash app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = "3. Liga Table of Justice"

# App layout
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.Div([
                html.H1("⚽ 3. Liga Table of Justice", className="text-center mb-0"),
                html.P("Expected Goals (xG) and Expected Points (xP) Analytics", 
                      className="text-center text-muted mb-4"),
            ])
        ])
    ]),
    
    # Controls
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H5("Controls", className="card-title"),
                    dbc.Row([
                        dbc.Col([
                            html.Label("Data Source:"),
                            dcc.Dropdown(
                                id='source-dropdown',
                                options=[
                                    {'label': source.title(), 'value': source} 
                                    for source in config.ENABLED_SOURCES
                                ],
                                value=config.ENABLED_SOURCES[0] if config.ENABLED_SOURCES else None,
                                clearable=False
                            )
                        ], width=6)
                    ])
                ])
            ])
        ])
    ], className="mb-4"),
    
    # Main content tabs
    dbc.Tabs([
        dbc.Tab(label="League Table", tab_id="league-table"),
        dbc.Tab(label="Performance Plots", tab_id="performance-plots"),
    ], id="main-tabs", active_tab="league-table"),
    
    html.Div(id="tab-content", className="mt-4"),
    
    # Footer
    html.Hr(),
    html.Footer([
        html.P([
            "Data scraped from FootyStats and Soccerway • ",
            f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        ], className="text-center text-muted small")
    ])
], fluid=True)

# Callback for tab content
@callback(
    Output("tab-content", "children"),
    [Input("main-tabs", "active_tab"),
     Input("source-dropdown", "value")]
)
def render_tab_content(active_tab, source):
    if not source or source not in data_loader.data:
        return dbc.Alert("No data available. Run the pipeline first.", color="warning")
    
    if active_tab == "league-table":
        return render_league_table(source)
    elif active_tab == "performance-plots":
        return render_performance_plots(source)
    
    return html.Div("Select a tab")

def render_league_table(source):
    """Render the league table tab"""
    source_data = data_loader.data.get(source, {})
    
    if 'season' not in source_data:
        return dbc.Alert("No season data available", color="warning")
    
    df = source_data['season'].copy()
    
    # Calculate point difference if both xP and Actual_Points exist
    if 'Actual_Points' in df.columns and 'xP' in df.columns:
        df['Point_Difference'] = (df['xP'] - df['Actual_Points']).round(1)
    else:
        df['Point_Difference'] = 0.0
    
    # Prepare table columns
    columns = [
        {"name": "Pos", "id": "Position", "type": "numeric"},
        {"name": "Team", "id": "Team"},
        {"name": "MP", "id": "Matches_Played", "type": "numeric"},
        {"name": "xP", "id": "xP", "type": "numeric", "format": {"specifier": ".1f"}},
    ]
    
    # Add actual points if available
    if 'Actual_Points' in df.columns:
        columns.append({"name": "Actual P", "id": "Actual_Points", "type": "numeric"})
        columns.append({"name": "Diff", "id": "Point_Difference", "type": "numeric", "format": {"specifier": "+.1f"}})
    
    # Add xG columns if available
    if 'xGF' in df.columns:
        columns.extend([
            {"name": "xGF", "id": "xGF", "type": "numeric", "format": {"specifier": ".1f"}},
            {"name": "xGA", "id": "xGA", "type": "numeric", "format": {"specifier": ".1f"}},
            {"name": "xGD", "id": "xGD", "type": "numeric", "format": {"specifier": "+.1f"}},
        ])
    
    # Style data conditionally
    style_data_conditional = [
        # Promotion zone (top 2)
        {
            'if': {'filter_query': '{Position} <= 2'},
            'backgroundColor': '#d4edda',
            'color': 'black',
        },
        # Playoff zone (3rd)
        {
            'if': {'filter_query': '{Position} = 3'},
            'backgroundColor': '#fff3cd',
            'color': 'black',
        },
        # Relegation zone (bottom 4)
        {
            'if': {'filter_query': f'{{Position}} >= {len(df)-3}'},
            'backgroundColor': '#f8d7da',
            'color': 'black',
        },
    ]
    
    # Add point difference styling if available
    if 'Point_Difference' in df.columns:
        style_data_conditional.extend([
            {
                'if': {'filter_query': '{Point_Difference} > 0'},
                'color': 'green',
            },
            {
                'if': {'filter_query': '{Point_Difference} < 0'},
                'color': 'red',
            }
        ])
    
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H4(f"xP-Based League Table ({source.title()})", className="mb-0")
                ]),
                dbc.CardBody([
                    dash_table.DataTable(
                        data=df.to_dict('records'),
                        columns=columns,
                        style_cell={'textAlign': 'center', 'padding': '10px'},
                        style_header={'backgroundColor': 'rgb(230, 230, 230)', 'fontWeight': 'bold'},
                        style_data_conditional=style_data_conditional,
                        sort_action="native",
                    ),
                    html.Div([
                        html.Small([
                            "🟢 Promotion • 🟡 Playoff • 🔴 Relegation",
                            " • Green: Overperforming xP • Red: Underperforming xP" if 'Point_Difference' in df.columns else ""
                        ], className="text-muted mt-2")
                    ])
                ])
            ])
        ])
    ])

def render_performance_plots(source):
    """Render performance plots tab"""
    source_data = data_loader.data.get(source, {})
    
    if 'season' not in source_data:
        return dbc.Alert("No season data available", color="warning")
    
    df = source_data['season'].copy()
    
    plots = []
    
    # Expected vs Actual Points scatter plot (if actual points available)
    if 'Actual_Points' in df.columns:
        fig_scatter = px.scatter(
            df, x='xP', y='Actual_Points', 
            hover_data=['Team'],
            title=f"Expected vs Actual Points ({source.title()})",
            labels={'xP': 'Expected Points', 'Actual_Points': 'Actual Points'}
        )
        
        # Add diagonal line (perfect correlation)
        min_val = min(df['xP'].min(), df['Actual_Points'].min())
        max_val = max(df['xP'].max(), df['Actual_Points'].max())
        fig_scatter.add_shape(
            type="line", line=dict(dash="dash"),
            x0=min_val, y0=min_val, x1=max_val, y1=max_val
        )
        
        plots.append(dbc.Col([dcc.Graph(figure=fig_scatter)], width=6))
    
    # xG vs xGA scatter plot (if xG data available)
    if 'xGF' in df.columns and 'xGA' in df.columns:
        fig_xg_scatter = px.scatter(
            df, x='xGA', y='xGF',
            hover_data=['Team'],
            title=f"Expected Goals For vs Against ({source.title()})",
            labels={'xGF': 'Expected Goals For', 'xGA': 'Expected Goals Against'}
        )
        
        plots.append(dbc.Col([dcc.Graph(figure=fig_xg_scatter)], width=6))
    
    # xP distribution
    fig_xp_dist = px.histogram(
        df, x='xP',
        title=f"Expected Points Distribution ({source.title()})",
        labels={'xP': 'Expected Points'}
    )
    plots.append(dbc.Col([dcc.Graph(figure=fig_xp_dist)], width=6))
    
    if not plots:
        return dbc.Alert("No data available for performance plots", color="warning")
    
    return dbc.Row(plots)

# Dashboard class for external usage
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
            self.app.run(host=host, port=port, debug=debug)
        except Exception as e:
            logger.error(f"💥 Dashboard failed: {e}")
            raise

# Create dashboard instance
dashboard = Dashboard()

if __name__ == "__main__":
    dashboard.run(debug=True)