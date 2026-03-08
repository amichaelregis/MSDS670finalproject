# -*- coding: utf-8 -*-
"""
================================================================================
PROJECT: Evolution of US Residential Broadband & Socio-Economic Correlation
COURSE:  MSDS 670 - Data Visualization
AUTHOR:  Amal Michael
DATE:    March 8, 2026

PROGRAM DESCRIPTION:
This script engineers an interactive, animated spatio-temporal choropleth map 
to visualize the "Digital Divide" across the Contiguous United States. 

KEY FEATURES:
1. DATA INTEGRATION: Synchronizes longitudinal broadband adoption data (Tier 4: 
   100+ Mbps) with socio-economic indicators, merging USDA Historical Income 
   baselines (2022) and SAIPE Estimates (2024).
   
2. GEOSPATIAL MERGE: Processes US Census Bureau TIGER/Line shapefiles. 
   The Pandas DF is merged with the Geopandas DF with shapefiles.

3. DYNAMIC TOOLTIPS: Implements conditional logic to display year-specific 
   economic data, mapping Median Household Income to the corresponding 
   broadband adoption rate in real-time as the animation progresses.

4. ANIMATION & UI: Utilizes Plotly’s animation engine to transition through 
   yearly snapshots (2018–2024), utilizing a categorical color scale 
   to highlight saturation milestones in residential high-speed internet.

INPUTS:
- county_tiers_201406_202406.csv : Longitudinal broadband tier data
- unemployment_income.csv        : USDA historical income data
- saipe_2024.csv                 : Small Area Income and Poverty Estimates
- tl_2024_us_county.shp          : US Census Bureau county boundaries

OUTPUTS:
- Interactive HTML file (MSDS670_Broadband_Project_Final.html)
- Automated browser rendering of the final visualization
================================================================================
"""
# %% [0] Imports
import pandas as pd
import geopandas as gpd
import json
import plotly.express as px
import plotly.io as pio

# Force the plot to open in the default web browser
pio.renderers.default = "browser"

# %% [1] Data Processing & Integration
print("Step 1: Processing Broadband and Income datasets...")

# Load Primary Broadband Data
df = pd.read_csv("county_tiers_201406_202406.csv", encoding="latin1")
df = df[df["Year"] >= 2018].copy()
df["FIPS"] = df["FIPS"].astype(str).str.zfill(5)

# --- Socio-Economic Data Integration ---
try:
    # 1. Load USDA Historical Data (providing the 2022 Baseline)
    df_usda = pd.read_csv('unemployment_income.csv', skiprows=4, encoding="latin1")
    df_usda['FIPS'] = df_usda['FIPS_Code'].astype(str).str.zfill(5)
    df_usda['Inc22'] = pd.to_numeric(df_usda['Median_Household_Income_2022'].astype(str).str.replace(r'[$,]', '', regex=True), errors='coerce')
    
    # 2. Load SAIPE 2024 Estimates
    df_24 = pd.read_csv('saipe_2024.csv', skiprows=3, encoding="latin1")
    df_24['FIPS'] = df_24['State FIPS Code'].astype(str).str.zfill(2) + df_24['County FIPS Code'].astype(str).str.zfill(3)
    df_24['Inc24'] = pd.to_numeric(df_24['Median Household Income'].astype(str).str.replace(r'[$,]', '', regex=True), errors='coerce')

    # 3. Join Datasets
    df = df.merge(df_usda[['FIPS', 'Inc22']], on='FIPS', how='left')
    df = df.merge(df_24[['FIPS', 'Inc24']], on='FIPS', how='left')
    
    # Define Dynamic Tooltip Label for Income
    def get_inc_label(row):
        val = row['Inc24'] if row['Year'] == 2024 else row['Inc22']
        if pd.isnull(val) or val <= 0: return "N/A"
        label = "(2024 Est)" if row['Year'] == 2024 else "(2022 Baseline)"
        return f"${val:,.0f} {label}"

    df['Inc_Display'] = df.apply(get_inc_label, axis=1)
except Exception as e:
    print(f"Data Integration Warning: {e}")
    df['Inc_Display'] = "Data N/A"

# Final Cleanup
df["Tier_4"] = df["Tier_4"].replace(-999, 0).fillna(0)
res_unit_col = "Housing_Units"
if res_unit_col in df.columns:
    df[res_unit_col] = df[res_unit_col].fillna(0).astype(int)
else:
    # Placeholder if column is missing to prevent script error
    df[res_unit_col] = 0

# Filter for Contiguous US (Excluding AK, HI, and Territories)
excluded = ['02','15','60','66','69','72','78']
df = df[~df["FIPS"].str[:2].isin(excluded)]

# %% [2] Geometry Processing (Performance Optimized)
print("Step 2: Processing and simplifying map geometry...")
counties = gpd.read_file("tl_2024_us_county.shp")
counties = counties.to_crs(epsg=4326)
counties = counties[~counties["STATEFP"].isin(excluded)]

# Simplify geometry (0.02) to ensure smooth browser rendering
counties["geometry"] = counties["geometry"].simplify(0.02)
counties_json = json.loads(counties.to_json())

# %% [3] Merging Map and Data
df_merged = counties.merge(df, left_on="GEOID", right_on="FIPS")

# State Name Mapping for Tooltips
fips_to_state = {
    '01':'Alabama','04':'Arizona','05':'Arkansas','06':'California','08':'Colorado','09':'Connecticut',
    '10':'Delaware','11':'DC','12':'Florida','13':'Georgia','16':'Idaho','17':'Illinois','18':'Indiana',
    '19':'Iowa','20':'Kansas','21':'Kentucky','22':'Louisiana','23':'Maine','24':'Maryland','25':'Massachusetts',
    '26':'Michigan','27':'Minnesota','28':'Mississippi','29':'Missouri','30':'Montana','31':'Nebraska',
    '32':'Nevada','33':'New Hampshire','34':'New Jersey','35':'New Mexico','36':'New York','37':'North Carolina',
    '38':'North Dakota','39':'Ohio','40':'Oklahoma','41':'Oregon','42':'Pennsylvania','44':'Rhode Island',
    '45':'South Carolina','46':'South Dakota','47':'Tennessee','48':'Texas','49':'Utah','50':'Vermont',
    '51':'Virginia','53':'Washington','54':'West Virginia','55':'Wisconsin','56':'Wyoming'
}
df_merged['State_Name'] = df_merged['STATEFP'].map(fips_to_state)
df_merged = df_merged.sort_values(["Year", "FIPS"])

# Formatting labels for the Adoption Rate Legend
def get_rate_label(val):
    labels = {0:"0%", 1:"0 to 20%", 2:"20 to 40%", 3:"40 to 60%", 4:"60 to 80%", 5:"80%+"}
    return labels.get(val, str(val))
df_merged["Adoption_Rate_Label"] = df_merged["Tier_4"].apply(get_rate_label)

# %% [4] Build Plotly Animation
print("Step 3: Generating Visual Objects...")
fig = px.choropleth(
    df_merged,
    geojson=counties_json,
    locations="FIPS",
    featureidkey="properties.GEOID",
    color="Tier_4",
    animation_frame="Year",
    scope="usa",
    color_continuous_scale="Blues",
    range_color=[0, 5],
    hover_name="NAMELSAD",
    hover_data={
        "State_Name": True, 
        "Adoption_Rate_Label": True, 
        "Inc_Display": True, 
        res_unit_col: ":,", 
        "Year": True, 
        "Tier_4": False, 
        "FIPS": False
    }
)

# %% [5] Final Layout & Annotations
# 1. Top Header Annotation
fig.add_annotation(
    text="<b>US Residential Broadband: 100+ Mbps Adoption (2018–2024)</b>" + 
         "<br><span style='font-size:14px; color:grey;'>Analyzing Adoption Saturation vs. Median Household Income</span>",
    xref="paper", yref="paper", 
    x=0.5, y=1.15, 
    xanchor="center", yanchor="bottom",
    showarrow=False, font=dict(size=20), align="center",
    bgcolor="white", bordercolor="navy", borderwidth=2, borderpad=10
)

# 2. Bottom-Left Insight Box
insight_text = (
    "<b>Data Insights:</b><br>"
    "• Darker blue indicates higher adoption (>80%).<br>"
    "• 2018-2023 Income uses 2022 Census Baseline.<br>"
    "• 2024 Income uses SAIPE 2024 Estimates.<br>"
    "• Gray areas indicate missing or excluded data."
)

fig.add_annotation(
    text=insight_text,
    xref="paper", yref="paper",
    x=0.01, y=0.05, 
    xanchor="left", yanchor="bottom",
    showarrow=False,
    font=dict(size=11, color="black"),
    align="left",
    bgcolor="rgba(255, 255, 255, 0.9)",
    bordercolor="navy",
    borderwidth=1,
    borderpad=8
)

# Formatting Tooltip Appearance
tooltip = (
    "<b>%{hovertext}</b><br>"
    "State: %{customdata[0]}<br>"
    "Year: %{customdata[4]}<br><br>"
    "Median Income: %{customdata[2]}<br>"
    "Housing Units: %{customdata[3]}<br>"
    "Adoption: %{customdata[1]}"
    "<extra></extra>"
)
fig.update_traces(hovertemplate=tooltip)
for frame in fig.frames:
    frame.data[0].hovertemplate = tooltip

fig.update_layout(
    coloraxis_colorbar=dict(
        tickvals=[0,1,2,3,4,5], 
        ticktext=["0%","20%","40%","60%","80%","80%+"], 
        title="Adoption %"
    ),
    # Increased top margin to prevent header from being cut off
    margin={"r":0, "t":160, "l":0, "b":50} 
)

# %% [6] Execution & File Output
fig.show()
fig.write_html("MSDS670_Broadband_Project_Final.html", include_plotlyjs='cdn')
print("Complete! Visualization exported to 'MSDS670_Broadband_Project_Final.html'.")