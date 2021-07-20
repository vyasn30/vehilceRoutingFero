import requests
import json
import threading
import numpy as np
import osrm

f = open("data.json")
data = json.load(f)

coorlist = [
              [float(order["destination"].split(",")[0]),
               float(order["destination"].split(",")[1])]
              for order in data["orders"]
           ]

coorlist.insert(0, [25.131419, 51.616930])
distanceMatrix = [[0 for i in range(len(coorlist))] for j in range(len(coorlist))]

osrm.RequestConfig.host=f"http://192.168.1.23:5000/"
print(coorlist)