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

# # Search for a suitable apartment
# > Note: All notebooks need the [environment dependencies](https://github.com/GIScience/openrouteservice-examples#local-installation)
# > as well as an [openrouteservice API key](https://openrouteservice.org/dev/#/signup) to run
#
# In this notebook we'll provide an example for using different openrouteservice API's to help you look for an apartment.

# + pycharm={"name": "#%%\n"}
import folium

from openrouteservice import client

# -

# We want to move to San Francisco with our kids and are looking for the perfect location to get a new home.
# Our geo intuition tells us we have to look at the data to come to this important decision.
# So we decide to geek it up a bit.

# # Apartment isochrones

# There are three different suggested locations for our new home. Let's visualize them, and the 15-minute walking radius
# on a map:

# +
api_key = 'your_key'  # Provide your personal API key
ors = client.Client(key=api_key)
# Set up folium map
map1 = folium.Map(tiles='Stamen Toner', location=([37.738684, -122.450523]), zoom_start=12)

# Set up the apartment dictionary with real coordinates
apartments = {'first': {'location': [-122.430954, 37.792965]},
              'second': {'location': [-122.501636, 37.748653]},
              'third': {'location': [-122.446629, 37.736928]}
              }

# Request of isochrones with 15 minute on foot.
params_iso = {'profile': 'foot-walking',
              'range': [900],  # 900/60 = 15 minutes
              'attributes': ['total_pop']  # Get population count for isochrones
              }

for name, apt in apartments.items():
    params_iso['locations'] = [apt['location']]  # Add apartment coords to request parameters
    apt['iso'] = ors.isochrones(**params_iso)  # Perform isochrone request
    folium.features.GeoJson(apt['iso']).add_to(map1)  # Add GeoJson to map

    folium.map.Marker(list(reversed(apt['location'])),  # reverse coords due to weird folium lat/lon syntax
                      icon=folium.Icon(color='lightgray',
                                       icon_color='#cc0000',
                                       icon='home',
                                       prefix='fa',
                                       ),
                      popup=name,
                      ).add_to(map1)  # Add apartment locations to map

map1
# -

# # POIs around apartments

# For the ever-styled foodie parents we are, we need to have the 3 basic things covered: kindergarten,
# supermarket and hair dresser.
# Let's see what options we got around our apartments:

# +
# Common request parameters
params_poi = {'request': 'pois',
              'sortby': 'distance'}

# POI categories according to
# https://github.com/GIScience/openrouteservice-docs#places-response
categories_poi = {'kindergarten': [153],
                  'supermarket': [518],
                  'hairdresser': [395]}

for name, apt in apartments.items():
    apt['categories'] = dict()  # Store in pois dict for easier retrieval
    params_poi['geojson'] = apt['iso']['features'][0]['geometry']
    print("\n{} apartment".format(name))

    for typ, category in categories_poi.items():
        params_poi['filter_category_ids'] = category
        apt['categories'][typ] = dict()
        apt['categories'][typ]['geojson'] = ors.places(**params_poi)[0]['features']  # Actual POI request
        print(f"\t{typ}: {len(apt['categories'][typ]['geojson'])}")
# -

# We already see that the second apartment is missing a supermarket in a 15-minute walking range and continue without it.

# Remove second apartment
del apartments['second']

# # Routing from apartments to POIs

# To decide on a place, we would like to know from which apartment we can reach all required POI categories the quickest.
# So, first we look at the distances from each apartment to the respective POIs.

# +
# Set up common request parameters
params_route = {'profile': 'foot-walking',
                'format_out': 'geojson',
                'geometry': 'true',
                'format': 'geojson',
                'instructions': 'false',
                }

# Set up dict for font-awesome
style_dict = {'kindergarten': 'child',
              'supermarket': 'shopping-cart',
              'hairdresser': 'scissors'
              }

# Store all routes from all apartments to POIs
for apt in apartments.values():
    for cat, pois in apt['categories'].items():
        pois['durations'] = []
        for poi in pois['geojson']:
            poi_coords = poi['geometry']['coordinates']

            # Perform actual request
            params_route['coordinates'] = [apt['location'],
                                           poi_coords
                                           ]
            json_route = ors.directions(**params_route)

            folium.features.GeoJson(json_route).add_to(map1)
            folium.map.Marker(list(reversed(poi_coords)),
                              icon=folium.Icon(color='white',
                                               icon_color='#1a1aff',
                                               icon=style_dict[cat],
                                               prefix='fa'
                                               )
                              ).add_to(map1)

            poi_duration = json_route['features'][0]['properties']['summary']['duration']
            pois['durations'].append(poi_duration)  # Record durations of routes

map1
# -

# # The Quickest route to all POIs

# Now, we only need to determine which apartment is closest to all POI categories.

# Sum up the closest POIs to each apartment
for name, apt in apartments.items():
    apt['shortest_sum'] = sum([min(cat['durations']) for cat in apt['categories'].values()])
    print(f"{name} apartment: {round(apt['shortest_sum'] / 60, 1)} min"
          )

# # We got a winner!

# Finally, it looks like the first apartment is the one where we would need to walk the shortest amount of time to reach
# a kindergarten, supermarket and a hair dresser. Let's pack those boxes and welcome to San Francisco.
