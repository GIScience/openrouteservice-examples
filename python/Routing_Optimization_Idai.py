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

import folium
from folium.plugins import BeautifyIcon
import shapely
import pandas as pd
import openrouteservice as ors
from IPython.core.interactiveshell import InteractiveShell

# # Routing optimization in a humanitarian context
#
# Routing optimization generally solves the [Vehicle Routing Problem](https://en.wikipedia.org/wiki/Vehicle_routing_problem)
# (a simple example being the more widely known [Traveling Salesman Problem](https://en.wikipedia.org/wiki/Travelling_salesman_problem)).
# A more complex example would be the distribution of goods by a fleet of multiple vehicles to dozens of locations,
# where each vehicle has certain time windows in which it can operate and each delivery location has certain time windows
# in which it can be served (e.g. opening times of a supermarket).
#
# In this example we'll look at a real-world scenario of **distributing medical goods during disaster response**
# following one of the worst tropical cyclones ever been recorded in Africa: **Cyclone Idai**.
#
# ![Cyclone Idai second landfall](https://openrouteservice.org/wp-content/uploads/2017/07/idai_flooding_satellite.jpeg "Copernicus Sentinel-1 -satellite (modified Copernicus Sentinel data (2019), processed by ESA, CC BY-SA 3.0 IGO)")
# *Cyclone Idai floods in false color image on 19.03.2019; © Copernicus Sentinel-1 -satellite (modified Copernicus Sentinel data (2019), processed by ESA, CC BY-SA 3.0 IGO), [source](http://www.esa.int/spaceinimages/Images/2019/03/Floods_imaged_by_Copernicus_Sentinel-1)*
#
# In this scenario, a humanitarian organization shipped much needed medical goods to Beira, Mozambique, which were then
# dispatched to local vehicles to be delivered across the region.
# The supplies included vaccinations and medications for water-borne diseases such as Malaria and Cholera,
# so distribution efficiency was critical to contain disastrous epidemics.
#
# We'll solve this complex problem with [OpenRouteService](https://openrouteservice.org) new **route optimization service**.
#

# ## The logistics setup
#
# In total 20 sites were identified in need of the medical supplies, while 3 vehicles were scheduled for delivery.
# Let's assume there was only one type of goods, e.g. standard moving boxes full of one medication.
# (In reality there were dozens of different good types, which can be modelled with the same workflow,
# but that'd unnecessarily bloat this example).
#
# The **vehicles** were all located in the port of Beira and had the same following constraints:
#
# - operation time windows from 8:00 to 20:00
# - loading capacity of 300 *[arbitrary unit]*
#
# The **delivery locations** were mostly located in the Beira region, but some extended ~ 200 km to the north of Beira.
# Their needs range from 10 to 148 units of the arbitrary medication goods
# (consult the file located at `../resources/data/idai_health_sites.csv`). Let's look at it in a map.

# +
# First define the map centered around Beira
m = folium.Map(location=[-18.63680, 34.79430], tiles='cartodbpositron', zoom_start=8)

# Next load the delivery locations from CSV file at ../resources/data/idai_health_sites.csv
# ID, Lat, Lon, Open_From, Open_To, Needed_Amount
deliveries_data = pd.read_csv(
    '../resources/data/idai_health_sites.csv',
    index_col="ID",
    parse_dates=["Open_From", "Open_To"]
)

# Plot the locations on the map with more info in the ToolTip
for location in deliveries_data.itertuples():
    tooltip = folium.map.Tooltip("<h4><b>ID {}</b></p><p>Supplies needed: <b>{}</b></p>".format(
        location.Index, location.Needed_Amount
    ))

    folium.Marker(
        location=[location.Lat, location.Lon],
        tooltip=tooltip,
        icon=BeautifyIcon(
            icon_shape='marker',
            number=int(location.Index),
            spin=True,
            text_color='red',
            background_color="#FFF",
            inner_icon_style="font-size:12px;padding-top:-5px;"
        )
    ).add_to(m)

# The vehicles are all located at the port of Beira
depot = [-19.818474, 34.835447]

folium.Marker(
    location=depot,
    icon=folium.Icon(color="green", icon="bus", prefix='fa'),
    setZIndexOffset=1000
).add_to(m)

m
# -

# ## The routing problem setup
#
# Now that we have described the setup sufficiently, we can start to set up our actual Vehicle Routing Problem.
# For this example we're using the FOSS library of [Vroom](https://github.com/VROOM-Project/vroom), which has
# [recently seen](http://k1z.blog.uni-heidelberg.de/2019/01/24/solve-routing-optimization-with-vroom-ors/) support for
# OpenRouteService and is available through our APIs.
#
# To properly describe the problem in algorithmic terms, we have to provide the following information:
#
# - **vehicles start/end address**: vehicle depot in Beira's port
# - **vehicle capacity**: 300
# - **vehicle operational times**: 08:00 - 20:00
# - **service location**: delivery location
# - **service time windows**: individual delivery location's time window
# - **service amount**: individual delivery location's needs
#
# We defined all these parameters either in code above or in the data sheet located in
# `../resources/data/idai_health_sites.csv`.
# Now we have to only wrap this information into our code and send a request to OpenRouteService optimization service at
# [`https://api.openrouteservice.org/optimization`](https://openrouteservice.org/dev/#/api-docs/optimization/post).

# +
# Define the vehicles
# https://openrouteservice-py.readthedocs.io/en/latest/openrouteservice.html#openrouteservice.optimization.Vehicle
vehicles = list()
for idx in range(3):
    vehicles.append(
        ors.optimization.Vehicle(
            id=idx,
            start=list(reversed(depot)),
            #end=list(reversed(depot)),
            capacity=[300],
            time_window=[1553241600, 1553284800]  # Fri 8-20:00, expressed in POSIX timestamp
        )
    )

# Next define the delivery stations
# https://openrouteservice-py.readthedocs.io/en/latest/openrouteservice.html#openrouteservice.optimization.Job
deliveries = list()
for delivery in deliveries_data.itertuples():
    deliveries.append(
        ors.optimization.Job(
            id=delivery.Index,
            location=[delivery.Lon, delivery.Lat],
            service=1200,  # Assume 20 minutes at each site
            amount=[delivery.Needed_Amount],
            time_windows=[[
                int(delivery.Open_From.timestamp()),  # VROOM expects UNIX timestamp
                int(delivery.Open_To.timestamp())
            ]]
        )
    )
# -

# With that set up we can now perform the actual request and let OpenRouteService calculate the optimal vehicle schedule
# for all deliveries.

# +
# Initialize a client and make the request
ors_client = ors.Client(key='your_key')  # Get an API key from https://openrouteservice.org/dev/#/signup
result = ors_client.optimization(
    jobs=deliveries,
    vehicles=vehicles,
    geometry=True
)

# Add the output to the map
for color, route in zip(['green', 'red', 'blue'], result['routes']):
    decoded=ors.convert.decode_polyline(route['geometry'])  # Route geometry is encoded
    gj = folium.GeoJson(
        name='Vehicle {}'.format(route['vehicle']),
        data={"type": "FeatureCollection", "features": [{"type": "Feature",
                                                         "geometry": decoded,
                                                         "properties": {"color": color}
                                                        }]},
        style_function=lambda x: {"color": x['properties']['color']}
    )
    gj.add_child(folium.Tooltip(
        """<h4>Vehicle {vehicle}</h4>
        <b>Distance</b> {distance} m <br>
        <b>Duration</b> {duration} secs
        """.format(**route)
    ))
    gj.add_to(m)

folium.LayerControl().add_to(m)
m
# -

# ## Data view
#
# Plotting it on a map is nice, but let's add a little more context to it in form of data tables.
# First the overall trip schedule:

# ### Overall schedule

# +
# Only extract relevant fields from the response
extract_fields = ['distance', 'amount', 'duration']
data = [{key: route[key] for key in extract_fields} for route in result['routes']]

vehicles_df = pd.DataFrame(data)
vehicles_df.index.name = 'vehicle'
vehicles_df
# -

# So every vehicle's capacity is almost fully exploited. That's good.
# How about a look at the individual service stations:

# Create a list to display the schedule for all vehicles
stations = list()
for route in result['routes']:
    vehicle = list()
    for step in route["steps"]:
        vehicle.append(
            [
                step.get("job", "Depot"),  # Station ID
                step["arrival"],  # Arrival time
                step["arrival"] + step.get("service", 0),  # Departure time

            ]
        )
    stations.append(vehicle)


# Now we can look at each individual vehicle's timetable:

# ### Vehicle 0

df_stations_0 = pd.DataFrame(stations[0], columns=["Station ID", "Arrival", "Departure"])
df_stations_0['Arrival'] = pd.to_datetime(df_stations_0['Arrival'], unit='s')
df_stations_0['Departure'] = pd.to_datetime(df_stations_0['Departure'], unit='s')
df_stations_0

# ### Vehicle 1

df_stations_1 = pd.DataFrame(stations[1], columns=["Station ID", "Arrival", "Departure"])
df_stations_1['Arrival'] = pd.to_datetime(df_stations_1['Arrival'], unit='s')
df_stations_1['Departure'] = pd.to_datetime(df_stations_1['Departure'], unit='s')
df_stations_1

# ### Vehicle 2

df_stations_2 = pd.DataFrame(stations[2], columns=["Station ID", "Arrival", "Departure"])
df_stations_2['Arrival'] = pd.to_datetime(df_stations_2['Arrival'], unit='s')
df_stations_2['Departure'] = pd.to_datetime(df_stations_2['Departure'], unit='s')
df_stations_2
