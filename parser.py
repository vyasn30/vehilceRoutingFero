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

for coor in coors:
  print(coor.latitude, coor.longitude)

names = [order["destination_address"] for order in data["orders"]]
names.insert(0, "depot_node")

handoverTimes = [order["handover_time"]  for order in data["orders"]]
handoverTimes.insert(0, 0)

demands = [order["quantity"] for order in data["orders"]]
demands.insert(0, 0)

depotNode = 0
avg_speed = data["avg_speed"]
network = vrpLevers.Network(depotNode, vehicleNumber, vehicles = totalVehicles, avgSpeed = avg_speed)


for i in range(0, len(coors)):
  newNode = vrpLevers.Node(coors[i], demands[i], processingTime = handoverTimes[i])
  network.addNodeToNetwork(newNode)

  

dataModel = vrpLevers.DataModel(network)
dataModel.assignNames(names)


data = dataModel.getData()
print(data["distance_matrix"])
vrp = vrpLevers.vrpWrap(data)
solution = vrp.solve()

vrp.print_solution()



