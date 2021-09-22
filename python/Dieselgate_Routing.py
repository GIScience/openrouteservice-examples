# -*- coding: utf-8 -*-
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

# # Dieselgate Routing
#
# > Note: All notebooks need the [environment dependencies](https://github.com/GIScience/openrouteservice-examples#local-installation)
# > as well as an [openrouteservice API key](https://openrouteservice.org/dev/#/signup) to run
#
# From the year 2019 on, Berlin will impose the Diesel ban.
# The following streets will be affected: Leipziger Straße, Reinhardstraße, Friedrichstraße, Brückenstraße, Kapweg,
# Alt-Moabit, Stromstraße und Leonorenstraße.
#
# As a showcase, we'll have a look how the frequent visits of Angela Merkel to the German Currywurst Museum
# (solely inferred from superficial research) will change its route from 2019. You'll find remarkable similarities.

# +
from openrouteservice import client
import folium
from shapely.geometry import LineString, Polygon, mapping
from shapely.ops import cascaded_union
import time

def style_function(color): # To style data
    return lambda feature: dict(color=color,
                                opacity=0.5,
                                weight=4,)


# -

# ### Regular Route
#
# So far: The shortest route for a car from A to B.

# +
# Basic parameters
api_key = 'your_key' #https://openrouteservice.org/sign-up
ors = client.Client(key=api_key)

map_berlin = folium.Map(tiles='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
                        attr='&copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap contributors</a>',
                        location=([52.516586, 13.381047]),
                        zoom_start=13.5) # Create map

popup_route = "<h4>{0} route</h4><hr>" \
             "<strong>Duration: </strong>{1:.1f} mins<br>" \
             "<strong>Distance: </strong>{2:.3f} km"

# Request route
coordinates = [[13.372582, 52.520295], [13.391476, 52.508856]]
direction_params = {'coordinates': coordinates,
                    'profile': 'driving-car',
                    'format_out': 'geojson',
                    'preference': 'shortest',
                    'geometry': 'true'}

regular_route = ors.directions(**direction_params) # Direction request

# Build popup
distance, duration = regular_route['features'][0]['properties']['summary'].values()
popup = folium.map.Popup(popup_route.format('Regular',
                                                 duration/60,
                                                 distance/1000))

gj= folium.GeoJson(regular_route,
                   name='Regular Route',
                   style_function=style_function('blue')) \
          .add_child(popup)\
          .add_to(map_berlin)

folium.Marker(list(reversed(coordinates[0])), popup='Bundeskanzleramt').add_to(map_berlin)
folium.Marker(list(reversed(coordinates[1])), popup='Deutsches Currywurst Museum').add_to(map_berlin)
map_berlin
# -

# ### Dieselgate Routing
#
# Coming soon: The shortest route for a Diesel driver, which must avoid the blackish areas.
# Then, affected cars can't cross Friedrichstraße anymore.
# See for yourself:

# + code_folding=[1, 9, 10]
# Start and destination coordinates of affectes streets
avoid_streets = [{'name':'Friedrichstraße', 'coords': [[13.390478, 52.506805], [13.387141, 52.52696]]},
                 {'name': 'Leiziger Straße', 'coords': [[13.377807, 52.509587], [13.401142, 52.511291]]},
                 {'name': 'Brückenstraße', 'coords': [[13.416549, 52.511141], [13.417686, 52.513531]]},
                 {'name': 'Alt-Moabit', 'coords': [[13.327618, 52.524322], [13.367872, 52.522325]]},
                 {'name': 'Stromstraße', 'coords': [[13.342155, 52.523474], [13.343239, 52.531555]]}]

# Affected streets
buffer = []
for street in avoid_streets:
    avoid_params = {'coordinates': street['coords'],
                    'profile': 'driving-car',
                    'format_out': 'geojson',
                    'preference': 'shortest',
                    'geometry': 'true'}
    avoid_request = ors.directions(**avoid_params)
    coords = avoid_request['features'][0]['geometry']['coordinates']
    route_buffer = LineString(coords).buffer(0.0005) # Create geometry buffer
    folium.vector_layers.Polygon([(y,x) for x,y in list(route_buffer.exterior.coords)],
                                color=('#FF0000'),
                                popup=street['name'],).add_to(map_berlin)
    simp_geom = route_buffer.simplify(0.005) # Simplify geometry for better handling
    buffer.append(simp_geom)
union_buffer = cascaded_union(buffer)
map_berlin
# -

# If they are serious about it, this will be the route while avoiding the banned areas:

# + code_folding=[]
# New routing with avoided streets
diesel_request = {'coordinates': coordinates,
                'format_out': 'geojson',
                'profile': 'driving-car',
                'preference': 'shortest',
                'instructions': False,
                 'options': {'avoid_polygons': mapping(union_buffer)}}
route_diesel = ors.directions(**diesel_request)

# Build popup
distance, duration = route_diesel['features'][0]['properties']['summary'].values()
popup = folium.map.Popup(popup_route.format('Diesel Route',
                                                 duration/60,
                                                 distance/1000))

folium.GeoJson(route_diesel,
               style_function=style_function('black'),
               name='Route after Jan 2019').add_child(popup).add_to(map_berlin)

map_berlin.add_child(folium.map.LayerControl())
# -

# Now, here it should be noted, that our dear Chancellor would have to drive a detour of more than **1.5 times** the
# current distance, imposing 50% more pollution on Berlin's residents, just to enjoy the history of the Currywurst.
# Click on the routes to see for yourself.
#
# At least Friedrichstraße is safe soon!
