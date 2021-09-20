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

# # Peak routing

# _Contributed by Dr. Stephan Fuchs_
#
# In this tutorial we will:
# - extract some mountain peaks from OpenStreetMap using the `overpy` package
# - calculate the routes to the peaks from different starting points
# - save the maps as PNG files using an intermediate HTML representation
# as well as the `selenium` and `webdriver-manager` packages

# + [markdown] pycharm={"name": "#%% md\n"}
# #### Create an output folder for the maps if it doesn't exist already

# + pycharm={"name": "#%%\n"}
import os

map_folder = f"{os.getcwd()}/maps"

if not os.path.exists(map_folder):
    print("Creating maps folder")
    os.makedirs(map_folder)

# + [markdown] pycharm={"name": "#%% md\n"}
# #### Get the coordinates of the peaks
# You can directly download the peak data via the overpy package.
# It uses the same query language as [overpass-turbo](https://overpass-turbo.eu/#).
#
# Here the peaks where the name matches one of the `peak_names` will be extracted from the given bounding box.

# + pycharm={"name": "#%%\n"}
import overpy
import json

api = overpy.Overpass()

bbox = [50.82263785103416, 13.996753692626951, 50.843670947425615, 14.116744995117186]
peak_names = ["Zeisigstein", "Herkuleskopf", "Kristin Hrádek"]

# Query natural peaks from overpass api within bounding box
result = api.query(
    f"""node["natural"="peak"][name~"^({"|".join(peak_names)})$"]({",".join([str(c) for c in bbox])});out;""")

# Extract name and coordinates
peaks = [{"name": n.tags['name'], "LonLat": [float(n.lon), float(n.lat)]} for n in result.nodes]
print(json.dumps(peaks, indent=2))

# + [markdown] pycharm={"name": "#%% md\n"}
# #### The starting points
# As starting locations we choose one bus station, a parking place and a Hotel from the surrounding area.
# For simplicity, the coordinates are given already.
# An identification color is added for styling corresponding elements.

# + pycharm={"name": "#%%\n"}
start_points = [
    {
        "name": "Bushaltestelle Zollhaus",
        "LonLat": [14.067741, 50.832176],
        "color": "blue"
    }, {
        "name": "Waldparkplatz Ottomühle",
        "LonLat": [14.045109, 50.839162],
        "color": "red"
    }, {
        "name": "Hotel Ostrov",
        "LonLat": [14.046037, 50.803897],
        "color": "orange"
    }
]
# -

# #### Calculate the routes
# For each of the peaks we create a folium map with routes from every starting point, and add it to the `maps` list.
# To every map we add the points, the calculated routes and a little styling.
#
# __Make sure to insert a valid openrouteservice API key before running the cell__

# +
import folium
import openrouteservice

client = openrouteservice.Client(key="your_api_key")


# The style for the plotted routes.
def route_style(color):
    return lambda feature: dict(color=color, opacity=0.9, weight=4, )


maps = []
for peak in peaks:
    # initialize map and storages
    map_object = folium.Map()
    bounds = []
    routes = {}

    for start in start_points:
        # Add point markers with LatLon coordinates
        folium.Marker(list(reversed(start["LonLat"])), popup=start["name"],
                      icon=folium.Icon(icon_color=start["color"], icon='taxi', prefix='fa')).add_to(map_object)
        folium.Marker(list(reversed(peak["LonLat"])), popup=peak["name"],
                      icon=folium.Icon(icon="chevron-up", icon_color="dark-grey", prefix="fa")).add_to(map_object)

        # request walking route from start to peak
        response = client.directions([start["LonLat"], peak["LonLat"]], profile='foot-walking', geometry='true',
                                     format_out="geojson")

        # extract route info
        routes[start["name"]] = {
            "distance_m": round(response["features"][0]["properties"]["summary"]["distance"]),
            "duration_min": round(response["features"][0]["properties"]["summary"]["duration"] / 60.)
        }

        # add styled route objects
        route = folium.GeoJson(response, style_function=route_style(start["color"]))
        route.add_to(map_object)

        # add bounds to list for overview-bounds calculation
        bounds.append(route.get_bounds())

    # calculate overview-bounds
    bbox = [
        [min(c[0][0] for c in bounds),
         min(c[0][1] for c in bounds)],
        [max(c[1][0] for c in bounds),
         max(c[1][1] for c in bounds)]
    ]
    map_object.fit_bounds(bbox)
    maps.append({
        "map_obj": map_object,
        "routes": routes
    })
    del routes

    # save as html to maps folder
    map_object.save("maps/" + peak["name"] + ".html")


# + [markdown] pycharm={"name": "#%% md\n"}
# #### Display maps
# Show route information and map interface (Only one map can be shown per Cell).

# + pycharm={"name": "#%%\n"}
def print_map_info(routes_dict: dict):
    """
    Prints info for each start point
    """
    for name, summary in routes_dict.items():
        print(f"From {name}: distance {summary['distance_m']} m, duration: {summary['duration_min']} min")


# + pycharm={"name": "#%%\n"}
print(f"-- Routes to {peak_names[0]} peak --")
print_map_info(maps[0]["routes"])
maps[0]["map_obj"]

# + pycharm={"name": "#%%\n"}
print(f"-- Routes to {peak_names[1]} peak --")
print_map_info(maps[1]["routes"])
maps[1]["map_obj"]

# + pycharm={"name": "#%%\n"}
print(f"-- Routes to {peak_names[2]} peak --")
print_map_info(maps[2]["routes"])
maps[2]["map_obj"]

# -

# #### Save maps as PNG
# For transformation to PNG, we need a browser to take a screenshot from.
# Luckily `webdriver-manager` takes care of installing the browser driver for us.
#
# After opening the images with the webdriver, we can set the resolution and save a screenshot of the browser window, to
# get our desired PNG file.

# + pycharm={"name": "#%%\n"}
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
import time

chrome_driver = webdriver.Chrome(ChromeDriverManager().install())
chrome_driver.set_window_size(1280, 900)  # choose a resolution

for peak in peak_names:
    path = f"file://{map_folder}/{peak}.html"
    chrome_driver.get(url=path)
    time.sleep(2)  # Waiting for page loading
    chrome_driver.save_screenshot(f"{map_folder}/{peak}.png")

chrome_driver.quit()
# -

# #### Additional image manipulation (optional)
# In case the image needs to be processed further e.g. the `Pillow` package can be used to manipulate it.
# Here a simple resize is shown to reduce the resolution while keeping the aspect ratio.

# + pycharm={"name": "#%%\n"}
from PIL import Image

for peak in peak_names:
    image = Image.open(f"{map_folder}/{peak}.png")
    new_image = image.resize([int(i * 0.25) for i in image.size])  # resize to 1/4 the resolution
    new_image.save(f"{map_folder}/{peak}_small.png")
