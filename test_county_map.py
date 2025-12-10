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
import io
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


def load_zip_to_fips_mapping():
    """Load zip code to FIPS county code mapping from public dataset."""
    try:
        # Try multiple public sources for zip-to-FIPS mapping
        sources = [
            {
                'name': 'Census ZCTA to County',
                'url': 'https://www2.census.gov/geo/docs/maps-data/data/rel/zcta_county_rel_10.txt',
            }
        ]
        
        for source in sources:
            try:
                # Use httpx with SSL verification disabled to avoid certificate issues
                # or use urlopen which respects the SSL context set at module level
                
                # Method 1: Try httpx (already imported)
                try:
                    response = httpx.get(source['url'], timeout=30, verify=False)
                    response.raise_for_status()
                    df = pd.read_csv(io.StringIO(response.text), sep=',', dtype={'ZCTA5': str, 'COUNTY': str, 'STATE': str})
                except:
                    # Method 2: Fallback to urlopen (respects ssl._create_default_https_context)
                    with urlopen(source['url']) as response:
                        df = pd.read_csv(response, sep='|', dtype={'ZCTA5': str, 'COUNTY': str, 'STATE': str})
                
                # Create FIPS code from STATE + COUNTY
                if 'STATE' in df.columns and 'COUNTY' in df.columns:
                    df['FIPS'] = (df['STATE'].astype(str).str.zfill(2) + df['COUNTY'].astype(str).str.zfill(3))
                    zip_col = 'ZCTA5' if 'ZCTA5' in df.columns else 'ZIP'
                    if zip_col in df.columns:
                        df['ZIP'] = df[zip_col].astype(str).str.zfill(5)
                        result = df[['ZIP', 'FIPS']].drop_duplicates()
                        if not result.empty:
                            return result
            except Exception as e:
                continue
        
        # If all sources fail, return empty DataFrame
        return pd.DataFrame(columns=['ZIP', 'FIPS'])
    except Exception as e:
        return pd.DataFrame(columns=['ZIP', 'FIPS'])

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

def load_traveler_data_from_zip(df_zip_travelers: pd.DataFrame, df_zip_fips: pd.DataFrame) -> pd.DataFrame:
    """
    Load traveler data at zip code level and map to FIPS codes.
    
    Args:
        df_zip_travelers: DataFrame with columns 'zip' (or 'zipcode'), 'date', 'expected_travelers' (or 'travelers')
        df_zip_fips: DataFrame with columns 'ZIP' and 'FIPS' mapping
        
    Returns:
        DataFrame with columns 'county_fips', 'date', 'expected_travelers' (aggregated from zip codes)
    """
    if df_zip_travelers.empty or df_zip_fips.empty:
        return pd.DataFrame()
    
    # Normalize column names
    zip_col = None
    for col in df_zip_travelers.columns:
        if col.lower() in ['zip', 'zipcode', 'zip_code', 'postal_code']:
            zip_col = col
            break
    
    if zip_col is None:
        st.error("❌ Traveler data must contain a zip code column (zip, zipcode, zip_code, or postal_code)")
        return pd.DataFrame()
    
    travelers_col = None
    for col in df_zip_travelers.columns:
        if col.lower() in ['expected_travelers', 'travelers', 'traveler_count', 'count']:
            travelers_col = col
            break
    
    if travelers_col is None:
        st.error("❌ Traveler data must contain a travelers column (expected_travelers, travelers, traveler_count, or count)")
        return pd.DataFrame()
    
    date_col = None
    for col in df_zip_travelers.columns:
        if col.lower() in ['date', 'travel_date', 'day']:
            date_col = col
            break
    
    if date_col is None:
        st.error("❌ Traveler data must contain a date column (date, travel_date, or day)")
        return pd.DataFrame()
    
    # Normalize zip codes to 5-digit strings
    df_zip_travelers = df_zip_travelers.copy()
    df_zip_travelers[zip_col] = df_zip_travelers[zip_col].astype(str).str.zfill(5)
    
    # Merge with zip-to-FIPS mapping
    df_merged = df_zip_travelers.merge(
        df_zip_fips,
        left_on=zip_col,
        right_on='ZIP',
        how='inner'
    )
    
    if df_merged.empty:
        st.warning("⚠️ No matching zip codes found between traveler data and FIPS mapping")
        return pd.DataFrame()
    
    # Aggregate by FIPS and date (sum travelers from all zip codes in a county)
    df_aggregated = df_merged.groupby(['FIPS', date_col])[travelers_col].sum().reset_index()
    df_aggregated.columns = ['county_fips', 'date', 'expected_travelers']
    
    # Ensure date is string format
    df_aggregated['date'] = df_aggregated['date'].astype(str)
    
    return df_aggregated

def generate_zip_code_traveler_data(county_fips_list: list, start_date: str, days: int = 7, df_zip_fips: pd.DataFrame = None) -> pd.DataFrame:
    """
    Generate dummy traveler data at zip code level for zip codes in the specified counties.
    
    Args:
        county_fips_list: List of FIPS county codes
        start_date: Start date in YYYY-MM-DD format
        days: Number of days to generate data for
        df_zip_fips: Optional zip-to-FIPS mapping DataFrame. If None, will try to load it.
        
    Returns:
        DataFrame with columns 'zip', 'date', 'expected_travelers'
    """
    import random
    from datetime import datetime, timedelta
    
    # Load zip-to-FIPS mapping if not provided
    if df_zip_fips is None or df_zip_fips.empty:
        df_zip_fips = load_zip_to_fips_mapping()
    
    if df_zip_fips.empty:
        st.warning("⚠️ Could not load zip-to-FIPS mapping. Cannot generate zip code data.")
        return pd.DataFrame()
    
    # Normalize FIPS codes to 5-digit strings
    county_fips_set = set(str(fips).zfill(5) for fips in county_fips_list)
    
    # Filter zip codes that belong to the affected counties
    df_zip_fips_filtered = df_zip_fips[df_zip_fips['FIPS'].isin(county_fips_set)].copy()
    
    if df_zip_fips_filtered.empty:
        st.warning(f"⚠️ No zip codes found for counties: {county_fips_list}")
        return pd.DataFrame()
    
    # Get unique zip codes
    zip_codes = df_zip_fips_filtered['ZIP'].unique().tolist()
    
    start = datetime.strptime(start_date, '%Y-%m-%d')
    data = []
    
    # Generate data for each zip code
    for zip_code in zip_codes:
        # Base travelers per zip code (realistic range: 50-5000)
        # Smaller than county-level since zip codes are smaller geographic areas
        base_travelers = random.randint(50, 5000)
        
        for day_offset in range(days):
            date = start + timedelta(days=day_offset)
            # Add some daily variation (±25% for more variation at zip level)
            daily_variation = random.uniform(0.75, 1.25)
            travelers = max(1, int(base_travelers * daily_variation))  # Ensure at least 1
            
            data.append({
                'zip': zip_code,
                'date': date.strftime('%Y-%m-%d'),
                'expected_travelers': travelers
            })
    
    df_result = pd.DataFrame(data)
    
    # Add some summary info
    if not df_result.empty:
        st.info(f"📊 Generated data for {len(zip_codes)} zip codes across {len(county_fips_set)} counties")
    
    return df_result

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
            
            # Data source selection
            data_source = st.radio(
                "Traveler Data Source",
                ["Load from Zip Code CSV", "Generate Dummy Zip Code Data", "Generate Dummy County Data"],
                help="Choose to load real zip code data or generate dummy data for testing"
            )
            
            df_travelers = pd.DataFrame()
            df_zip_travelers = pd.DataFrame()  # Store original zip-level data for scenario analysis
            df_zip_fips = pd.DataFrame()  # Store zip-to-FIPS mapping for scenario analysis
            
            if data_source == "Generate Dummy Zip Code Data":
                st.markdown("**Generate dummy traveler data at zip code level for affected counties**")
                days_ahead = st.slider("Days to analyze", 1, 14, 7, help="Number of days from start date to analyze", key="zip_days")
                
                with st.spinner("Loading zip-to-FIPS mapping and generating zip code data..."):
                    # Load zip-to-FIPS mapping
                    df_zip_fips = load_zip_to_fips_mapping()
                    
                    if not df_zip_fips.empty:
                        affected_fips = df_counties['county_fips'].tolist()
                        df_zip_travelers = generate_zip_code_traveler_data(affected_fips, date, days_ahead, df_zip_fips)
                        
                        if not df_zip_travelers.empty:
                            # Map zip codes to FIPS for visualization
                            df_travelers = load_traveler_data_from_zip(df_zip_travelers, df_zip_fips)
                            st.success(f"✅ Generated zip code data: {df_zip_travelers['zip'].nunique()} zip codes → {df_travelers['county_fips'].nunique()} counties")
                            
                            # Show preview
                            with st.expander("📋 Preview generated zip code data"):
                                st.dataframe(df_zip_travelers.head(20))
                            
                            # Show download option
                            csv_zip_data = df_zip_travelers.to_csv(index=False)
                            st.download_button(
                                "Download Zip Code Data (CSV)",
                                csv_zip_data,
                                f"zip_travelers_{track_id}_{date}.csv",
                                "text/csv",
                                key="download_zip_data"
                            )
                        else:
                            st.warning("⚠️ Could not generate zip code data. Check zip-to-FIPS mapping.")
                    else:
                        st.warning("⚠️ Could not load zip-to-FIPS mapping. Please try uploading a mapping file.")
                        mapping_file = st.file_uploader(
                            "Upload zip-to-FIPS mapping CSV",
                            type=['csv'],
                            key="zip_fips_mapping_gen",
                            help="CSV with columns: 'zip' (or 'ZIP') and 'fips' (or 'FIPS')"
                        )
                        
                        if mapping_file is not None:
                            df_zip_fips = pd.read_csv(mapping_file)
                            zip_col = [c for c in df_zip_fips.columns if 'zip' in c.lower()][0] if any('zip' in c.lower() for c in df_zip_fips.columns) else None
                            fips_col = [c for c in df_zip_fips.columns if 'fips' in c.lower()][0] if any('fips' in c.lower() for c in df_zip_fips.columns) else None
                            
                            if zip_col and fips_col:
                                df_zip_fips = df_zip_fips[[zip_col, fips_col]].copy()
                                df_zip_fips.columns = ['ZIP', 'FIPS']
                                df_zip_fips['ZIP'] = df_zip_fips['ZIP'].astype(str).str.zfill(5)
                                df_zip_fips['FIPS'] = df_zip_fips['FIPS'].astype(str).str.zfill(5)
                                
                                affected_fips = df_counties['county_fips'].tolist()
                                df_zip_travelers = generate_zip_code_traveler_data(affected_fips, date, days_ahead, df_zip_fips)
                                
                                if not df_zip_travelers.empty:
                                    df_travelers = load_traveler_data_from_zip(df_zip_travelers, df_zip_fips)
                                    st.success(f"✅ Generated zip code data: {df_zip_travelers['zip'].nunique()} zip codes → {df_travelers['county_fips'].nunique()} counties")
            
            elif data_source == "Load from Zip Code CSV":
                st.markdown("**Upload CSV with zip code level traveler data**")
                st.info("💡 **Expected format:** CSV with columns: `zip` (or `zipcode`), `date` (YYYY-MM-DD), `expected_travelers` (or `travelers`)")
                
                uploaded_file = st.file_uploader(
                    "Choose CSV file",
                    type=['csv'],
                    help="Upload a CSV file with zip code, date, and traveler count columns"
                )
                
                if uploaded_file is not None:
                    try:
                        df_zip_travelers = pd.read_csv(uploaded_file)
                        st.success(f"✅ Loaded {len(df_zip_travelers)} rows from CSV")
                        
                        # Show preview
                        with st.expander("📋 Preview uploaded data"):
                            st.dataframe(df_zip_travelers.head(10))
                        
                        # Load zip-to-FIPS mapping
                        with st.spinner("Loading zip code to FIPS mapping..."):
                            df_zip_fips = load_zip_to_fips_mapping()
                        
                        if not df_zip_fips.empty:
                            st.success(f"✅ Loaded {len(df_zip_fips)} zip-to-FIPS mappings")
                            
                            # Map zip codes to FIPS
                            with st.spinner("Mapping zip codes to FIPS codes..."):
                                df_travelers = load_traveler_data_from_zip(df_zip_travelers, df_zip_fips)
                            
                            if not df_travelers.empty:
                                st.success(f"✅ Mapped to {df_travelers['county_fips'].nunique()} counties")
                                
                                # Show mapping summary
                                matched_zips = len(df_zip_travelers.merge(
                                    df_zip_fips,
                                    left_on=df_zip_travelers.columns[df_zip_travelers.columns.str.lower().str.contains('zip')][0] if any(df_zip_travelers.columns.str.lower().str.contains('zip')) else None,
                                    right_on='ZIP',
                                    how='inner'
                                ))
                                st.info(f"📊 Matched {matched_zips} zip code records to counties")
                            else:
                                st.warning("⚠️ No traveler data could be mapped to counties. Check zip code format.")
                        else:
                            # Allow manual upload of zip-to-FIPS mapping
                            st.warning("⚠️ Could not load zip-to-FIPS mapping from public source")
                            st.markdown("**Upload zip-to-FIPS mapping CSV**")
                            mapping_file = st.file_uploader(
                                "Upload zip-to-FIPS mapping CSV",
                                type=['csv'],
                                key="zip_fips_mapping",
                                help="CSV with columns: 'zip' (or 'ZIP') and 'fips' (or 'FIPS')"
                            )
                            
                            if mapping_file is not None:
                                df_zip_fips = pd.read_csv(mapping_file)
                                # Normalize column names
                                zip_col = [c for c in df_zip_fips.columns if 'zip' in c.lower()][0] if any('zip' in c.lower() for c in df_zip_fips.columns) else None
                                fips_col = [c for c in df_zip_fips.columns if 'fips' in c.lower()][0] if any('fips' in c.lower() for c in df_zip_fips.columns) else None
                                
                                if zip_col and fips_col:
                                    df_zip_fips = df_zip_fips[[zip_col, fips_col]].copy()
                                    df_zip_fips.columns = ['ZIP', 'FIPS']
                                    df_zip_fips['ZIP'] = df_zip_fips['ZIP'].astype(str).str.zfill(5)
                                    df_zip_fips['FIPS'] = df_zip_fips['FIPS'].astype(str).str.zfill(5)
                                    
                                    with st.spinner("Mapping zip codes to FIPS codes..."):
                                        df_travelers = load_traveler_data_from_zip(df_zip_travelers, df_zip_fips)
                                    
                                    if not df_travelers.empty:
                                        st.success(f"✅ Mapped to {df_travelers['county_fips'].nunique()} counties")
                    except Exception as e:
                        st.error(f"❌ Error loading CSV: {e}")
                        st.info("💡 Make sure your CSV has the correct format: zip, date, expected_travelers")
            
            else:  # Generate dummy data
                days_ahead = st.slider("Days to analyze", 1, 14, 7, help="Number of days from start date to analyze")
                
                with st.spinner("Generating traveler data..."):
                    affected_fips = df_counties['county_fips'].tolist()
                    df_travelers = generate_traveler_data(affected_fips, date, days_ahead)
                
                st.success(f"✅ Generated traveler data for {len(affected_fips)} counties over {days_ahead} days")
            
            if df_travelers.empty:
                st.warning("⚠️ No traveler data available. Please load zip code data or generate dummy data.")
            
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
                        scenario_start = scenario_date.strftime('%Y-%m-%d')
                        
                        # Handle scenario data based on original data source
                        if (data_source in ["Load from Zip Code CSV", "Generate Dummy Zip Code Data"] and 
                            not df_zip_travelers.empty and not df_zip_fips.empty):
                            # For zip code data, adjust dates but keep same zip-to-FIPS mapping
                            # We need to shift dates in the original zip data
                            df_zip_travelers_scenario = df_zip_travelers.copy()
                            # Calculate date shift
                            original_start = datetime.strptime(date, '%Y-%m-%d')
                            scenario_start_dt = datetime.strptime(scenario_start, '%Y-%m-%d')
                            date_shift = (scenario_start_dt - original_start).days
                            
                            # Shift dates
                            date_col_name = [c for c in df_zip_travelers.columns if c.lower() in ['date', 'travel_date', 'day']][0]
                            df_zip_travelers_scenario[date_col_name] = pd.to_datetime(df_zip_travelers_scenario[date_col_name]) + pd.Timedelta(days=date_shift)
                            df_zip_travelers_scenario[date_col_name] = df_zip_travelers_scenario[date_col_name].dt.strftime('%Y-%m-%d')
                            
                            # Map to FIPS
                            df_travelers_scenario = load_traveler_data_from_zip(df_zip_travelers_scenario, df_zip_fips)
                        else:
                            # Generate dummy data for scenario
                            days_ahead = len(df_travelers['date'].unique()) if not df_travelers.empty else 7
                            affected_fips = df_counties['county_fips'].tolist()
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

