import json
import vrpLevers 

f = open('data.json', )
data = json.load(f)
#print(data["orders"])

nodes = []

vehicleNumber = len(data["drivers"])

totalVehicles = [vrpLevers.Vehicle(driver["capacity_of_vehicle"], driver["max_utilized_capacity_of_vehicle"]) for driver in data["drivers"]]

coors = [vrpLevers.Coors(order["destination"]) for order in data["orders"]]
coors.insert(0, vrpLevers.Coors(data["warehouse_location"]))

handoverTimes = [order["handover_time"]  for order in data["orders"]]


demands = [order["quantity"] for order in data["orders"]]
depotNode = 0

network = vrpLevers.Network(depotNode, vehicleNumber, vehicles = totalVehicles)
print(len(coors))



for i in range(0, len(coors)-1):
  newNode = vrpLevers.Node(coors[i], demands[i], processingTime = handoverTimes[i])
  network.addNodeToNetwork(newNode)


data = vrpLevers.DataModel(network).getData()

print(data)


