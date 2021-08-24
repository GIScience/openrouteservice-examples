# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:light
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.11.4
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# # Combining Twitter Data and OpenRouteService Directions API

# In the case of a natural disaster like earthquakes or floods areas and streets can be blocked and not passable. Regular routes are not available and the accessibility of critical infrastructure might change. In the moment when a disaster happens, valid information on affected areas is often not immediately available. In these situations social media data can be a novel source of real-time data created by citizens living in the affected area. 
#
# In the year 2013 there was a severe flood in the eastern part of Germany, which also affected the city of Magdeburg. This notebook will focus on a possible way to access important locations in such a disaster case. The OpenRouteService `direction` paramter can be used to receive the shortest or fastest route from A to B. This parameter offers the `avoid_polygons` feature which is suited to avoid blocked areas and to generate the shortes route in respect to the disaster situation.
#
# In this study Twitter data will be used, because of the location based information they offer in real time quality. Twitter data can be obtained via the [Twitter API](https://dev.twitter.com/apps).

# ## Workflow
#
# - Preprocessing: Get Twitter data from 2013 and classify them into flood affected tweets and regular tweets.
# - Analysis: Compute two routes between two locations. One for a regular scenario and one for the case of a disaster with blocked streets.
# - Result: Visualize results on a map. 

# ## Preprocessing
#
# To get started load in all needed python packages, apply for your own [OpenRouteService API Key](https://openrouteservice.org/dev/#/signup) and download the Social media data.
#
# Each tweet includes information about the user, a timestamp, a message, if geolocated coordinates and further meta data. For this study we are only interessted in tweets concerning the flood event. Therefore we filter by keywords and hashtags. Tweets  related to the flood event are markek with 1, all remaining tweets with 0. (*Note: This is not done within this notebook. Make sure to provide this information already in your data set.*)

# +
import os

import folium
from folium import Map, Marker, LayerControl
#from folium.plugins import MarkerCluster

from openrouteservice import client

import fiona as fn
from shapely import geometry
from shapely.geometry import shape, Polygon, mapping, MultiPolygon, LineString, Point
from shapely.ops import cascaded_union, transform

import pyproj

# +
# insert your ORS api key
api_key = 'YOUR-KEY' 
clnt = client.Client(key=api_key)

# Twitter data from 2013
tweet_file = 'tweets/tweets_magdeburg.shp'


# -

# Tweets are represented as point geometries. We apply a buffer to the tweets to generate polygons. Street segments which overlap with a buffered tweet will be avoided. The upcoming function `CreateBufferPolygon` transforms point geometries from WGS84 (EPSG: 4326) to UTM32N (EPSG: 32632), creates a 20 meter buffer around each one and transforms the geometries back to WGS84.
#
# Futhermore, we create a function `CreateRoute` to request routes from the OpenRouteService Directions API. Besided the regular input (starting point, end point, profile, output format, profile) we pass `avoid_polygons` as an additional option.
#
# *Side Note: Applying a buffer directly to the point geometries without transforming the spatial reference system will lead to oval shapes. So, whenever you receive non round shapes after buffering consider changing the projection.*

# +
# Function to create buffer around tweet point geometries and transform it to the needed coordinate system (WGS84)
def CreateBufferPolygon(point_in, resolution=2, radius=20):    
    sr_wgs = pyproj.Proj(init='epsg:4326') # WGS84
    sr_utm = pyproj.Proj(init='epsg:32632') # UTM32N
    point_in_proj = pyproj.transform(sr_wgs, sr_utm, *point_in) # Unpack list to arguments
    point_buffer_proj = Point(point_in_proj).buffer(radius, resolution=resolution) # 20 m buffer
    
    # Iterate over all points in buffer and build polygon
    poly_wgs = []
    for point in point_buffer_proj.exterior.coords:
        poly_wgs.append(pyproj.transform(sr_utm, sr_wgs, *point)) # Transform back to WGS84
        
    return poly_wgs


# Function to request directions with avoided_polygon feature
def CreateRoute(avoided_point_list, n=0):
    route_request = {'coordinates': coordinates, 
                    'format_out': 'geojson',
                    'profile': 'driving-car',
                    'preference': 'shortest',
                    'instructions': False,
                     'options': {'avoid_polygons': geometry.mapping(MultiPolygon(avoided_point_list))}} 
    route_directions = clnt.directions(**route_request)
    
    return route_directions


# Function to create buffer around requested route
def CreateBuffer(route_directions): 
    line_tup = []
    for line in route_directions['features'][0]['geometry']['coordinates']:
        tup_format = tuple(line)
        line_tup.append(tup_format)  

    new_linestring = LineString(line_tup)
    dilated_route = new_linestring.buffer(0.001)
        
    return dilated_route


# -

# ## Analysis
# To get an overview of the received data we load in all data for the chosen time and area. We group the data into tweets related to the flood event (red) and other tweets (blue). Furthermore we are applying the CreateBufferPoylgon function to create buffer polygons using flood related tweets. 

# +
map_tweet = folium.Map(tiles='Stamen Toner', location=([52.136096, 11.635208]), zoom_start=14) # Create map

def style_function(color): # To style data
    return lambda feature: dict(color=color)

counter = 0
flood_tweets = [] # Flood affected tweets
tweet_geometry = [] # Simplify geometry of tweet buffer polygons
with fn.open(tweet_file, 'r') as tweet_data: # Open data in reading mode
    print('{} tweets in total available.'.format(len(tweet_data)))
    for data in tweet_data:
        # Tweets which are not affected by the flood
        if data['properties']['HOCHWASSER'] != 1:
            counter += 1
            folium.Marker(list(reversed(data['geometry']['coordinates'][0])),
                          icon=folium.Icon(color='lightgray',
                                        icon_color='blue',
                                        icon='twitter',
                                        prefix='fa'),
                          popup='Regular Tweet').add_to(map_tweet)
            
        # Tweets which are affected by the flood
        else:
            folium.Marker(list(reversed(data['geometry']['coordinates'][0])),
                          icon=folium.Icon(color='lightgray',
                                        icon_color='red',
                                        icon='twitter',
                                        prefix='fa'),
                          popup=data['properties']['tweet']).add_to(map_tweet)

            # Create buffer polygons around affected sites with 20 m radius and low resolution
            flood_tweet = CreateBufferPolygon(data['geometry']['coordinates'][0],
                                           resolution=2, # low resolution to keep polygons lean
                                           radius=20)
            flood_tweets.append(flood_tweet)
            
            # Create simplify geometry and merge overlapping buffer regions
            poly = Polygon(flood_tweet)  
            tweet_geometry.append(poly)
union_poly = mapping(cascaded_union(tweet_geometry)) 
                      
folium.features.GeoJson(data=union_poly,
                        name='Flood affected areas',
                        style_function=style_function('#ffd699'),).add_to(map_tweet)

print('{} regular tweets with no flood information avalibale.'.format(counter))
print(len(flood_tweets), 'tweets with flood information available.')

#map_tweet.save(os.path.join('results', '1_tweets.html'))
map_tweet
# -

# In the beginning we have created two functions, `CreateRoute` and `CreateBuffer`. The `CreateRoute` function requests the shortest route from A to B for the driving-car profile. It also avoids the tweets which are included in the avoided_point_list. This list is empty in the beginning.
#
# To check if a flood tweet overlaps the route, we generate a buffer around the requested route. If tweet and buffered route intersect, the tweet location will be appended to the `avoided_point_list`. For the next routing request these geometries will be avoided. This keeps doing until a shortest route is generated which does not intersect with any tweet. 

# +
# Visualize start and destination point on map
coordinates = [[11.653361, 52.144116], [11.62847, 52.1303]] # Central Station and Fire Department
for coord in coordinates:
    folium.map.Marker(list(reversed(coord))).add_to(map_tweet)

# Regular Route
avoided_point_list = [] # Create empty list with avoided tweets
route_directions = CreateRoute(avoided_point_list) # Create regular route with still empty avoided_point_list

folium.features.GeoJson(data=route_directions,
                        name='Regular Route',
                        style_function=style_function('#ff5050'),
                        overlay=True).add_to(map_tweet)
print('Generated regular route.')

# Avoiding tweets route
dilated_route = CreateBuffer(route_directions) # Create buffer around route

# Check if flood affected tweet is located on route
try:
    for site_poly in flood_tweets:
        poly = Polygon(site_poly)
        if poly.within(dilated_route):
            avoided_point_list.append(poly)

            # Create new route and buffer
            route_directions = CreateRoute(avoided_point_list, 1)
            dilated_route = CreateBuffer(route_directions)

    folium.features.GeoJson(data=route_directions,
                            name='Alternative Route',
                            style_function=style_function('#006600'),
                            overlay=True).add_to(map_tweet)
    print('Generated alternative route, which avoids affected areas.')
except Exception: 
    print('Sorry, there is no route available between the requested destination because of too many blocked streets.')

#map_tweet.save(os.path.join('results', '2_routes.html'))
map_tweet.add_child(folium.map.LayerControl())
map_tweet
# -

# ## Conclusion
# In the case of a disaster fast response is importent and life saving. Information on blocked streets is crucial, but a the same time this infornations needs to be considered by routing engines in real-time. However, many routing engines use street network data which is at best updated once a week or even less often. For many proprietary routing engines which do not use OpenStreetMap data it is also hardly possible to figure out when the data was updated for the last time. 
#
# To tackle this issue, we showed in this notebook how the direction feature `avoid_polygons` of the OpenRouteService API can be used. It allows to avoid certain areas (e.g. flood affected regions) and to request the fastest or shortest route for different kind of travel profiles (e.g. car or truck). we used Twitter data which offers real time location based point data which can be used as a fast ground truth information.
#
#
# *Side Note: Because of the limited length of a GET request, the avoid_polygons feature can currently handle just a limited number of polygons. Make sure not to exceed this limit to receive promising routing directions. And don't worry, we are addressing this issue also on our side. So stay tuned for future improvements of the OpenRouteService API.*
