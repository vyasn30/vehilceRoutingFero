# VRP

Vehicle Route Planning 

### Current Optimization

* Single Trip Optimization: Single driver's trip optimization
  File: Single_Trip_Optimization.py
* Multiple driver Optimization: Resource Utilization (minizing distance + no. of drivers)
  FIle: VRPSPD_ortools_v1.py
* Multiple driver with time window Optimization: Resource Utilization (minizing distance + no. of drivers within time window)
  FIle: VRPSPDTW_ortools_v1.py

Installation:

Requirements: Python 3.7
(Might create virtual env if needed)

1. pip install requirements.txt 
2. Repo don't include "google_distance_matrix.txt" file which includes api key for distance matrix.
   Copy paste file into this folder.

3. run celery workers
   ```bash
   celery -A VRP_server_celery.celery worker --loglevel=debug -f celery_worker_log
   ```
   (config setting: log files)
   
4. run flask server.
   ```bash
   gunicorn --access-logfil vrp_optimize_server_log -b 127.0.01:5001 -w 2 wsgi:app
   ```
   (config setting: 2 workers, 5001 port and info level logger)
  
   or run server with python.
      ```bash
      python VRP_server_celery.py
      ```
      
 ## Setting up the osrm on local server
 
 Download the map with following code:
 ```bash
   wget http://download.geofabrik.de/asia/gcc-states-latest.osm.pbf
   ```
 Pre-process the extract with the car profile and start a routing engine HTTP server on port 5000
 ```bash
   sudo docker run -t -v "${PWD}:/data" osrm/osrm-backend osrm-extract -p /data/car.lua /data/gcc-states-latest.osm.pbf
   ```
 Run the following commands to extract the graph data and store it on the local server for further use:
 ```bash
   sudo docker run -t -v "${PWD}:/data" osrm/osrm-backend osrm-partition /data/gcc-states-latest.osrm
   sudo docker run -t -v "${PWD}:/data" osrm/osrm-backend osrm-customize /data/gcc-states-latest.osrm
   ```
 Now, run the docker on the backen on port 5000:
 ```bash
   sudo docker run -d --restart unless-stopped -t -i -p 5000:5000 -v "${PWD}:/data" osrm/osrm-backend osrm-routed --algorithm mld --max-matching-size 7500 /data/gcc-states-latest.osrm
   ```
 To check whether it works, type the following in terminal and see if you get the proper output:
  ```bash
   curl "http://127.0.0.1:5000/route/v1/driving/55.1377716,25.1126852;55.1034942,25.1171059?steps=true&overview=false"
   ```
 If the default RequestConfig host for osrm is not set to local machine, type the followng in your python script:
  ```bash
   osrm.RequestConfig.host = "https://localhost:5000"
   ```     
   

### Paramters included:

Round-trip option and storage-type based planning.

To use the round-trip option, include the following flag in in the input payload(0 for open-loop 1 for round-trip; default - 1):
```bash
   "round": 0
   ```     
Generally, when the delivery or pick-up is from the same location excepet the warehouse, the hand-over time is added only once. However, that parameter has been exposed as the following flag flag in in the input payload(0 to not add each hand-over, 1 to add each hand-over regardless of the location; default - 0):
```bash
   "repeat_handover": 0
   ```     

For storage based  planning, we need to include storage type for individual oders as well as drivers. 
In orders, inlcude the following flag:
```bash
   "storage": "F"
   ```     
The flags available for storage type are:

* "F" for Frozen storage
* "C" for Chilled storage
* "D" for Dry storage

For drivers, include the flags which include available for the vehicle assigned as follows:
```bash
   "storage": "FC"
   ```     
If some storage type is unavailable, one can exclude it in the flag or simply add X instead. Some examples are as follows:
* "FC" or "FCX" - Frozen and Chilled storage available; Dry storage not available
* "D" or "XXD" - Only Dry avaialable; Frozen and Chilled storage unavailable

An example payload has been provided named example_payload.json

NOTE: If no storage parameters are provided, the planning will be done as usual i,e., storage-type invariant planning.

The following endpoints are provided in this API:

1. VRP for single trip optimization
2. VRP for multiple drivers with contsraints like time-window and capacity
3. Route-matching to plot the actual path data points gathered on the map
4. ETA estimation for each driver 
5. Task status update for both single trip and VRPSPDTW
6. Debug to get last 'n' requests and their outputs
7. Ideal route plotter to plot the ideal route given the list of locations for a given driver
