import requests
import json
import threading
import numpy as np

f = open("data.json")
data = json.load(f)

coorlist = [
              [float(order["destination"].split(",")[0]), 
               float(order["destination"].split(",")[1])

               for order in data["orders"]
            ]


            
