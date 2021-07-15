import osrm

client = osrm.Client(host='https://uat.chefme.fero.ai/routing/')

response = client.route(
    coordinates=[[-74.0056, 40.6197], [-74.0034, 40.6333]],
    overview=osrm.overview.full)

print(response)

