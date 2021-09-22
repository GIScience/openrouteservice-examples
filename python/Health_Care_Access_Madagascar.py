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

# # Analysis of Access to Health Care using openrouteservice
# > Note: All notebooks need the [environment dependencies](https://github.com/GIScience/openrouteservice-examples#local-installation)
# > as well as an [openrouteservice API key](https://openrouteservice.org/dev/#/signup) to run

# ## Abstract
# In the case of a disaster (natural or man made), a country is not only affected by the intensity of the disaster but
# also by its own vulnerability to it.
# Countries have different kind of opportunities to prepare for such catastrophes,
# to respond  finally to start the recovery.
# Many less developed countries, e.g. Madagascar, are in particular prone to disasters, not only because of the higher
# probability of occurrence, but also due to a potentially lower ability to cope up during and after the event.
#
# In this example we will focus on vulnerability in terms of access to health care.
# The access to health facilities can be highly unequal within a country.
# Consequently, some areas and communities are more vulnerable to disasters effects than others.
# Quantifying and visualizing such inequalities is the aim of this notebook.
#
# The notebook gives an overview on health sites distribution and the amount of population with access to those by foot
# and by car for Madagascar.
# Open source data from OpenStreetMap and tools (such as the openrouteservice) were used to create accessibility
# isochrones for each hospital and to derive analysis results about the population percentage with access to
# health facilities per district.
# The findings show that the inhabitants of 69 of 119 (58%) districts don't have any access to hospitals in a one-hour
# walking range, and those of 43 of 119 (36%) districts in a one-hour car driving range.
#
# ### Workflow:
# * **Preprocessing**: Get data for districts, health facilities, population density, population count per district.
# * **Analysis**:
#     * Compute accessibility to health care facilities using openrouteservice API
#     * Derive the percentage of people with access to health care per district.
# * **Result**: Visualize results as choropleth maps.
#
#
# ### Datasets and Tools:
# * [Shapefile of district boundaries][boundaries] - Admin Level 2 (data from Humanitarian Data Exchange, 05/07/2018)
# * [Shapefile of health facilities][facilities] (data from Humanitarian Data Exchange, 05/07/2018)
# * [Raster file of population density][pop] - Worldpop Data (data from Humanitarian Data Exchange, 05.07.2018)
# * [openrouteservice][ors] - generate isochrones on the OpenStreetMap road network
# * [python implementation of zonal statistic by perrygeo][zonal_stats] - generate population count per district
#
# [boundaries]: https://data.humdata.org/dataset/madagascar-administrative-boundary-shapefiles-level-1-4
# [facilities]: https://data.humdata.org/dataset/madagascar-healthsites
# [pop]: https://data.humdata.org/dataset/worldpop-madagascar
# [ors]: https://openrouteservice.org/
# [zonal_stats]: https://gist.github.com/perrygeo/5667173

# # Python Workflow

# +
import os

from IPython.display import display

import folium
from folium.plugins import MarkerCluster

from openrouteservice import client

import time
import pandas as pd
import fiona as fn
from shapely.geometry import shape, mapping
from shapely.ops import cascaded_union

# import zonal stats function from python file, get it here: https://gist.github.com/perrygeo/5667173
from zonal_stats import *
# -

# ## Preprocessing
# For this study different kind of data were used. First a map were created with folium, a python package.
# The boundaries of the districts as well as the health sites were given as shapefiles, which were printed on the map.
# The dataset about the health sites is from 2018.
# * Folium map
# * [Shapefile of district boundaries](https://data.humdata.org/dataset/madagascar-administrative-boundary-shapefiles-level-1-4) - Admin Level 2 (data from Humanitarian Data Exchange, 05/07/2018)
# * [Shapefile of health facilities](https://data.humdata.org/dataset/madagascar-healthsites) (data from Humanitarian Data Exchange, 05/07/2018)
# * [Raster file of population density](https://data.humdata.org/dataset/worldpop-madagascar) - Worldpop Data (data from Humanitarian Data Exchange, 05.07.2018)

# +
# insert your ORS api key
api_key = '{your-ors-api-key}'
ors = client.Client(key=api_key)

# make sure to provide the right filenames
districts_filename = 'data/mdg_polbnda_adm2_Distritcts_BNGRC_OCHA.shp'
health_facilities_filename = 'data/healthsites.shp'
population_raster_filename = 'data/MDG_ppp_2020_adj_v2.tif'

# these files will be generated during processing
isochrones_car_filename = 'data/iso_union_car.shp'
isochrones_car_per_district_filename = 'data/iso_car_per_district.shp'
isochrones_foot_filename = 'data/iso_union_foot.shp'
isochrones_foot_per_district_filename = 'data/iso_foot_per_district.shp'

# final file with all generated information
output_file = 'data/districts_final.geojson'
# -

# ### Create district dictionary and facilities dictionary

# +
districts_dictionary = {}
with fn.open(districts_filename, 'r') as districts:
    for feature in districts:
        district_id = int(feature['id'])
        districts_dictionary[district_id] = {
            'District Code': feature['properties']['DIST_PCODE'],
            'District Name': feature['properties']['DISTRICT_N'],
            'Population Count': 0,
            'Car: Pop. with access': 0,
            'Car: Pop. with access [%]': 0.0,
            'Foot: Pop. with access': 0,
            'Foot: Pop. with access [%]': 0.0,
            'geometry': feature['geometry']
        }
print('created dictionary for %s districts' % len(districts_dictionary))

facilities_dictionary = {}
with fn.open(health_facilities_filename, 'r') as facilities:
    for feature in facilities:
        facility_id = int(feature['id'])
        facilities_dictionary[facility_id] = {
            'geometry': feature['geometry']
        }
print('created dictionary for %s facilities' % len(facilities_dictionary))
# -

# ### Let's get an overview and look at a map of the districts and health facilities

# +
map_outline = folium.Map(tiles='Stamen Toner', location=([-18.812718, 46.713867]), zoom_start=5)

# Import health facilities
cluster = MarkerCluster().add_to(map_outline) # To cluster hospitals

for facility_id in facilities_dictionary:
    folium.Marker(list(reversed(facilities_dictionary[facility_id]['geometry']['coordinates']))).add_to(cluster)

# Import district boundaries
district_simp = []
for district_id in districts_dictionary:
    geom = shape(districts_dictionary[district_id]['geometry'])
    # we simplify the geometry just for the purpose of visualisation
    # be aware that some browsers e.g. chrome might fail to render the entire map if there are to many coordinates
    simp_geom = geom.simplify(0.005, preserve_topology=False)
    simp_coord = mapping(simp_geom)
    folium.GeoJson(simp_coord).add_to(map_outline)
    district_simp.append(simp_coord)

map_outline.save(os.path.join('results', '1_health_facilities_overview.html'))
map_outline
# -

# ## Analysis
# We will follow these steps:
# * Get Isochrones from openrouteservice
# * Compute Health Access Area per District
# * Compute Population Count per District
# * Compute Population with Access per District
# * Save output as GeoJSON file

# ### Get Isochrones from openrouteservice
# The accessibility of hospitals in a one-hour range is of note.
# Therefore, isochrones with a one-hour walk range and one-hour car drive range around each hospital were created with
# the open source tool openrouteservice.
# This might take several minutes depending on the number of health facilities
# (currently we can send 40 requests per minute).

# +
# request isochrones from ORS api for car
request_counter = 0
iso_car = []
for facility_id in facilities_dictionary.keys():
    loc = facilities_dictionary[facility_id]
    try:
        iso_params = {'locations': loc['geometry']['coordinates'],
                          'profile': 'driving-car',
                          'range_type': 'time',
                          'segments': 3600, # 3600 = 1hour
                          'attributes': {'total_pop', 'area'}}

        request = ors.isochrones(**iso_params)
        request_counter += 1

        lon, lat = loc['geometry']['coordinates']
        iso_car.append(shape(request['features'][0]['geometry']))
        if len(iso_car) % 39 == 0:
            time.sleep(60)
    except Exception as err:
        pass
print('requested %s isochrones for car from ORS API' % request_counter)

# generate cascaded union of all isochrones
iso_union_car = cascaded_union(iso_car)
print('computed cascaded union of all isochrones')


# save isochrones to shapefiles
schema = {'geometry': 'Polygon',
              'properties': {'id': 'int'}}
index = 0
with fn.open(isochrones_car_filename, 'w', 'ESRI Shapefile', schema) as c:
    for poly in iso_union_car:
        index += 1
        c.write({'geometry': mapping(poly),
                 'properties': {'id': index}})
print('saved isochrones as shapefiles for car.')

# +
# request isochrones from ORS api for pedestrian
request_counter = 0
iso_foot = []
for facility_id in facilities_dictionary.keys():
    loc = facilities_dictionary[facility_id]
    try:
        iso_params = {'locations': loc['geometry']['coordinates'],
                          'profile': 'foot-walking',
                          'range_type': 'time',
                          'segments': 3600, # 3600 = 1hour
                          'attributes': {'total_pop', 'area'}}
        request = ors.isochrones(**iso_params)
        request_counter += 1

        lon, lat = loc['geometry']['coordinates']
        iso_foot.append(shape(request['features'][0]['geometry']))
        if len(iso_foot) % 39 == 0:
            time.sleep(60)
    except Exception as err:
        pass
print('requested %s isochrones for foot from ORS API' % request_counter)

# generate cascaded union of all isochrones
iso_union_foot = cascaded_union(iso_foot)
print('computed cascaded union of all isochrones')


# save isochrones to shapefiles
schema = {'geometry': 'Polygon',
              'properties': {'id': 'int'}}
index = 0
with fn.open(isochrones_foot_filename, 'w', 'ESRI Shapefile', schema) as c:
    for poly in iso_union_foot:
        index += 1
        c.write({'geometry': mapping(poly),
                 'properties': {'id': index}})
print('saved isochrones as shapefiles for pedestrian.')
# -

# #### Let's look at the map of the isochrones

# +
# Create isochrones with one-hour foot walking range
map_isochrones = folium.Map(tiles='Stamen Toner', location=([-18.812718, 46.713867]), zoom_start=5) # New map for isochrones

def style_function(color): # To style isochrones
    return lambda feature: dict(color=color)

union_coord_car = mapping(iso_union_car)
for l in union_coord_car['coordinates']:
    switched_coords = [[(y,x) for x,y in l[0]]]
    folium.features.PolygonMarker(switched_coords,
                            color='#ff751a',
                             fill_color='#ff751a',
                            fill_opacity=0.2,
                             weight=3).add_to(map_isochrones)

union_coord_foot = mapping(iso_union_foot)
for l in union_coord_foot['coordinates']:

    switched_coords = [[(y,x) for x,y in l[0]]]
    folium.features.PolygonMarker(switched_coords,
                            color='#ffd699',
                             fill_color='#ffd699',
                            fill_opacity=0.2,
                             weight=3).add_to(map_isochrones)

map_isochrones.save(os.path.join('results', '2_isochrones.html'))
map_isochrones
# -

# ### Compute Health Access Area per District

# +
# schema of the new shapefile
schema =  {'geometry': 'Polygon',
           'properties': {'district_fid': 'int'}}

# creation of the new shapefile with the intersection for car
car_iso_district_dict = {}
foot_iso_district_dict = {}

counter = 0
with fn.open(isochrones_car_per_district_filename, 'w',driver='ESRI Shapefile', schema=schema) as output:
    for district in fn.open(districts_filename):
        for isochrone in fn.open(isochrones_car_filename):
            if shape(district['geometry']).intersects(shape(isochrone['geometry'])):
                prop = {'district_fid': district['id']}
                car_iso_district_dict[counter] = district['id']
                output.write({'geometry':mapping(shape(district['geometry']).intersection(shape(isochrone['geometry']))),'properties': prop})
                counter += 1
print('created %s isochrones per district for car' % counter)

# creation of the new shapefile with the intersection for pedestrian
counter = 0
with fn.open(isochrones_foot_per_district_filename, 'w',driver='ESRI Shapefile', schema=schema) as output:
    for district in fn.open(districts_filename):
        for isochrone in fn.open(isochrones_foot_filename):
            if shape(district['geometry']).intersects(shape(isochrone['geometry'])):
                prop = {'district_fid': district['id']}
                foot_iso_district_dict[counter] = district['id']
                output.write({'geometry':mapping(shape(district['geometry']).intersection(shape(isochrone['geometry']))),'properties': prop})
                counter += 1
print('created %s isochrones per district for pedestrian' % counter )
# -

# ### Compute Population Count per District
# The population data were given as a raster file for the whole country. In this study the focus lies on the single
# districts why the data has to be reduced down to the given district boundaries.
# The population data is a prediction for 2020.
# This has to be considered when comparing with the health sites data (from 2018).

stats = zonal_stats(districts_filename, population_raster_filename, nodata_value=-999, global_src_extent=False)
total_population = 0
for element in stats:
    district_id = int(element['fid'])
    districts_dictionary[district_id]['Population Count'] = element['sum']
    total_population += element['sum']
print('computed population count per district.')
print('Madagascar has a total population of %s inhabitants.' % int(total_population))

# ### Compute Population with Access per District
# To receive the percentage of population with access to health facilities per district,
# the amount of people with access per district were divided by the districts inhabitants and multiplied by 100.

# +
# compute zonal statistics for car
stats_car = zonal_stats(isochrones_car_per_district_filename, population_raster_filename, nodata_value=-999, global_src_extent=False)
for element in stats_car:
    district_id = int(car_iso_district_dict[element['fid']])
    try:
        pop_iso = districts_dictionary[district_id]['Car: Pop. with access'] + element['sum']
        pop_total = districts_dictionary[district_id]['Population Count']
        districts_dictionary[district_id]['Car: Pop. with access'] = pop_iso
        districts_dictionary[district_id]['Car: Pop. with access [%]'] = 100 * pop_iso / pop_total
    except:
        pass
print('computed population count with access per district for car.')


# compute zonal statistics for pedestrian
stats_foot = zonal_stats(isochrones_foot_per_district_filename, population_raster_filename, nodata_value=-999, global_src_extent=False)
for element in stats_foot:
    district_id = int(foot_iso_district_dict[element['fid']])
    try:
        pop_iso = districts_dictionary[district_id]['Foot: Pop. with access'] + element['sum']
        pop_total = districts_dictionary[district_id]['Population Count']
        districts_dictionary[district_id]['Foot: Pop. with access'] = pop_iso
        districts_dictionary[district_id]['Foot: Pop. with access [%]'] = 100 *pop_iso / pop_total
    except:
        pass
print('computed population count with access per district for foot.')
# -

# ### Save Output

# +
# save data from districts dictionary as shapefiles
schema = {'geometry': 'Polygon',
          'properties': {
              'code': 'str',
              'name': 'str',
              'pop_count': 'float',
              'pop_car': 'float',
              'pop_car_perc': 'float',
              'pop_foot': 'float',
              'pop_foot_perc': 'float'
          }
         }

with fn.open(output_file, 'w', driver='GeoJSON', schema=schema) as c:
    for district_id in districts_dictionary.keys():
        props = {
              'code': districts_dictionary[district_id]['District Code'],
              'name': districts_dictionary[district_id]['District Name'],
              'pop_count': districts_dictionary[district_id]['Population Count'],
              'pop_car': districts_dictionary[district_id]['Car: Pop. with access'],
              'pop_car_perc': districts_dictionary[district_id]['Car: Pop. with access [%]'],
              'pop_foot': districts_dictionary[district_id]['Foot: Pop. with access'],
              'pop_foot_perc': districts_dictionary[district_id]['Foot: Pop. with access [%]']
        }


        # we simplify the geometry
        geom = shape(districts_dictionary[district_id]['geometry'])
        # we simplify the geometry just for the purpose of visualisation
        # be aware that some browsers e.g. chrome might fail to render the entire map if there are to many coordinates
        simp_geom = geom.simplify(0.005, preserve_topology=False)
        c.write({'geometry': mapping(simp_geom),
                 'properties': props})
print('created %s with all information.' % output_file)
# -

# ## Results
# The table shows the results of the analysis ordered by districts.
# Two choropleth maps were created, one with the population percentage with access by foot and one with access by car.

# show attributes
df_total = pd.DataFrame.from_dict(districts_dictionary, orient='index')
display(pd.DataFrame.from_dict(districts_dictionary, orient='index').round(2)[0:5])
print('display first 5 entries of the final results.')

# #### Show Map for Access to Health Facilities by Car

# +
map_choropleth_car = folium.Map(tiles='Stamen Toner', location=([-18.812718, 46.713867]), zoom_start=5)
map_choropleth_car.choropleth(geo_data = output_file,
                          data = df_total,
                          columns= ['District Code','Car: Pop. with access [%]'],
                          key_on = 'feature.properties.code',
                          fill_color='BuPu',
                          legend_name='Car: Pop. with access [%]')

map_choropleth_car.save(os.path.join('results', '3a_choropleth_car.html'))
map_choropleth_car
# -

# #### Show Map for Access to Health Facilities by Foot

# +
map_choropleth_foot = folium.Map(tiles='Stamen Toner', location=([-18.812718, 46.713867]), zoom_start=5)
map_choropleth_foot.choropleth(geo_data = output_file,
                          data = df_total,
                          columns= ['District Code','Foot: Pop. with access [%]'],
                          key_on = 'feature.properties.code',
                          fill_color='BuPu',
                          legend_name='Foot: Pop. with access [%]')

map_choropleth_foot.save(os.path.join('results', '3b_choropleth_foot.html'))
map_choropleth_foot
# -

# ## Conclusion
# There is a small amount of hospitals in Madagascar, which are undistributed over the country.
# Consequently, a high percentage of the population don't have fast access to health sites.
# The findings show that the inhabitants of 69 of 119 districts don't have any access in a one-hour walking range,
# and those of 43 of 119 districts in a one-hour car driving range.
# The received maps (map_choropleth_foot and map_choropleth_car) show the population in percentage with access to
# health facilities by foot and by car.
#
# This study used open source data and tools. Therefore, results can be generated with a low amount money.
# However, free data and tools can have limits for the analysis.
# The data can show characteristics of incompleteness and inconsistency and the tools don't have for instance arranged
# support for users.
