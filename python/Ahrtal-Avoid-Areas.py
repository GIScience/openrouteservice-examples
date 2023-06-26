# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:light
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.14.6
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# # Disaster aware routing with openrouteservice

# ### Install and import necessary libraries
#
# For this exercise we use the following R libraries:
#
# -   `dplyr` for the ease of manipulating data.frame classes Wickham H, François R, Henry L, Müller K, Vaughan D (2023). *dplyr: A Grammar of Data Manipulation*. R package version 1.1.2, <https://CRAN.R-project.org/package=dplyr>.
# -   `sf` the dplyr equivalent to work with spatial data.frames. Pebesma, E., & Bivand, R. (2023). Spatial Data Science: With Applications in R (1st ed.). Chapman and Hall/CRC. <https://doi.org/10.1201/9780429459016>
# -   `openrouteservice` is the package that provides a user firendly R interface to the openrouteservice API. The package is not published on CRAN, therefore we install it via the `devtools` package from github.
# -   `mapview` is a easy to use library to create interactive maps. Appelhans T, Detsch F, Reudenbach C, Woellauer S (2022). *mapview: Interactive Viewing of Spatial Data in R*. R package version 2.11.0, <https://CRAN.R-project.org/package=mapview>.

from openrouteservice import client
from openrouteservice.exceptions import ApiError
import geopandas as gpd
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import folium
from branca.colormap import linear
from shapely.geometry import Point, mapping
from ipyleaflet import Map, DrawControl, AwesomeIcon, Marker, GeoData, basemaps, LayersControl, Icon, GeoJSON

# ### Set up openrouteservice

# insert your ORS api key
api_key = ''
ors = client.Client(key=api_key)

# ## Simple route with avoid area  

# ### Normal route from disaster relief stagin area towards Bad Neuanahr-Ahrweiler 

# +
start_point = (6.943241, 50.334265)
destination = (7.119166, 50.548979)

# Define parameters for request to openrouteservice
request_params = {'coordinates': [start_point, destination],
                 'format_out': 'geojson',
                 'profile': 'driving-hgv',
                 'preference': 'recommended',
                 'instructions': False}
# -

# Send request to ORS

route_directions = ors.directions(**request_params)

# Convert ORS response to GeoDataFrame

route = gpd.GeoDataFrame().from_features(route_directions).set_crs(epsg=4326)

route.explore()

# Plot route on map

# avoid_polygons = {
#     'type': 'FeatureCollection',
#     'features': []
# }

# def handle_draw(self, action, geo_json):
#     """Do something with the GeoJSON when it's drawn on the map"""    
#     avoid_polygons['features'].append(geo_json)

# m = Map(center=(7, 50.4), zoom=10, scroll_wheel_zoom=True, basemap=basemaps.CartoDB.Positron)
#
# route_layer = GeoData(geo_dataframe = route,
#                         name = 'Route Normal', 
#                         style={"color": "red",
#                                "opacity": 0.5})
# m.add_layer(route_layer)
# draw_control = DrawControl()
# draw_control.polygon = {
#     "shapeOptions": {
#         "fillColor": "#6be5c3",
#         "color": "#6be5c3",
#         "fillOpacity": 1.0
#     },
#     "drawError": {
#         "color": "#dd253b",
#         "message": "Oups!"
#     },
#     "allowIntersection": False
# }
# draw_control.on_draw(handle_draw)
# m.add_control(draw_control)
# m

# #### Send request again with avoided polygon
#

# request_params['options'] = {'avoid_polygons': avoid_polygons['features'][0]['geometry']}
# route_directions_avoided = ors.directions(**request_params)
# route_avoided = gpd.GeoDataFrame().from_features(route_directions_avoided)

# m = Map(center=start_point[::-1], zoom=10, scroll_wheel_zoom=True, basemap=basemaps.CartoDB.Positron)
#
# route_layer = GeoData(geo_dataframe = route,
#                         name = 'Route Normal', 
#                         style={"color": "green",
#                                "opacity": 0.5})
# m.add_layer(route_layer)
#
# route_avoided_layer = GeoData(geo_dataframe = route_avoided,
#                         name = 'Route Avoided', 
#                         style={"color": "red",
#                                "opacity": 0.5})
# m.add_layer(route_avoided_layer)
#
# avoided_polygon = GeoData(geo_dataframe = gpd.GeoDataFrame().from_features(avoid_polygons),
#                         name = 'Avoided polygon', 
#                         style={"color": "blue", "fillColor": None, 'alpha': 0, "fillOpacity": 1,
#                                "opacity": 0.5})
# m.add_layer(avoided_polygon)
#
# m
# ### Load affected roads and places 

# The basecamp where the rescue helpers were stationed is the Nürburgring

basecamp_coordinates = (6.943488121032716, 50.33214859082482)
basecamp = gpd.GeoDataFrame({'geometry': [Point(basecamp_coordinates)], 'name': ['Base Camp']}, crs="epsg:4326")

affected_roads_bridges = gpd.read_file("../resources/data/ahrtal/affected_roads.gpkg")
affected_roads_bridges['id'] = affected_roads_bridges.index
affected_places = gpd.read_file("../resources/data/ahrtal/affected_places.gpkg")


# Buffer the damaged bridges and roads by 2 meters to convert them into polygons

affected_roads_bridges_union = affected_roads_bridges.copy()
affected_roads_bridges_union.geometry = affected_roads_bridges_union.geometry.to_crs('25832').buffer(2).to_crs('4326').make_valid()
affected_roads_bridges_union = affected_roads_bridges_union.dissolve()
affected_roads_bridges_union.geometry = affected_roads_bridges_union.make_valid()

m = affected_roads_bridges.explore(color='red',
                                  tooltip=['id'])
affected_places.explore(m=m, 
                        color='blue')

# ### Calculate routes from base camp to the affected places 

# First, we need to add the affected roads and bridges to the quer parameters as areas to avoid.

request_params_flood = request_params.copy()
request_params_flood['options'] = {'avoid_polygons': mapping(affected_roads_bridges_union.make_valid().geometry[0])}

# +
normal_routes = []
avoiding_routes = []

for i, p in affected_places.iterrows():

    # Calculate route before the flood
    request_params['coordinates'] = [basecamp_coordinates, (p.geometry.x, p.geometry.y)]
    directions_normal = ors.directions(**request_params)
    directions_normal_df = gpd.GeoDataFrame().from_features(directions_normal)
    directions_normal_df['name'] = p['name']
    directions_normal_df['id'] = i

    # Calculate route after the flood
    try:
        request_params_flood['coordinates'] = [basecamp_coordinates, (p.geometry.x, p.geometry.y)]
        directions_flood = ors.directions(**request_params_flood)
        directions_flood_df = gpd.GeoDataFrame().from_features(directions_flood)
        directions_flood_df['name'] = p['name']
        directions_flood_df['id'] = i
    except ApiError as e:
        print(e)
        print(f"No route found for {p['name']}")
        continue
    
    avoiding_routes.append(directions_flood_df)    
    normal_routes.append(directions_normal_df)

# -

normal_routes_df = gpd.GeoDataFrame(pd.concat(normal_routes)).set_crs(epsg=4326).set_index('id')
avoiding_routes_df = gpd.GeoDataFrame(pd.concat(avoiding_routes)).set_crs(epsg=4326).set_index('id')

normal_routes_df['duration'] = normal_routes_df.summary.map(lambda x: x['duration'])
avoiding_routes_df['duration'] = avoiding_routes_df.summary.map(lambda x: x['duration'])

avoiding_routes_df = avoiding_routes_df.join(normal_routes_df[['duration']], lsuffix='_avoid')
avoiding_routes_df['duration_difference'] = (avoiding_routes_df.duration_avoid - avoiding_routes_df.duration) / 60. 
avoiding_routes_df['duration_difference_%'] = (avoiding_routes_df.duration_avoid - avoiding_routes_df.duration) / avoiding_routes_df.duration_avoid * 100. 

fig, axes = plt.subplots(1,1, figsize=(15, 5))
sns.barplot(data=avoiding_routes_df.sort_values('duration_difference_%', ascending=False), 
            x='name', y='duration_difference_%', color='lightblue',
           ax=axes)
g = plt.xticks(rotation = 45, ha='right') # Rotates X-Axis Ticks by 45-degrees

affected_places_dur = affected_places.join(avoiding_routes_df[['duration_difference', 'duration_difference_%']])
#affected_places_dur = affected_places_dur.loc[affected_places_dur['name'] != 'Hönningen']

# +
place_name = 'Hönningen'
m = affected_places_dur.explore(column='duration_difference_%', 
                            tooltip=['name', 'duration_difference_%','duration_difference'],
                            popup=True,  # show all values in popup (on click)
                            tiles="CartoDB positron",  # use "CartoDB positron" tiles
                            cmap='Reds', vmin=0, vmax=affected_places_dur['duration_difference_%'].max(),
                            marker_kwds=dict(radius=10, fill=True))

basecamp.explore(
    m=m,
    marker_type='marker',
    marker_kwds={'icon': folium.map.Icon(icon='people')},
    color="orange", 
    #marker_kwds=dict(radius=10, fill=True)
)
avoiding_routes_df.loc[avoiding_routes_df['name'] == place_name].explore(
    m=m,
    highlight=True,
    name='Route after flood',
    legend=True,
    tooltip=['name', 'duration'],
    popup=True,
    color="lightpink")
#normal_routes_df.loc[normal_routes_df['name'] == place_name].explore(
#    m=m,
#    name='Route before flood',
#    tooltip=['name', 'duration'],
#    popup=True,
#    color="green")
affected_roads_bridges.explore(m=m, 
                               color='red',
                                 tooltip=['id'],
 
                              )
m
# -

# ## Isochrones

isochrones_parameters = {
    'locations': [basecamp_coordinates],
    'profile': 'driving-car',
    'range_type': 'time',
    'range': [60 * 60],  # 900/60 = 15 minutes # Get population count for isochrones
}

isochrones = ors.isochrones(**isochrones_parameters)
isochrones_df = gpd.GeoDataFrame.from_features(isochrones).set_crs(epsg=4326)

# +
m = affected_places.explore(tooltip=['name'],
                            popup=True,  # show all values in popup (on click)
                            tiles="CartoDB positron", 
                            color='red',
                            marker_kwds=dict(radius=10, fill=True))

basecamp.explore(
    m=m,
    marker_type='marker',
    marker_kwds={'icon': folium.map.Icon(icon='people')},
    color="orange", 
    #marker_kwds=dict(radius=10, fill=True)
)
affected_roads_bridges.explore(m=m, 
                               color='red',
                                 tooltip=['id'],
 
                              )
isochrones_df.explore(m=m)
# -


