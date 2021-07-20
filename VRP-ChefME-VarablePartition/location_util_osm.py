from geopy.geocoders import Nominatim
from collections import defaultdict
from geopy.distance import geodesic
from math import radians, cos, sin, asin, sqrt
import osrm
import os
# import urllib

osrm.RequestConfig.host=f"https://uat.chefme.fero.ai/routing/route/v1/driving/:{os.environ.get('OSRM_PORT', 5000)}"
import logging

logger = logging.getLogger(__name__)
logger.info(os.environ.get('OSRM_PORT'))
geolocator = Nominatim(user_agent="VRP Opt 1")


def location_to_latlong(location):
    """
    convert given location string (comma seperated lat lnog) to latlong
    """
    lat, long = map(float, location.split(","))
    return (lat, long)


def location_to_latlong_dict(locations):
    """
        given locations, return only unique locations with dict 
    """

    unique_nodes = dict()
    for i, j in locations:
        if not i in unique_nodes:
            unique_nodes[i] = location_to_latlong(i)
        if not j in unique_nodes:
            unique_nodes[j] = location_to_latlong(j)

    return unique_nodes


def haversine(latlon1, latlon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians
    
    latlon1 = latlon1[1], latlon1[0]
    latlon2 = latlon2[1], latlon2[0]
    # lon1, lat1 = lonlat1
    # lon2, lat2 = lonlat2
    # lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # haversine formula
    # dlon = lon2 - lon1
    # dlat = lat2 - lat1
    # a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    # c = 2 * asin(sqrt(a))
    # Radius of earth in kilometers is 6371
    # km = 6371 * c
    try:
        dist = osrm.simple_route(latlon1,latlon2,output='route',overview='full',geometry='wkt')
    except Exception as e :
        logger.exception(e)
        logger.debug("exception while connecting to OSRM.")
    else:
        km = dist[0]['distance']/1000
        # print(km)
        # km = 6371 * c
        return km


def distance_matrix(locations):
    """
        Given list of locations, return distance matrix between them.
        Below code is optimized to only calculated distance between unique location, 
        and return full matrix from that.
    """
    unique_nodes = dict()
    for i in locations:
        if not i in unique_nodes:
            unique_nodes[i] = location_to_latlong(i)

    unique_nodes_graph = dict()
    for i in unique_nodes.keys():
        for j in unique_nodes.keys():

            # following is heurisitc is applied to increase haversine distance
            # general idea is that distance between place is city is much higher than haversine
            # but distance between city is not that high compared to haversine distance.
            temp_dist = 1.1*haversine(unique_nodes[i], unique_nodes[j]) #initially multiplied by 1.5
#             if temp_dist < 10:
#                 temp_dist *= 1.6
#             elif temp_dist < 20:
#                 temp_dist *= 1.5
#             elif temp_dist < 40:
#                 temp_dist *= 1.25
#             else:
#                 temp_dist *= 1.1

            unique_nodes_graph[i + j] = temp_dist

    full_graph = [[0 for _ in locations] for _ in locations]

    for i, il in enumerate(locations):
        for j, jl in enumerate(locations):
            full_graph[i][j] = unique_nodes_graph[il + jl]

    return full_graph


if __name__ == "__main__":
    # keep in mind, lat long cannot be given reversed
    # current implementation supports lat,long and not long,lat
    print(haversine((72.551270, 23.069804), (72.534526, 23.01781)))
    print(haversine((23.069804, 72.551270), (23.01781, 72.534526)))

