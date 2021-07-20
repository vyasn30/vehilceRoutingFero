# import collections

# # import requests
# import json
# import urllib.request
# import requests


# def get_file_contents(filename):
#     """
# 		Given a filename,
#         return the contents of that file
#     """
#     try:
#         with open(filename, "r") as f:
#             # It's assumed our file contains a single line,
#             # with our API key
#             return f.read().strip()
#     except FileNotFoundError:
#         print("'%s' file not found" % filename)


# # don't push text to git repo
# API_key = get_file_contents("google_distance_matrix.txt")


# def create_distance_matrix(addresses, API_key):

#     # Distance Matrix API only accepts 100 elements per request, so get rows in multiple requests.
#     max_elements = 100
#     num_addresses = len(addresses)
#     # Maximum number of rows that can be computed per request
#     max_rows = max_elements // num_addresses
#     # num_addresses = q * max_rows + r
#     q, r = divmod(num_addresses, max_rows)
#     dest_addresses = addresses
#     distance_matrix = []
#     # Send q requests, returning max_rows rows per request.
#     for i in range(q):
#         origin_addresses = addresses[i * max_rows : (i + 1) * max_rows]
#         response = send_request(origin_addresses, dest_addresses, API_key)
#         distance_matrix += build_distance_matrix(response)

#     # Get the remaining remaining r rows, if necessary.
#     if r > 0:
#         origin_addresses = addresses[q * max_rows : q * max_rows + r]
#         response = send_request(origin_addresses, dest_addresses, API_key)
#         distance_matrix += build_distance_matrix(response)
#     return distance_matrix


# def send_request(origin_addresses, dest_addresses, API_key):
#     """ Build and send request for the given origin and destination addresses."""

#     def build_address_str(addresses):
#         # Build a pipe-separated string of addresses
#         address_str = ""
#         for i in range(len(addresses) - 1):
#             address_str += addresses[i] + "|"
#         address_str += addresses[-1]
#         return address_str

#     request = "https://maps.googleapis.com/maps/api/distancematrix/json?units=imperial"
#     origin_address_str = build_address_str(origin_addresses)
#     dest_address_str = build_address_str(dest_addresses)
#     request = (
#         request
#         + "&origins="
#         + origin_address_str
#         + "&destinations="
#         + dest_address_str
#         + "&key="
#         + API_key
#     )
#     jsonResult = urllib.request.urlopen(request).read()
#     response = json.loads(jsonResult)
#     return response


# def build_distance_matrix(response):
#     distance_matrix = []
#     for row in response["rows"]:
#         row_list = [
#             row["elements"][j]["distance"]["value"] for j in range(len(row["elements"]))
#         ]
#         distance_matrix.append(row_list)
#     return distance_matrix


# def distance_matrix(locations):
#     print(locations)
#     unique_nodes = dict()
#     cnt = 0
#     N = len(locations)
#     for i in locations:
#         if not i in unique_nodes:
#             unique_nodes[i] = cnt
#             cnt += 1

#     unique_distance_matrix = create_distance_matrix(list(unique_nodes.keys()), API_key)

#     print(unique_distance_matrix)

#     full_distance_matrix = [[0 for _ in range(N)] for _ in range(N)]

#     for i_idx, i in enumerate(locations):
#         for j_idx, j in enumerate(locations):
#             full_distance_matrix[i_idx][j_idx] = (
#                 unique_distance_matrix[unique_nodes[i]][unique_nodes[j]] // 1000
#             )  # google return in meters, so converting into KMs
#     # print (full_distance_matrix)
#     return full_distance_matrix

