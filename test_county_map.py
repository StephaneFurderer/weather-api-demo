"""
County-Level Choropleth Map - Hurricane Impact Analysis
Identifies counties crossed by hurricane AL042024 on 2024-08-03
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from urllib.request import urlopen
import json
import ssl
import httpx
from datetime import datetime

ssl._create_default_https_context = ssl._create_unverified_context

st.set_page_config(
    page_title="County Choropleth Map Demo",
    page_icon="🗺️",
    layout="wide"
)

st.title("🌀 Hurricane County Impact Map")
st.markdown("Identifying counties crossed by hurricane AL042024 (2024-08-03)")

# Load GeoJSON for US counties
st.sidebar.header("📊 Data Loading")
st.sidebar.info("Loading county boundaries from Plotly's example dataset...")

@st.cache_data
def load_county_geojson():
    """Load county GeoJSON data."""
    try:
        with urlopen('https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json') as response:
            counties = json.load(response)
        return counties
    except Exception as e:
        st.error(f"Error loading GeoJSON: {e}")
        return None

@st.cache_data
def fetch_hurricane_track(track_id: str, date: str) -> list:
    """Fetch hurricane track with full records from API."""
    try:
        api_url = "https://weather-lab-data-api-production.up.railway.app"
        response = httpx.get(f"{api_url}/data", params={"date": date}, timeout=30)
        data = response.json()
        records = [r for r in data.get('records', []) if r.get('track_id') == track_id]
        # Sort by valid_time
        records.sort(key=lambda x: x.get('valid_time', ''))
        return records
    except Exception as e:
        st.error(f"Error fetching hurricane data: {e}")
        return []

def get_counties_crossed_with_timing(track_records: list, counties_geojson: dict) -> pd.DataFrame:
    """Identify counties crossed with timing and hurricane data."""
    try:
        import shapely.geometry as geom
        from datetime import datetime, timedelta
        
        if not track_records:
            return pd.DataFrame()
        
        # Extract coordinates and create line segments
        track_coords = [(r['lat'], r['lon']) for r in track_records if r.get('lat') and r.get('lon')]
        track_lines = []
        for i in range(len(track_coords) - 1):
            lat1, lon1 = track_coords[i]
            lat2, lon2 = track_coords[i + 1]
            track_lines.append(geom.LineString([(lon1, lat1), (lon2, lat2)]))
        
        track_points = [geom.Point(lon, lat) for lat, lon in track_coords]
        
        # Parse start time
        start_time = None
        if track_records[0].get('valid_time'):
            try:
                start_time = datetime.fromisoformat(track_records[0]['valid_time'].replace('Z', '+00:00'))
            except:
                start_time = datetime.now()
        else:
            start_time = datetime.now()
        
        county_data = []
        
        for feature in counties_geojson.get('features', []):
            fips = feature.get('id')
            if not fips:
                continue
            
            # Create polygon
            coords = feature['geometry']['coordinates']
            if feature['geometry']['type'] == 'Polygon':
                polygon = geom.Polygon(coords[0])
            elif feature['geometry']['type'] == 'MultiPolygon':
                polygon = geom.MultiPolygon([geom.Polygon(p[0]) for p in coords])
            else:
                continue
            
            # Find first intersection point and segment
            first_crossing_idx = None
            crossing_time = None
            
            # Check points first
            for i, point in enumerate(track_points):
                if polygon.contains(point) or polygon.touches(point):
                    first_crossing_idx = i
                    if track_records[i].get('valid_time'):
                        try:
                            crossing_time = datetime.fromisoformat(track_records[i]['valid_time'].replace('Z', '+00:00'))
                        except:
                            crossing_time = start_time + timedelta(hours=i*6)
                    else:
                        crossing_time = start_time + timedelta(hours=i*6)
                    break
            
            # Check line segments if no point found
            if first_crossing_idx is None:
                for i, line in enumerate(track_lines):
                    if polygon.intersects(line) or polygon.crosses(line):
                        first_crossing_idx = i
                        # Interpolate time between segment endpoints
                        if track_records[i].get('valid_time') and track_records[i+1].get('valid_time'):
                            try:
                                t1 = datetime.fromisoformat(track_records[i]['valid_time'].replace('Z', '+00:00'))
                                t2 = datetime.fromisoformat(track_records[i+1]['valid_time'].replace('Z', '+00:00'))
                                crossing_time = t1 + (t2 - t1) / 2  # Midpoint
                            except:
                                crossing_time = start_time + timedelta(hours=i*6 + 3)
                        else:
                            crossing_time = start_time + timedelta(hours=i*6 + 3)
                        break
            
            if first_crossing_idx is not None:
                record = track_records[first_crossing_idx]
                relative_hours = (crossing_time - start_time).total_seconds() / 3600
                
                county_data.append({
                    'county_fips': fips,
                    'expected_time': crossing_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'relative_hours': round(relative_hours, 2),
                    'relative_days': round(relative_hours / 24, 2),
                    'lat': record.get('lat'),
                    'lon': record.get('lon'),
                    'wind_speed_knots': record.get('maximum_sustained_wind_speed_knots'),
                    'pressure_hpa': record.get('minimum_sea_level_pressure_hpa'),
                    'radius_km': record.get('radius_34_knot_winds_ne_km')
                })
        
        return pd.DataFrame(county_data).sort_values('relative_hours')
    except ImportError:
        st.warning("⚠️ Shapely required. Install: pip install shapely")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error detecting counties: {e}")
        return pd.DataFrame()

def get_counties_crossed(track_records: list, counties_geojson: dict) -> set:
    """Get set of FIPS codes for quick visualization."""
    df = get_counties_crossed_with_timing(track_records, counties_geojson)
    return set(df['county_fips'].tolist()) if not df.empty else set()

def generate_traveler_data(county_fips_list: list, start_date: str, days: int = 7) -> pd.DataFrame:
    """Generate dummy traveler data per county per day."""
    import random
    from datetime import datetime, timedelta
    
    start = datetime.strptime(start_date, '%Y-%m-%d')
    data = []
    
    for fips in county_fips_list:
        # Base travelers per county (realistic range: 1000-50000)
        base_travelers = random.randint(1000, 50000)
        
        for day_offset in range(days):
            date = start + timedelta(days=day_offset)
            # Add some daily variation (±20%)
            daily_variation = random.uniform(0.8, 1.2)
            travelers = int(base_travelers * daily_variation)
            
            data.append({
                'county_fips': fips,
                'date': date.strftime('%Y-%m-%d'),
                'expected_travelers': travelers
            })
    
    return pd.DataFrame(data)

def calculate_impacted_travelers(df_counties: pd.DataFrame, df_travelers: pd.DataFrame, scenario_start_date: str = None) -> pd.DataFrame:
    """Calculate travelers impacted per county per day based on hurricane crossing."""
    if df_counties.empty or df_travelers.empty:
        return pd.DataFrame()
    
    from datetime import datetime, timedelta
    
    impact_data = []
    
    for _, county_row in df_counties.iterrows():
        fips = county_row['county_fips']
        relative_days = county_row['relative_days']
        
        # If scenario date provided, calculate new impact date based on relative timing
        if scenario_start_date:
            start = datetime.strptime(scenario_start_date, '%Y-%m-%d')
            new_impact_date = (start + timedelta(days=relative_days)).strftime('%Y-%m-%d')
        else:
            # Use original crossing date
            new_impact_date = county_row['expected_time'].split()[0]
        
        # Find traveler data for this county on impact date
        county_travelers = df_travelers[
            (df_travelers['county_fips'] == fips) & 
            (df_travelers['date'] == new_impact_date)
        ]
        
        if not county_travelers.empty:
            travelers = county_travelers.iloc[0]['expected_travelers']
            impact_data.append({
                'county_fips': fips,
                'impact_date': new_impact_date,
                'expected_time': county_row['expected_time'] if not scenario_start_date else f"{new_impact_date} {county_row['expected_time'].split()[1]}",
                'relative_hours': county_row['relative_hours'],
                'relative_days': county_row['relative_days'],
                'travelers_impacted': travelers,
                'wind_speed_knots': county_row['wind_speed_knots'],
                'pressure_hpa': county_row['pressure_hpa'],
                'radius_km': county_row['radius_km']
            })
    
    return pd.DataFrame(impact_data).sort_values('relative_hours')

def create_impact_map(counties_geojson: dict, crossed_fips: set, track_coords: list, df_impact: pd.DataFrame = None):
    """Create choropleth map with traveler impact data and hurricane track."""
    import plotly.graph_objects as go
    
    if df_impact is not None and not df_impact.empty:
        # Use traveler data for coloring
        df_map = df_impact.groupby('county_fips').agg({
            'travelers_impacted': 'sum',
            'impact_date': 'first',
            'relative_days': 'first'
        }).reset_index()
        df_map.columns = ['fips', 'travelers', 'impact_date', 'days']
        
        fig = px.choropleth(
            df_map, geojson=counties_geojson, locations='fips', color='travelers',
            color_continuous_scale='Reds', scope='usa',
            labels={'travelers': 'Travelers Impacted'},
            hover_data=['impact_date', 'days']
        )
        
        # Update hover template to show travelers, date, and day
        fig.update_traces(
            hovertemplate='<b>County FIPS: %{location}</b><br>' +
                         'Travelers Impacted: %{z:,.0f}<br>' +
                         'Impact Date: %{customdata[0]}<br>' +
                         'Days Since Start: %{customdata[1]:.1f}<extra></extra>'
        )
        
        # Update colorbar title
        fig.update_layout(
            coloraxis_colorbar=dict(title="Travelers<br>Impacted")
        )
    else:
        # Fallback: simple binary map
        df = pd.DataFrame({'fips': list(crossed_fips), 'impact': [1] * len(crossed_fips)})
        fig = px.choropleth(
            df, geojson=counties_geojson, locations='fips', color='impact',
            color_continuous_scale='Reds', scope='usa', labels={'impact': 'Affected'}
        )
    
    # Add hurricane track line
    if track_coords:
        lats, lons = zip(*track_coords)
        fig.add_trace(go.Scattergeo(
            lat=lats, lon=lons, mode='lines+markers',
            line=dict(width=3, color='darkred'), 
            marker=dict(size=4, color='red'),
            name='Hurricane Track',
            hovertemplate='<b>Hurricane Path</b><br>Lat: %{lat:.2f}<br>Lon: %{lon:.2f}<extra></extra>'
        ))
    
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, height=600)
    return fig

# Load county boundaries
with st.spinner("Loading county boundaries..."):
    counties_geojson = load_county_geojson()

if counties_geojson:
    st.sidebar.success(f"✅ Loaded {len(counties_geojson['features'])} counties")
    
    # Fetch hurricane track
    track_id = "AL042024"
    date = "2024-08-03"
    
    with st.spinner(f"Fetching hurricane {track_id} track data..."):
        track_records = fetch_hurricane_track(track_id, date)
    
    if track_records:
        track_coords = [(r['lat'], r['lon']) for r in track_records if r.get('lat') and r.get('lon')]
        st.sidebar.success(f"✅ Found {len(track_coords)} track points")
        
        # Identify affected counties with timing
        with st.spinner("Identifying affected counties with timing..."):
            df_counties = get_counties_crossed_with_timing(track_records, counties_geojson)
            crossed_fips = set(df_counties['county_fips'].tolist()) if not df_counties.empty else set()
        
        st.sidebar.success(f"✅ {len(crossed_fips)} counties affected")
        
        # Display results
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Track Points", len(track_coords))
        with col2:
            st.metric("Affected Counties", len(crossed_fips))
        with col3:
            st.metric("Hurricane", track_id)
        with col4:
            if not df_counties.empty:
                first_time = df_counties.iloc[0]['expected_time']
                st.metric("First Impact", first_time.split()[0])
        
        # Initial map showing affected counties
        st.subheader("🗺️ Counties Crossed by Hurricane")
        fig_initial = create_impact_map(counties_geojson, crossed_fips, track_coords)
        st.plotly_chart(fig_initial, use_container_width=True)
        
        # Detailed county impact table
        if not df_counties.empty:
            st.subheader("📋 County Impact Timeline & Data")
            st.markdown("**Expected crossing times and hurricane conditions for each county**")
            
            # Format table for display
            display_df = df_counties[[
                'county_fips', 'expected_time', 'relative_hours', 'relative_days',
                'wind_speed_knots', 'pressure_hpa', 'radius_km', 'lat', 'lon'
            ]].copy()
            display_df.columns = [
                'County FIPS', 'Expected Time', 'Hours Since Start', 'Days Since Start',
                'Wind Speed (knots)', 'Pressure (hPa)', 'Radius (km)', 'Latitude', 'Longitude'
            ]
            
            st.dataframe(display_df, use_container_width=True)
            
            # Traveler Impact Analysis
            st.subheader("👥 Traveler Impact Analysis")
            
            days_ahead = st.slider("Days to analyze", 1, 14, 7, help="Number of days from start date to analyze")
            
            with st.spinner("Generating traveler data..."):
                affected_fips = df_counties['county_fips'].tolist()
                df_travelers = generate_traveler_data(affected_fips, date, days_ahead)
            
            st.success(f"✅ Generated traveler data for {len(affected_fips)} counties over {days_ahead} days")
            
            # Calculate impacted travelers
            df_impact = calculate_impacted_travelers(df_counties, df_travelers)
            
            # Enhanced map with traveler impact data
            if not df_impact.empty:
                st.subheader("🗺️ Impact Map: Travelers & Impact Days")
                fig_impact = create_impact_map(counties_geojson, crossed_fips, track_coords, df_impact)
                st.plotly_chart(fig_impact, use_container_width=True)
                st.info("💡 **Map shows:** Counties colored by travelers impacted. Hover to see impact date and day. Red line = hurricane track.")
            
            if not df_impact.empty:
                # Impact summary metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Travelers Impacted", f"{df_impact['travelers_impacted'].sum():,}")
                with col2:
                    st.metric("Affected Counties", len(df_impact))
                with col3:
                    st.metric("Avg per County", f"{df_impact['travelers_impacted'].mean():,.0f}")
                with col4:
                    daily_max = df_impact.groupby('impact_date')['travelers_impacted'].sum().max()
                    st.metric("Peak Day Travelers", f"{daily_max:,}")
                
                # Detailed impact table
                st.subheader("📋 Traveler Impact by County & Day")
                display_impact = df_impact[[
                    'county_fips', 'impact_date', 'expected_time', 'relative_days',
                    'travelers_impacted', 'wind_speed_knots', 'pressure_hpa'
                ]].copy()
                display_impact.columns = [
                    'County FIPS', 'Impact Date', 'Expected Time', 'Days Since Start',
                    'Travelers Impacted', 'Wind Speed (knots)', 'Pressure (hPa)'
                ]
                st.dataframe(display_impact, use_container_width=True)
                
                # Daily impact summary
                st.subheader("📊 Daily Impact Summary")
                daily_summary = df_impact.groupby('impact_date').agg({
                    'travelers_impacted': 'sum',
                    'county_fips': 'count'
                }).reset_index()
                daily_summary.columns = ['Date', 'Total Travelers Impacted', 'Counties Affected']
                st.dataframe(daily_summary, use_container_width=True)
                
                # Visualization: Travelers impacted over time
                st.subheader("📈 Travelers Impacted Over Time")
                fig_timeline = px.bar(
                    daily_summary, 
                    x='Date', 
                    y='Total Travelers Impacted',
                    title='Daily Traveler Impact',
                    labels={'Total Travelers Impacted': 'Travelers Impacted', 'Date': 'Date'}
                )
                st.plotly_chart(fig_timeline, use_container_width=True)
                
                # Export data
                st.subheader("💾 Export Data")
                csv_impact = df_impact.to_csv(index=False)
                st.download_button(
                    "Download Impact Data (CSV)",
                    csv_impact,
                    f"hurricane_impact_{track_id}_{date}.csv",
                    "text/csv"
                )
                
                # What-If Scenario Analysis
                st.markdown("---")
                st.subheader("🔮 What-If Scenario Analysis")
                st.markdown("**Compare impact if the same hurricane occurred at a different time**")
                
                scenario_date = st.date_input(
                    "Scenario Start Date",
                    value=datetime.strptime("2025-09-10", "%Y-%m-%d").date(),
                    help="What if the hurricane started on this date instead?"
                )
                
                if st.button("Run What-If Scenario"):
                    with st.spinner(f"Generating scenario for {scenario_date}..."):
                        # Generate traveler data for scenario date
                        scenario_start = scenario_date.strftime('%Y-%m-%d')
                        df_travelers_scenario = generate_traveler_data(affected_fips, scenario_start, days_ahead)
                        
                        # Calculate impact with new dates
                        df_impact_scenario = calculate_impacted_travelers(
                            df_counties, df_travelers_scenario, scenario_start_date=scenario_start
                        )
                        
                        if not df_impact_scenario.empty:
                            # Comparison metrics
                            st.subheader("📊 Scenario Comparison")
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.markdown("### Original Scenario")
                                st.metric("Start Date", date)
                                st.metric("Total Travelers", f"{df_impact['travelers_impacted'].sum():,}")
                                st.metric("Peak Day", df_impact.groupby('impact_date')['travelers_impacted'].sum().idxmax())
                                st.metric("Peak Day Travelers", f"{df_impact.groupby('impact_date')['travelers_impacted'].sum().max():,}")
                            
                            with col2:
                                st.markdown("### What-If Scenario")
                                st.metric("Start Date", scenario_start)
                                st.metric("Total Travelers", f"{df_impact_scenario['travelers_impacted'].sum():,}")
                                if not df_impact_scenario.empty:
                                    peak_day = df_impact_scenario.groupby('impact_date')['travelers_impacted'].sum().idxmax()
                                    peak_travelers = df_impact_scenario.groupby('impact_date')['travelers_impacted'].sum().max()
                                    st.metric("Peak Day", peak_day)
                                    st.metric("Peak Day Travelers", f"{peak_travelers:,}")
                            
                            # Difference
                            diff = df_impact_scenario['travelers_impacted'].sum() - df_impact['travelers_impacted'].sum()
                            pct_change = (diff / df_impact['travelers_impacted'].sum() * 100) if df_impact['travelers_impacted'].sum() > 0 else 0
                            
                            st.metric(
                                "Difference",
                                f"{diff:+,} travelers ({pct_change:+.1f}%)",
                                delta=f"{pct_change:.1f}%"
                            )
                            
                            # Scenario map
                            st.subheader("🗺️ What-If Scenario Map")
                            fig_scenario = create_impact_map(counties_geojson, crossed_fips, track_coords, df_impact_scenario)
                            st.plotly_chart(fig_scenario, use_container_width=True)
                            st.info(f"💡 Map shows impact if hurricane started on {scenario_start}. Same track, different traveler patterns.")
                            
                            # Comparison table
                            st.subheader("📋 Side-by-Side Comparison")
                            comparison_df = pd.merge(
                                df_impact[['county_fips', 'impact_date', 'travelers_impacted']].rename(
                                    columns={'impact_date': 'original_date', 'travelers_impacted': 'original_travelers'}
                                ),
                                df_impact_scenario[['county_fips', 'impact_date', 'travelers_impacted']].rename(
                                    columns={'impact_date': 'scenario_date', 'travelers_impacted': 'scenario_travelers'}
                                ),
                                on='county_fips',
                                how='outer'
                            )
                            comparison_df['difference'] = comparison_df['scenario_travelers'].fillna(0) - comparison_df['original_travelers'].fillna(0)
                            comparison_df.columns = [
                                'County FIPS', 'Original Date', 'Original Travelers',
                                'Scenario Date', 'Scenario Travelers', 'Difference'
                            ]
                            st.dataframe(comparison_df, use_container_width=True)
                        else:
                            st.warning("⚠️ No impact data calculated for scenario. Check date matching.")
            
            # Summary statistics
            with st.expander("📊 Impact Summary"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Duration", f"{df_counties['relative_hours'].max():.1f} hours")
                with col2:
                    st.metric("Avg Wind Speed", f"{df_counties['wind_speed_knots'].mean():.1f} knots")
                with col3:
                    st.metric("Min Pressure", f"{df_counties['pressure_hpa'].min():.1f} hPa")
        else:
            st.warning("⚠️ No counties identified. Check if hurricane track is over land.")
    else:
        st.warning(f"⚠️ No track data found for {track_id} on {date}")
    
else:
    st.error("❌ Failed to load county boundaries.")

