# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:light
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.15.2
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# # Michael Moyles - Avoid Noisy Areas Using OpenRouteService Directions API

# This notebook has built upon the work of Amandus, [link](https://openrouteservice.org/example-avoid-flooded-areas-with-ors/).

# ## Preprocessing

# Inside the directory, run 'pip install -r requirements.txt' to download all the necessary packages.
#
# Included in this repository is a CSV file with sample data based on outputs from a model analysing noise complaint data in Manhattan, New York. This notebook uses noise complaints classified as 'outside' as a proxy for whether a particular coordinate is noisy. 
#
# Data Source: https://data.cityofnewyork.us/Social-Services/Noise-Complaints-in-2017-/be8n-q3nj/data

# ## Motivation

# The directions endpoint of the OpenRouteService API can be used to receive the shortest or fastest route from point A to point B. This endpoint offers the avoid_polygons feature which is suited to avoid these areas as a primary objective and setting shortest path as the secondary objective. The data points are generally clustered so overlapping polygons are merged in order to reduce API calls to the ORS server.
#
# Using this functionality, a routing service can be developed that avoids noisy areas. This can be especially important for people that are sensitive to these stimuli and wish to avoid them.

# ## Import Required Packages

import folium
import geopandas as gpd
from openrouteservice import client
import pandas as pd
from shapely.geometry import mapping, MultiPolygon, Point
from shapely.ops import unary_union

# insert your ORS api key
api_key = '5b3ce3597851110001cf6248a1fb1aae1ad345ae93bbb1ac6a8aa8de'
ors = client.Client(key=api_key)

# ## Data Inspection
# Inspecting the data stored in the CSV. The important columns are extracted, the coordinate values, the hour of the day, whether the noise complaint is on a weekday or weekend and the 'noisyness' level designated Final Noise Complaint Category. 
#
# Note:
# * The noisyness level has been normalised
# * The model outputs values for the weekend and weekday as binary [1,0]

# +
df = pd.read_csv("../resources/data/noise_data/noisy_areas.csv", names=['Longitude','Latitude','Hour','Weekday','Weekend',"Final Noise Complaint Category"], skiprows=1)

columns = df.columns

for column in columns:
    print("Column Name:", column, "\nData Type:", df[column].dtype, "\nNumber of Unique Values:", str(len(df[column].unique())))
    print(df[column].unique())
    print()
# -

# Overview of data in the CSV

df.head(20)


# ## Data Models

# ## Setup Functions

# The create_route function requests routes from the OpenRouteService Directions API. Next to the regular input (starting point, end point, profile, preference), we pass avoid_polygons as an additional option.

# +
# Function to request directions with avoided_polygon feature
def create_route(data, avoided_point_list):
    route_request = {'coordinates': data,
                        'format': 'geojson',
                        'profile': 'foot-walking',
                        'preference': 'shortest',
                        'options': {'avoid_polygons': mapping(MultiPolygon(avoided_point_list))}}
    route_directions = ors.directions(**route_request)
    return route_directions

# Function to style data
def style_function(color):
    return lambda feature: dict(color=color)


# -

# ## Analysis

# Creates a visualisation of the noisy areas on the map for every time and day using a GeoPandas dataframe and the EPSG:4326 (WGS84) coordinate reference system

geometry = [Point(xy) for xy in zip(df['Longitude'], df['Latitude'])]
gdf = gpd.GeoDataFrame(df, geometry=geometry, crs=4326)
gdf.explore()

# Specify a time and date with conditional indexing into the dataframe

# +
# Filter rows where 'noise_complain' is over 0.5, time is 17:00 and weekday is 0 (Monday)
noisy_areas = gdf[(gdf['Final Noise Complaint Category'] > 0.5) & (gdf['Hour'] == 17) & (gdf['Weekday'] == 0)].copy()

# Create a buffer of around the coordinates and display
noisy_areas['buffer_polygon'] = noisy_areas['geometry'].apply(lambda x: x.buffer(0.0002))
noisy_areas['buffer_polygon'].explore()
# -

# ## Routing
# Visualises the routing that takes place for a particular time and day. The CreateRoute function requests the shortest route from A to B for the foot-walking profile. It also avoids the areas which are included in the avoided_polygons_series. This list is empty in the beginning.
#
# To retrieve a route that does not intersect with any noisy areas, all intersecting polygons are merged. These polygons are sent to the API as areas to avoid, it then returns back the avoidance route for rendering. By merging the polygons together, instead of sending polygons for every coordinate, the package size sent to the API is much smaller. It can only handle a limited number of poylgons as areas to avoid currently.

# +
# Join clustering polygons to reduce API calls
union_poly = unary_union(noisy_areas['buffer_polygon'])

# Check if the result is a MultiPolygon
if isinstance(union_poly, MultiPolygon):
    # Convert each polygon in the MultiPolygon to a separate entry in the GeoSeries
    avoided_polygons_series = gpd.GeoSeries([poly for poly in union_poly.geoms], crs=4326)
else:
    # If it's a single Polygon, create a GeoSeries with a single element
    avoided_polygons_series = gpd.GeoSeries([union_poly], crs=4326)

# +
map = folium.Map(location=[40.721954, -74.008310], zoom_start=16)

# Coordinate that demonstrates re-routing
coordinates = [[-74.008627, 40.719967], [-74.007763, 40.724708]]

# Starting location marker (Red)
folium.map.Marker(
    location=list(reversed(coordinates[0])),
    icon=folium.Icon(color="red"),
    ).add_to(map)

# Destination marker (Blue)
folium.map.Marker(
    location=list(reversed(coordinates[1])),
    icon=folium.Icon(color="blue"),
    ).add_to(map)

try:
    # Create regular route with an empty list of areas to avoid
    optimal_route = create_route(coordinates, [])

    # Plot optimal route
    folium.features.GeoJson(
        data=optimal_route,
        name='Regular Route',
        style_function=style_function('#ff5050'), overlay=True).add_to(map)
    print('Generated regular route.')

except Exception as e:
    print(e)

# Display the noisy areas
folium.features.GeoJson(
    data=avoided_polygons_series,
    name='Noisy Area',
    overlay=True).add_to(map)

# Initialise avoidance_route as an empty string
avoidance_route = ""
try:
    avoidance_route = create_route(coordinates, avoided_polygons_series.tolist())
except Exception as e:
    print(e)

if avoidance_route != optimal_route:
    # Display the avoidance route
    folium.features.GeoJson(
        data=avoidance_route,
        name='Alternative Route',
        style_function=style_function('#006600'),
        overlay=True).add_to(map)
    print('Generated alternative route, which avoids affected areas.')

map.add_child(folium.map.LayerControl())
map
# -

# ## Export Map Views

# The following exports an interactive HTML of a map for every day and time possible for inspection. This helps to determine the correct threshold that defines an area as noisy, in the above it's the top 50%. With too high a threshold, the clusters become too large to be practically routed around and too small, the user could be routed through a noisy area.
#
# Note: This can take a while few minutes run as it runs for 48 iterations and has to merge all the coordinate level poylgons together to render them on the map

# ### Noisy Areas

for prediction_day in [0, 6]:
    # Create a map for every hour in a day (0-24)
    for prediction_hour in range(24):
        # Filter rows where noise complaints are over 0.5 for every hour and day
        noisy_areas = gdf[(gdf['Final Noise Complaint Category'] > 0.5) & (gdf['Hour'] == prediction_hour) & (gdf['Weekday'] == prediction_day)].copy()
        noisy_areas['buffer_polygon'] = noisy_areas['geometry'].apply(lambda x: x.buffer(0.0002))
        union_poly = unary_union(noisy_areas['buffer_polygon'])

        # Check if the result is a MultiPolygon
        if isinstance(union_poly, MultiPolygon):
            # Convert each polygon in the MultiPolygon to a separate entry in the GeoSeries
            avoided_polygons_series = gpd.GeoSeries([poly for poly in union_poly.geoms], crs=4326)
        else:
            # If it's a single Polygon, create a GeoSeries with a single element
            avoided_polygons_series = gpd.GeoSeries([union_poly], crs=4326)

        # Create a folium map
        map = folium.Map(location=[40.715709, -74.005092], zoom_start=14)

        # Add polygons to the map
        for polygon in avoided_polygons_series:
            folium.GeoJson(polygon).add_to(map)

        # Save the map as a HTML doc in the map_export subdirectory
        map.save(f'../resources/img/map_exports/map_noise_{prediction_day}_{prediction_hour}.html')

# ## Conclusion
# A routing service that can avoid particular areas specified by the user allows for a greater diversity of use. This type of service empowers people to find optimal pathways based on additional criteria to shortest path. For people that are sensitive to a range of stimuli, the shortest path may not be their optimal path. In this example, noisy areas are avoided in Manhattan, New York but the same concept could be expanded to optimise the user's route based on other criteria.
#
# To tackle this issue, this notebook shows how the direction feature avoid_polygons of the OpenRouteService API can be used. It allows avoiding certain areas (e.g. noisy areas) and to request the fastest or shortest route for different routes while walking. This notebook has built upon the work of Amandus, [link](https://openrouteservice.org/example-avoid-flooded-areas-with-ors/).
