#!/usr/bin/env python3
"""
3. Liga Table of Justice - Interactive Dashboard
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import dash
from dash import dcc, html, Input, Output, callback, dash_table
import dash_bootstrap_components as dbc
from pathlib import Path
import sys
from datetime import datetime

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
        
        # Load season table
        season_files = list(source_dir.glob("*season*.csv"))
        if season_files:
            df = pd.read_csv(season_files[0])
            data['season'] = df
        
        # Load individual spieltag files
        spieltag_files = sorted([f for f in source_dir.glob("spieltag*.csv")])
        data['spieltags'] = {}
        
        for file in spieltag_files:
            try:
                spieltag_num = int(file.stem.split('_')[1])
                df = pd.read_csv(file)
                data['spieltags'][spieltag_num] = df
            except (ValueError, IndexError):
                continue
        
        return data
    
    def get_available_teams(self):
        """Get list of all available teams"""
        teams = set()
        for source_data in self.data.values():
            if 'season' in source_data:
                teams.update(source_data['season']['Team'].unique())
        return sorted(teams)
    
    def get_available_spieltags(self):
        """Get list of available spieltags"""
        spieltags = set()
        for source_data in self.data.values():
            spieltags.update(source_data.get('spieltags', {}).keys())
        return sorted(spieltags)

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
                        ], width=6),
                        dbc.Col([
                            html.Label("Compare Sources:"),
                            dbc.Switch(
                                id="compare-sources-switch",
                                label="Enable",
                                value=False
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
        dbc.Tab(label="Team Analysis", tab_id="team-analysis"),
        dbc.Tab(label="Performance Plots", tab_id="performance-plots"),
        dbc.Tab(label="Source Comparison", tab_id="source-comparison"),
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
     Input("source-dropdown", "value"),
     Input("compare-sources-switch", "value")]
)
def render_tab_content(active_tab, source, compare_sources):
    if not source or source not in data_loader.data:
        return dbc.Alert("No data available. Run the pipeline first.", color="warning")
    
    if active_tab == "league-table":
        return render_league_table(source, compare_sources)
    elif active_tab == "team-analysis":
        return render_team_analysis(source)
    elif active_tab == "performance-plots":
        return render_performance_plots(source)
    elif active_tab == "source-comparison":
        return render_source_comparison()
    
    return html.Div("Select a tab")

def render_league_table(source, compare_sources):
    """Render the league table tab"""
    source_data = data_loader.data.get(source, {})
    
    if 'season' not in source_data:
        return dbc.Alert("No season data available", color="warning")
    
    df = source_data['season'].copy()
    
    # Prepare table columns
    columns = [
        {"name": "Pos", "id": "Position", "type": "numeric"},
        {"name": "Team", "id": "Team"},
        {"name": "MP", "id": "Matches_Played", "type": "numeric"},
        {"name": "xP", "id": "xP", "type": "numeric", "format": {"specifier": ".1f"}},
        {"name": "Actual P", "id": "Actual_Points", "type": "numeric"},
        {"name": "Diff", "id": "Point_Difference", "type": "numeric", "format": {"specifier": "+.1f"}},
        {"name": "xGF", "id": "xGF", "type": "numeric", "format": {"specifier": ".1f"}},
        {"name": "xGA", "id": "xGA", "type": "numeric", "format": {"specifier": ".1f"}},
        {"name": "xGD", "id": "xGD", "type": "numeric", "format": {"specifier": "+.1f"}},
    ]
    
    # Add position indicators
    if 'Position' not in df.columns:
        df = df.sort_values('xP', ascending=False).reset_index(drop=True)
        df['Position'] = range(1, len(df) + 1)
    
    # Calculate point difference
    if 'Point_Difference' not in df.columns and 'Actual_Points' in df.columns:
        df['Point_Difference'] = df['xP'] - df['Actual_Points']
    
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
        # Positive point difference
        {
            'if': {'filter_query': '{Point_Difference} > 0'},
            'color': 'green',
        },
        # Negative point difference
        {
            'if': {'filter_query': '{Point_Difference} < 0'},
            'color': 'red',
        }
    ]
    
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
                            "🟢 Promotion • 🟡 Playoff • 🔴 Relegation • ",
                            "Green: Overperforming xP • Red: Underperforming xP"
                        ], className="text-muted mt-2")
                    ])
                ])
            ])
        ])
    ])

def render_team_analysis(source):
    """Render team analysis tab"""
    teams = data_loader.get_available_teams()
    
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H4("Team Analysis")
                ]),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Label("Select Team:"),
                            dcc.Dropdown(
                                id='team-dropdown',
                                options=[{'label': team, 'value': team} for team in teams],
                                value=teams[0] if teams else None
                            )
                        ], width=6)
                    ]),
                    html.Div(id="team-analysis-content", className="mt-4")
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
    
    # Expected vs Actual Points scatter plot
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
    
    # xG vs xGA scatter plot
    fig_xg_scatter = px.scatter(
        df, x='xGA', y='xGF',
        hover_data=['Team'],
        title=f"Expected Goals For vs Against ({source.title()})",
        labels={'xGF': 'Expected Goals For', 'xGA': 'Expected Goals Against'}
    )
    
    return dbc.Row([
        dbc.Col([
            dcc.Graph(figure=fig_scatter)
        ], width=6),
        dbc.Col([
            dcc.Graph(figure=fig_xg_scatter)
        ], width=6)
    ])

def render_source_comparison():
    """Render source comparison tab"""
    if len(config.ENABLED_SOURCES) < 2:
        return dbc.Alert("Need at least 2 data sources for comparison", color="info")
    
    # Compare season data between sources
    comparison_data = []
    
    for source in config.ENABLED_SOURCES:
        source_data = data_loader.data.get(source, {})
        if 'season' in source_data:
            df = source_data['season'].copy()
            df['Source'] = source.title()
            comparison_data.append(df)
    
    if not comparison_data:
        return dbc.Alert("No comparable data available", color="warning")
    
    # Combine data
    combined_df = pd.concat(comparison_data, ignore_index=True)
    
    # Create comparison plot
    fig = px.box(
        combined_df, x='Source', y='xP',
        title="xP Distribution by Source",
        points="all"
    )
    
    return dbc.Row([
        dbc.Col([
            dcc.Graph(figure=fig)
        ])
    ])

# Team analysis callback
@callback(
    Output("team-analysis-content", "children"),
    [Input("team-dropdown", "value"),
     Input("source-dropdown", "value")]
)
def update_team_analysis(selected_team, source):
    if not selected_team or not source:
        return "Select a team to analyze"
    
    source_data = data_loader.data.get(source, {})
    spieltags = source_data.get('spieltags', {})
    
    if not spieltags:
        return dbc.Alert("No match data available", color="warning")
    
    # Collect team data across spieltags
    team_data = []
    for spieltag_num, df in spieltags.items():
        team_matches = df[
            (df['Home_Team'] == selected_team) | 
            (df['Away_Team'] == selected_team)
        ].copy()
        
        for _, match in team_matches.iterrows():
            if match['Home_Team'] == selected_team:
                team_data.append({
                    'Spieltag': spieltag_num,
                    'Opponent': match['Away_Team'],
                    'Home': True,
                    'xG_For': match.get('Home_xG', 0),
                    'xG_Against': match.get('Away_xG', 0),
                    'xP': match.get('Home_xP', 0)
                })
            else:
                team_data.append({
                    'Spieltag': spieltag_num,
                    'Opponent': match['Home_Team'],
                    'Home': False,
                    'xG_For': match.get('Away_xG', 0),
                    'xG_Against': match.get('Home_xG', 0),
                    'xP': match.get('Away_xP', 0)
                })
    
    if not team_data:
        return dbc.Alert(f"No data found for {selected_team}", color="warning")
    
    team_df = pd.DataFrame(team_data).sort_values('Spieltag')
    
    # Create cumulative xP chart
    team_df['Cumulative_xP'] = team_df['xP'].cumsum()
    
    fig_cumulative = px.line(
        team_df, x='Spieltag', y='Cumulative_xP',
        title=f"{selected_team} - Cumulative Expected Points",
        markers=True
    )
    
    # Create xG chart
    fig_xg = go.Figure()
    fig_xg.add_trace(go.Bar(
        x=team_df['Spieltag'],
        y=team_df['xG_For'],
        name='xG For',
        marker_color='green'
    ))
    fig_xg.add_trace(go.Bar(
        x=team_df['Spieltag'],
        y=-team_df['xG_Against'],  # Negative for visual separation
        name='xG Against',
        marker_color='red'
    ))
    fig_xg.update_layout(
        title=f"{selected_team} - Expected Goals by Match",
        yaxis_title="Expected Goals",
        barmode='overlay'
    )
    
    return dbc.Row([
        dbc.Col([
            dcc.Graph(figure=fig_cumulative)
        ], width=6),
        dbc.Col([
            dcc.Graph(figure=fig_xg)
        ], width=6),
        dbc.Col([
            html.H5("Season Summary"),
            html.P(f"Total xP: {team_df['xP'].sum():.1f}"),
            html.P(f"Average xG For: {team_df['xG_For'].mean():.1f}"),
            html.P(f"Average xG Against: {team_df['xG_Against'].mean():.1f}"),
            html.P(f"Matches Played: {len(team_df)}")
        ], width=12, className="mt-4")
    ])

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