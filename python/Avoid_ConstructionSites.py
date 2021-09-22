# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:light
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.12.0
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# # Avoiding construction sites dynamically

# In this example, we'd like to showcase how to use the [directions API][directions] and to avoid a number of
# construction sites while routing.
#
# The challenge here is to prepare the data appropriately and construct a reasonable GET request.
#
# [directions]: https://openrouteservice.org/documentation/#/reference/directions/directions/directions-service

import folium
import pyproj
import requests
from openrouteservice import client
from shapely import geometry
from shapely.geometry import Point, LineString, Polygon, MultiPolygon

# Rostock is beautiful, but, as in most other pan-European cities, there are a lot of construction sites.
# Wouldn't it be great if we could plan our trip avoiding these sites and consequently save lots of time!?

# ## Construction sites in Rostock

# We take the [open data](https://www.opendata-hro.de/de/dataset/baustellen) from the Rostock authorities.
# It's hard (to impossible) to find construction site polygons, so these are points, and we need to buffer them to
# a polygon to be able to avoid them when they cross a street.
#
# For the investigatory in you: yes, no CRS is specified on the link (shame on you, Rostock!).
# It's fair enough to assume it comes in WGS84 lat/long though (my reasoning:
# they show Leaflet maps plus GeoJSON is generally a web exchange format, and many web clients (Google Maps, Leaflet)
# won't take CRS other than WGS84).
# Since degrees are not the most convenient unit to work with, let's first define a function which does the buffering job
# with UTM32N projected coordinates:

# +
url = 'https://geo.sv.rostock.de/download/opendata/baustellen/baustellen.json'

def create_buffer_polygon(point_in, resolution=10, radius=10):

    sr_wgs = pyproj.Proj(init='epsg:4326')
    sr_utm = pyproj.Proj(init='epsg:32632') # WGS84 UTM32N
    point_in_proj = pyproj.transform(sr_wgs, sr_utm, *point_in) # unpack list to arguments
    point_buffer_proj = Point(point_in_proj).buffer(radius, resolution=resolution) # 10 m buffer

    # Iterate over all points in buffer and build polygon
    poly_wgs = []
    for point in point_buffer_proj.exterior.coords:
        poly_wgs.append(pyproj.transform(sr_utm, sr_wgs, *point)) # Transform back to WGS84

    return poly_wgs



# +
# Set up the fundamentals
api_key = 'your_key' # Individual api key
clnt = client.Client(key=api_key) # Create client with api key
rostock_json = requests.get(url).json() # Get data as JSON

map_params = {'tiles':'Stamen Toner',
              'location':([54.13207, 12.101612]),
              'zoom_start': 12}
map1 = folium.Map(**map_params)

# Populate a construction site buffer polygon list
sites_poly = []
for site_data in rostock_json['features']:
    site_coords = site_data['geometry']['coordinates']
    folium.features.Marker(list(reversed(site_coords)),
                           popup='Construction point<br>{0}'.format(site_coords)).add_to(map1)

    # Create buffer polygons around construction sites with 10 m radius and low resolution
    site_poly_coords = create_buffer_polygon(site_coords,
                                           resolution=2, # low resolution to keep polygons lean
                                           radius=10)
    sites_poly.append(site_poly_coords)

    site_poly_coords = [(y,x) for x,y in site_poly_coords] # Reverse coords for folium/Leaflet
    folium.vector_layers.Polygon(locations=site_poly_coords,
                                  color='#ffd699',
                                  fill_color='#ffd699',
                                  fill_opacity=0.2,
                                  weight=3).add_to(map1)

map1


# -

# That's a lot of construction sites in Rostock! If you dig into the `properties` of the JSON, you'll see that those
# are kept up-to-date though. Seems like an annoying place to ride a car...
#
# Anyways, as you might know, a GET request can only contain so many characters. Unfortunately, > 80 polygons are more
# than a GET can take (that's why we set `resolution = 2`).
# Because there's no POST endpoint available currently, we'll have to work around it:
#
# One sensible thing one could do, is to eliminate construction zones which are not in the immediate surrounding of the
# route of interest.
# Hence, we can request a route without construction sites, take a reasonable buffer,
# filter construction sites within the buffer and try again.
#
# Let's try this:

# +
# GeoJSON style function
def style_function(color):
    return lambda feature: dict(color=color,
                              weight=3,
                              opacity=0.5)

# Create new map to start from scratch
map_params.update({'location': ([54.091389, 12.096686]),
                   'zoom_start': 13})
map2 = folium.Map(**map_params)

# Request normal route between appropriate locations without construction sites
request_params = {'coordinates': [[12.108259, 54.081919],
                                 [12.072063, 54.103684]],
                'format_out': 'geojson',
                'profile': 'driving-car',
                'preference': 'shortest',
                'instructions': 'false',}
route_normal = clnt.directions(**request_params)
folium.features.GeoJson(data=route_normal,
                        name='Route without construction sites',
                        style_function=style_function('#FF0000'),
                        overlay=True).add_to(map2)

# Buffer route with 0.009 degrees (really, just too lazy to project again...)
route_buffer = LineString(route_normal['features'][0]['geometry']['coordinates']).buffer(0.009)
folium.features.GeoJson(data=geometry.mapping(route_buffer),
                        name='Route Buffer',
                        style_function=style_function('#FFFF00'),
                        overlay=True).add_to(map2)

# Plot which construction sites fall into the buffer Polygon
sites_buffer_poly = []
for site_poly in sites_poly:
    poly = Polygon(site_poly)
    if route_buffer.intersects(poly):
        folium.features.Marker(list(reversed(poly.centroid.coords[0]))).add_to(map2)
        sites_buffer_poly.append(poly)

map2
# -

# Finally, we can try to request a route using `avoid_polygons`, which conveniently takes a GeoJSON as input.

# +
# Add the site polygons to the request parameters
request_params['options'] = {'avoid_polygons': geometry.mapping(MultiPolygon(sites_buffer_poly))}
route_detour = clnt.directions(**request_params)

folium.features.GeoJson(data=route_detour,
                        name='Route with construction sites',
                        style_function=style_function('#00FF00'),
                        overlay=True).add_to(map2)

map2.add_child(folium.map.LayerControl())
map2
# -

# > Note: This request might fail sometime in the future, as the JSON is loaded dynamically and changes a few times
# > a week.
# > Thus the amount of sites within the buffer can exceed the GET limit (which is between 15-20 site polygons approx).
