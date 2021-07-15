import requests
import json
import threading
import numpy as np

f = open("data.json")
data = json.load(f)

coorlist = [
              [float(order["destination"].split(",")[0]), 
               float(order["destination"].split(",")[1])]
              for order in data["orders"]
           ]
coorlist.insert(0, [25.131419, 51.616930])
distanceMatrix = [[0 for i in range(len(coorlist))] for j in range(len(coorlist))]


def getURL(coor1, coor2):
  url = "https://uat.chefme.fero.ai/routing/route/v1/driving/"
  url += str(coor1[1])
  url += ","
  url += str(coor1[0])
  url += ";"
  url += str(coor2[1])
  url += ","
  url += str(coor2[0])
  url += "?overview=false"

  return url

def getDistance(url):
  r = requests.get(url)

  return r.json()["routes"][0]["distance"]/1000

  
def getDistanceMatrix():
  for i in range(len(coorlist)):
    for j in range(len(coorlist)):
      try:
        if i==j:
          continue
        elif i<j:
          print(i, j)
          url = getURL(coorlist[i], coorlist[j])
      
          distanceMatrix[i][j] = getDistance(url)
          print(distanceMatrix[i][j])

        else:
          distanceMatrix[i][j] = distanceMatrix[j][i]
        
      except:
        distanceMatrix[i][j] = distanceMatrix[i][j-1]

threads = []
"""
for i in range(50):
  t = threading.Thread(target=getDistanceMatrix)
  t.daemon = True
  threads.append(t)


for i in range(50):
  threads[i].start()

for i in range(50):
  threads[i].join()

"""
getDistanceMatrix()
print(distanceMatrix)
distanceArray = np.array(distanceMatrix)
np.save("distanceMatrix", distanceArray)
