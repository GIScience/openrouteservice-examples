# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:light
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.16.4
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# # Calculating Centrality using the Export Endpoint
#
# Complex network analysis, such as calculating different centrality measures (TODO: add wiki link(s)), surpass the capabilites of the openrouteservice. There exist a lot of tools for network analyses that are much better suited for these tasks. 
#
# To support these kinds of analyses, the road network that the openrouteservice uses for route calculation can be exported. This training aims to show the usage of the openrouteservice `/export` endpoint, how to parse the endpoints output into GeoJSON and how to import it into networkx for centrality analyses.

# ## Setup
#
# Load all necessary modules

import openrouteservice as ors
import geojson
import folium
import networkx as nx
from branca.colormap import linear
from folium import plugins

# + [markdown] jp-MarkdownHeadingCollapsed=true
# ### Visualization Utilities
# -

# We define a few utility functions to aid with visualization later.

# +
from math import atan2, pi

def calcRotation(line_points):
    fromCoord = line_points[0]
    toCoord = line_points[1]

    dx = fromCoord[0] - toCoord[0]
    dy = fromCoord[1] - toCoord[1]
    
    # calculate angle to draw arrow
    rot = atan2(dx, dy) * 180 / pi
    
    return 180 - rot

def calcLocation(line_points):
    fromCoord = line_points[0]
    toCoord = line_points[1]

    dx = toCoord[0] - fromCoord[0]
    dy = toCoord[1] - fromCoord[1]

    return [toCoord[0] - 0.05*dx, toCoord[1] - 0.05*dy]



# -

# ### Set up openrouteservice

# Make sure that you have a [personal key for the public openrouteservice API](https://openrouteservice.org/dev/#/login). Insert **your API key** below.

api_key = '5b3ce3597851110001cf6248fc20d2ec7ea24e968d74e1bab4bfbe46'

# **Create a ORS client** which will be used to send request to the API. 

ors_client = ors.Client(key=api_key)

# ## Export Endpoint - Parse Results to GeoJSON
#
# Define a **bounding box** in the format `[[lon_min, lat_min],[lon_max, lat_max]]` for which you want to export data, as well as the **profile** that you want to export the graph for.
#
# In this example, we'll use the `driving-car` profile and focus on Heidelberg, Germany.

profile = "driving-car"
#bbox = [[8.677139,49.412872],[8.690443,49.421080]] # Neuenheim
#bbox = [[8.655967,49.382834],[8.718537,49.435273]] # Heidelberg
bbox = [[8.668069,49.398477],[8.697079,49.426174]] # Neuenheim + Bergheim + Weststadt

# The export endpoint has not been included into the openrouteservice-py module yet, but it includes the `request()` method to direct requests to any url. We can use this to request from the `/export`-endpoint.

resp = ors_client.request(url = f'/v2/export/{profile}', get_params = {}, post_json = {'bbox': bbox})

# The output format is defined [in our backend documentation](https://giscience.github.io/openrouteservice/api-reference/endpoints/export/#export-endpoint)
# We will first transform our response into a GeoJSON that can then be visualized and exported.

# +
 # parse all nodes into Points, add ID to feature, add to FeatureCollection
points = {}
node_list = []
for node in resp['nodes']:
    point = geojson.Point(node['location'])
    points[node['nodeId']] = point
    feature = geojson.Feature(geometry=point, properties={"ID": node['nodeId']})
    node_list.append(feature)

node_collection = geojson.FeatureCollection(node_list)

# parse all edges into LineString, add weight to Feature, add to FeatureCollection
edge_list = []
for edge in resp['edges']:
    line = geojson.LineString((points[edge['fromId']], points[edge['toId']]))
    feature = geojson.Feature(geometry=line, properties={"weight": edge['weight'], "direction": f"{edge["fromId"]} -> {edge["toId"]}"})
    edge_list.append(feature)

edge_collection = geojson.FeatureCollection(edge_list)
# -

# We now have two FeatureCollections that we could export or visualize rather easily.
#
# Note, that there is quite a bit of data that is getting extracted, so the nodes have been disabled by default to not crowd the view.
# You can enable them by clicking the layer control in the top right.

# +
geoJSONMap = folium.Map(location = [49.411085, 8.685894], zoom_start = 13)
folium.GeoJson(edge_collection, name="Edges", tooltip=folium.GeoJsonTooltip(fields=['weight', 'direction'])).add_to(geoJSONMap)
layer = folium.GeoJson(node_collection, name="Nodes", marker=folium.CircleMarker(radius = 5, color="black", weight=3), tooltip=folium.GeoJsonTooltip(fields=['ID']), show=False).add_to(geoJSONMap)

# Set the view to view everything
geoJSONMap.fit_bounds(layer.get_bounds())
folium.LayerControl().add_to(geoJSONMap)
geoJSONMap
# -

# This works rather well to get a rough idea of the graph structure, and hovering over the nodes and edges shows the node IDs and the edge weights.
# The problem here is mainly that edges that go in both directions (i.e. roads that are *not* one-way streets) are not shown separately. After all, we are not visualizing a graph, but a geojson.
#
# Getting around this by tampering with GeoJSON in `folium` is rather complicated and tedious.
# Therefore, we will resort to basic `folium.PolyLine`s to make this easier.
#
# The following visualization uses a small `x` in the middle of any edge to denote that it is a bi-directional edge.
# Hovering over the part of the edge between the `x` and either of the nodes connected to the edge (which can be shown via the layer controls in the top right) shows information about this direction of the edge.

# +
points = {}
for node in resp['nodes']:
    # Folium coordinate order is different from GeoJSON.
    points[node['nodeId']] = list(reversed(node['location']))

edges = {}
for edge in resp['edges']:
    fromId = edge['fromId']
    toId = edge['toId']
    weight = edge['weight']
    edges.setdefault(fromId, {})
    edges[fromId][toId] = weight

# parse all edges into Linestrings, add weight to Feature, add them to FeatureCollection
lineMap = folium.Map(location = [49.411085, 8.685894], zoom_start = 13)

for fromId, values in edges.items():
    for toId, weight in values.items():
        if fromId in edges.get(toId, []):
            # reverse direction exists, only draw half a line
            mid = [sum(x)/2 for x in zip(points[fromId], points[toId])]
            line_points = [mid, points[toId]]
            line = folium.PolyLine(
                locations = line_points,
                tooltip = f"{fromId} -> {toId}, weight: {weight}"
            )
            line.add_to(lineMap)
            #rotation = calcRotation(line_points)
            #location = calcLocation(line_points)
            
            #folium.RegularPolygonMarker(location=location, color='red', stroke=1, fill_color='red', number_of_sides=3, radius=8, rotation=rotation).add_to(lineMap)
            #folium.RegularPolygonMarker(location=mid, color='black', stroke=2, fill_color='black', number_of_sides=4, radius=4, rotation=rotation).add_to(lineMap)
            folium.Marker(location=mid, icon=plugins.BeautifyIcon(
                     icon="x",
                     text_color='black',
                     background_color='transparent',
                     border_color='transparent',
                     #inner_icon_style='font-size:20px'
                 )).add_to(lineMap)
            # TODO: add viz for start/end
        else:
            line = folium.PolyLine(
                locations = [points[fromId], points[toId]],
                tooltip = f"{fromId} -> {toId}, weight: {weight}"
            )
            line.add_to(lineMap)

folium.GeoJson(node_collection, name="Nodes", marker=folium.CircleMarker(radius = 5, color="black", weight=3), tooltip=folium.GeoJsonTooltip(fields=['ID']), show=False).add_to(lineMap)

folium.LayerControl().add_to(lineMap)
lineMap
# -

# # Centrality from Export Endpoint
#
# Centrality is an information about how "important" an edge is in a graph. There exist different centrality measures, but for road network analysis, the main measure we are focusing on is called [**betweenness centrality**](https://en.wikipedia.org/wiki/Betweenness_centrality). 
#
# For any two nodes, calculate the shortest path between the two nodes. This will yield a number of total shortest paths. Let's call it `T`. Now select an edge, and count how many of these shortest paths use this edge. Call this number `E`. The ratio of shortest paths using the edge to total shortest paths using the edge, i.e. `E/T` is the centrality of the edge.
#
# Thus, the more optimal connections in a graph use a certain edge, the more "central" to the graph it becomes.
# We will show this in an example for a part of Heidelberg.
#
# First, we load our edges into a [networkx `DiGraph`](https://networkx.org/documentation/stable/reference/classes/digraph.html#networkx.DiGraph), a bi-directional graph structure.

# +
g = nx.DiGraph()

for edge in resp['edges']:
    g.add_edge(edge['fromId'], edge['toId'], weight=edge['weight'])
# -

# Next, we can calulate the edge centralities:

edge_centralities = nx.edge_betweenness_centrality(g)

# Visualization follows the pattern from above, but without the midpoints. Color is used to denote centralities, if an edge seemingly has two colors, that means it's a bi-directional edge where the color corresponds to the centrality of the direction the edge is going to from the midpoint.

# +
centralityMap = folium.Map(location = [49.411085, 8.685894], zoom_start = 13)
min_val = min(edge_centralities.values())
max_val = max(edge_centralities.values())
diff = max_val - min_val

for fromId, values in edges.items():
    for toId, weight in values.items():
        if fromId in edges.get(toId, []):
            # reverse direction exists, only draw half a line
            mid = [sum(x)/2 for x in zip(points[fromId], points[toId])]
            line_points = [mid, points[toId]]
            line = folium.PolyLine(
                locations = line_points,
                tooltip = f"{fromId} -> {toId}, weight: {weight}, centrality: {edge_centralities[(fromId, toId)]}",
                color = linear.RdYlBu_04(1-((edge_centralities[(fromId, toId)] - min_val)/diff)),
                weight = 5
            )
            line.add_to(centralityMap)
            rotation = calcRotation(line_points)
            location = calcLocation(line_points)
            
            #folium.RegularPolygonMarker(location=location, color='red', stroke=1, fill_color='red', number_of_sides=3, radius=8, rotation=rotation).add_to(lineMap)
            #folium.RegularPolygonMarker(location=mid, color='black', stroke=2, fill_color='black', number_of_sides=4, radius=4, rotation=rotation).add_to(lineMap)
            # TODO: add viz for start/end
        else:
            line = folium.PolyLine(
                locations = [points[fromId], points[toId]],
                tooltip = f"{fromId} -> {toId}, weight: {weight}, centrality: {edge_centralities[(fromId, toId)]}",
                color = linear.RdYlBu_04(1-((edge_centralities[(fromId, toId)] - min_val)/diff)),
                weight = 5
            )
            line.add_to(centralityMap)

centralityMap
# -

# To show how centrality changes, we remove the two edges representing the western bridge - both from our graph and from our edges. This simulates a possible disaster, such as a ship striking the bridge, which would make it impossible to pass.

g.remove_edge(19266968, 1039877)
g.remove_edge(181908, 181913)
_ = edges[19266968].pop(1039877)
_ = edges[181908].pop(181913)

# Let's recalculate centralities…

edge_centralities = nx.edge_betweenness_centrality(g)

# …and visualize the changes.

# +
centralityMap = folium.Map(location = [49.411085, 8.685894], zoom_start = 13)
min_val = min(edge_centralities.values())
max_val = max(edge_centralities.values())
diff = max_val - min_val

for fromId, values in edges.items():
    for toId, weight in values.items():
        if fromId in edges.get(toId, []):
            # reverse direction exists, only draw half a line
            mid = [sum(x)/2 for x in zip(points[fromId], points[toId])]
            line_points = [mid, points[toId]]
            line = folium.PolyLine(
                locations = line_points,
                tooltip = f"{fromId} -> {toId}, weight: {weight}, centrality: {edge_centralities[(fromId, toId)]}",
                color = linear.RdYlBu_04(1-((edge_centralities[(fromId, toId)] - min_val)/diff)),
                weight = 5
            )
            line.add_to(centralityMap)
            rotation = calcRotation(line_points)
            location = calcLocation(line_points)
            
            #folium.RegularPolygonMarker(location=location, color='red', stroke=1, fill_color='red', number_of_sides=3, radius=8, rotation=rotation).add_to(lineMap)
            #folium.RegularPolygonMarker(location=mid, color='black', stroke=2, fill_color='black', number_of_sides=4, radius=4, rotation=rotation).add_to(lineMap)
            # TODO: add viz for start/end
        else:
            line = folium.PolyLine(
                locations = [points[fromId], points[toId]],
                tooltip = f"{fromId} -> {toId}, weight: {weight}, centrality: {edge_centralities[(fromId, toId)]}",
                color = linear.RdYlBu_04(1-((edge_centralities[(fromId, toId)] - min_val)/diff)),
                weight = 5
            )
            line.add_to(centralityMap)

centralityMap
# -
# As we can see, the centrality of the eastern bridge increases quite heavily, as all connections from the south to the north of the river (or vice versa) now have to use the eastern bridge.
#
# For the given topology, this is not too surprising - but go check out how your area would change, if certain central connections were not available anymore.



