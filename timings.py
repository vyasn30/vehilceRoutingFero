from datetime import datetime
import requests
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim

key = "hw5ODt9aNcsJZfFmk8XVcRrU1VQx7zWa" 

def geoStringsToCoors(geoStringList):
  coorList = []
  for geoString in geoStringList:
    locator = Nominatim(user_agent = "myGeocoder")
    location = locator.geocode(geoString)
    coor = []
    coor.append(location.latitude)
    coor.append(location.longitude)
    coorList.append(coor)

  return coorList


def getTimeMatrix(geoStringList):
  geoList = geoStringsToCoors(geoStringList)
  timeMatrix = [[0 for i in range(len(geoList))] for j in range(len(geoList))]

  for i in range(len(geoList)):
    for j in range(len(geoList)):
      if i==j:
        continue
      
      timeMatrix[i][j] = getTime(geoList[i], geoList[j])

  return timeMatrix
      



def getTime(coor1, coor2):
  r = requests.get(
    "https://api.tomtom.com/routing/1/calculateRoute/" +str    (coor1[0])+ "," + str(coor1[1]) + ":" + str(coor2[0])    + "," + str(coor2[1]) + "/xml?avoid=unpavedRoads&key=" + key
  )

  
  c = r.content
  soup = BeautifulSoup(c, "html.parser")
  soup.prettify()
  
  travelTime = int(soup.find('traveltimeinseconds').get_text())
  return travelTime


def incrementalStamps(timestamps, timeWindows):
  startingTime_ref = timestamps[0][0]
  incrementalSteps = []

  for val in timestamps:
    temp = []
    openTime = (val[0] - startingTime_ref)/60
    endTime = (val[1] - startingTime_ref)/60
    temp.append(openTime)
    temp.append(endTime)
    temp = tuple(temp)
    incrementalSteps.append(temp)
  
  return incrementalSteps
  
    
  
  



def convertToTimeStamps(timeWindows):
  
  timeStamps = []

  for val in timeWindows:
    temp = []
    temp.append(datetime.strptime(val[0], '%d/%m/%Y %H:%M:%S').timestamp())
    temp.append(datetime.strptime(val[1], '%d/%m/%Y %H:%M:%S').timestamp())

    timeStamps.append(temp)

  return timeStamps
 

if __name__=="__main__":
  geoStringList = ["Ambawadi Circle, Ahmedabad", "Club 07, Bopal", "Naroda Patiya", "The Fern Hotel, Sola", "Trimandir, Adalaj"]
  
  #getTimeMatrix(geoStringList)
  timeWindows = [
  ("08/07/2021 06:00:00", "08/07/2021 09:00:00"),
  ("08/07/2021 10:00:00", "08/07/2021 12:00:00"),
  ("08/07/2021 12:30:00", "08/07/2021 13:30:00"), 
  ("08/07/2021 14:40:00", "08/07/2021 15:30:00"), 
  ("08/07/2021 16:50:00", "08/07/2021 17:20:00")
  ]
 
  timeStamps = convertToTimeStamps(timeWindows)
  incrementalTimeSteps = incrementalStamps(timeStamps, timeWindows)
  print(incrementalTimeSteps)
