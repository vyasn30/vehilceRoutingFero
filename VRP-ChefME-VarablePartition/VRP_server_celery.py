import json
import time
import osrm

from celery import Celery
from copy import deepcopy
from flask import Flask, request, jsonify, url_for, redirect

from VRPSPD_ortools_v1 import VRPSPD_ortools
from Single_Trip_Optimize import Single_Trip
from VRPSPDTW_ortools import VRPSPDTW_ortools
from validation_json_schema import VRPSPD_data_schema, VRPSPDTW_data_schema
from celery.utils.log import get_task_logger
from persistent_storage import CeleryTask_model, CeleryTask_Query, db_Session, engine
from location_util_osm import haversine

from rdp import rdp 
from statistics import mean

# Flask configration
app = Flask(__name__)
app.config["CELERY_BROKER_URL"] = "redis://localhost:6379/4"
app.config["CELERY_RESULT_BACKEND"] = "redis://localhost:6379/4"

# celery configration
celery = Celery(app.name, broker=app.config["CELERY_BROKER_URL"])
celery.conf.update(app.config)
celery_logger = get_task_logger(__name__)

# database wrapper init
ct_query_engine = CeleryTask_Query()


def standard_response(status, message, data):
    """
    standard response format
    """
    response = {}
    response["status"] = status
    response["message"] = message
    response["data"] = data
    return response


def celery_task_id_verify(task_id):
    """
    celery task id pattern checker
    """
    if "-" in task_id and task_id.count("-") == 4:
        return True
    return False


def check_data_v1(req):
    """
        check VRPSPD request data format
    """
    inputs = VRPSPD_data_schema(req)
    data = req.json

    if inputs.validate():
        last_n = len(data["orders"])
        # check if orders don't have location
        data["new_orders"] = [
            order
            for order in data["orders"]
            if not (
                "none" in order["source"].lower()
                or "none" in order["destination"].lower()
            )
        ]
        # if some orders has no location, excluded those order
        # and remove those orders list
        if last_n != len(data["new_orders"]):
            data["excluded_orders"] = [
                order["order_id"]
                for order in data["orders"]
                if (
                    "none" in order["source"].lower()
                    or "none" in order["destination"].lower()
                )
            ]
            data["orders"] = data["new_orders"]
        return True, None
    else:
        return False, inputs.errors


def unroll_data_v1(data):
    """
        unrool VRPSPD data request format to match internal formats
        basically convert json object to arrays.
    """
    data["depot_location"] = data["warehouse_location"]
    data["total_orders"] = len(data["orders"])
    data["do_numbers"] = []
    data["locations_of_orders"] = []
    data["delivery_sizes"] = []
    data["type_of_orders"] = []

    for order in data["orders"]:
        data["do_numbers"].append(order["order_id"])
        data["locations_of_orders"].append([order["source"], order["destination"]])
        data["delivery_sizes"].append(order["quantity"])
        data["type_of_orders"].append(1 if order["order_type"] == "pickup" else 0)

# -----------------------------------------------------------------
# -------------Snapping Route to Nearest Road Network--------------
# -----------------------------------------------------------------

#Function to extract meaningful result from snapped data
def mkjson(route):
    lat = []
    lon = []
    dump = []
    confidence = []
    distance = []

    stat = {"Average Confidence": 0, "Distance(km)": 0, "Locations": []}

    for match in route["matchings"]:

        confidence.append(float(match["confidence"]))
        distance.append(float(match["distance"]))

        for i in match["geometry"]["coordinates"]:
            stat["Locations"].append({"lat": i[1], "long": i[0]})
        

    stat["Average Confidence"] = mean(confidence) * 100
    stat["Distance(km)"] = sum(distance)/1000 #in km

    dump.append(stat)   	 		
   	 		
    return dump

#Extracting lat, long from the input data
def extract(data):

    points = []
    i = 0
    ts = []

    for loc in data:
        
        points.append((float(loc["long"]), float(loc["lat"])))
        ts.append(float(loc["ts"]))  #extracting  timestamps

    return points, ts

#Function to clean the data using Ramer-Douglas-Peucker Algorithm
def clean(points):
    return rdp(points)

@app.route("/routeoptimization/routematching/snapping", methods=["POST"])
def match_endpoint_v1():
    """
        Endpoint for snapping the points
    """
    data = request.json
    points, timestamps = extract(data)            #extracting the coords and storing

    douglas = clean(points)   #removing the noisy/unwanted points from the data

    r = [] #radius of uncertainity for each measurement

    for i in range(len(douglas)):
        r.append(20.0)

    act_route = osrm.match(douglas, radius=r, overview='simplified', geometry='geojson', tidy=True)     #generating the snapped points

    out_snapped = mkjson(act_route)

    resp = standard_response(
        status="SUCCESS", message="Points Snapped!", data=out_snapped
    )

    
    return jsonify(resp), 200

# ------------------------------------------------------------------
# ------------------------------------------------------------------
# ------------------------------------------------------------------ 

# ------------------------------------------------------------------
# --------------------ETA For Given Driver--------------------------
# ------------------------------------------------------------------      
#Extracting useful data from the raw data
def extract_eta(data):

    destination = []
    order_ids = []
    handover_times =  []

    for order in data["orders"]:
        destination.append((order["lat"],order["long"]))
        order_ids.append(order["order_id"])
        handover_times.append(order["handover_time"])

    return destination, order_ids, handover_times

@app.route("/routeoptimization/routematching/eta", methods=["POST"])
def eta_endpoint():
    """
        Endpoint for getting ETA of the given driver
    """
    data = request.json
    locations, order_ids, handover_times = extract_eta(data)

    current_time = data["current_time"]
    current_loc = (data["current_lat"],data["current_long"])
    avg_speed = data["avg_speed"]/60 #in km/min
    
    #Generating output json template
    stat = {"Current Location": "{},{}".format(current_loc[0],current_loc[1]), "Current Time":current_time, "ETA Table": []}


    for d in range(len(locations)):

        distance = haversine(current_loc,locations[d])
        time = distance/float(avg_speed) + float(handover_times[d])
        stat["ETA Table"].append({"OrderID":order_ids[d],"handover_time": handover_times[d], "ETA":round(time + current_time)})#time+current_time
        current_loc = locations[d]
        current_time = time + current_time


    

    resp = standard_response(
        status="SUCCESS", message="ETA Generated", data=stat
    )

    
    return jsonify(resp), 200

# ------------------------------------------------------------------
# ------------------------------------------------------------------
# ------------------------------------------------------------------

# ------------------------------------------------------------------
# --------------------Ideal Route Plotting--------------------------
# ------------------------------------------------------------------ 

#Extracting lat long from LINESTRING output of simple_route function
def mkjson_ideal(ideal_route):

    lat = []
    lon = []

    for i in ideal_route[0]["geometry"][12:-1].split(","):
        lat.append(float(i.split(" ")[1]))
        lon.append(float(i.split(" ")[0]))


    stat = {"Distance(km)": ideal_route[0]["distance"]/1000, "Duration": ideal_route[0]["duration"], "Directions":[]}

    for j in range(len(lat)):
        stat["Directions"].append({"lat":lat[j], "long":lon[j]})

    return stat


#Extracting lat, long from the input data
def extract_ideal(data):

    points = []    

    for loc in data:

        points.append([float(loc["lng"]), float(loc["lat"])])

    return points


@app.route("/routeoptimization/routematching/ideal", methods=["POST"])
def ideal_endpoint_v1():
    """
        Endpoint for plotting the ideal route
    """
    data = request.json

    points = extract_ideal(data)            #extracting the coords and storing


    ideal_route = osrm.simple_route(coord_origin=points[0], coord_dest=points[-1], coord_intermediate=points[1:-1], output='route', overview='full', geometry='wkt')     #generating the snapped points

    out_ideal = mkjson_ideal(ideal_route)

    resp = standard_response(
        status="SUCCESS", message="Ideal Route Generated", data=out_ideal
    )
    
    return jsonify(resp), 200


# ------------------------------------------------------------------
# ------------------------------------------------------------------
# ------------------------------------------------------------------


@celery.task(bind=True)
def VRPSPD_request_v1(self, data):
    """
    async function for VRPSPD optimization
    """

    engine.dispose()
    celery_logger.info(f"multiple driver input: {data}")

    # updating status in postgres
    ct_query_engine.update_task(
        self.request.id, status_msg="Working on Optimization", input_data=data
    )

    # recalculating capacity based on max util factor
    data["capacity_of_vehicles"] = [
        data["capacity_of_vehicles"][i] * data["max_utilized_capacity_of_vehicles"][i]
        for i in range(data["no_vehicles"])
    ]

    unroll_data_v1(data)

    try:
        # start solving optimization
        t1 = time.time()
        solver = VRPSPD_ortools(data)
        out_data = solver.solve()
        total_time = time.time() - t1

        # check for excluded orders
        out_data["excluded_orders"] = data.get("excluded_orders", [])
        out_data["time_taken_to_solve"] = int(total_time)

        celery_logger.info(f"multiple driver output: {out_data}")

        # update response in postgres
        ct_query_engine.update_task(
            self.request.id,
            status="SUCCESS",
            status_msg="Optimization Completed",
            out_data=out_data,
        )

        self.update_state(state="SUCCESS", meta={"result": out_data})

    except Exception as e:
        # update response in postgres
        ct_query_engine.update_task(
            self.request.id,
            status="FAILED",
            status_msg="Optimization Failed",
            # out_data=out_data,
        )
        celery_logger.info(f"Exception Handled on {self.request.id}")
        celery_logger.exception(e)
        self.update_state(state="FAILED")

    return {"status": "Task completed!"}


@app.route("/routeoptimization/optimize/multipledriver", methods=["POST"])
def VRPSPD_request_endpoint_v1():
    """
        End point for submiting VRPSPD task
        return celery task id as response
    """
    data = request.json
    # checking data
    validation_status, validation_msg = check_data_v1(request)
    if not validation_status:
        resp = standard_response(status="FAILED", message=validation_msg, data={})
        return jsonify(resp), 400
    # sending task to celery queue
    task = VRPSPD_request_v1.apply_async(args=[data])
    resp = standard_response(
        status="SUCCESS", message="Submitted to job queue", data={"task_id": task.id}
    )

    # adding task informatino into postgres
    ct = CeleryTask_model(
        id=task.id,
        status="PENDING",
        input_data=data,
        status_msg="Submitted to job queue",
        task_type="multiple driver",
    )
    ct_query_engine.insert(ct)

    return jsonify(resp), 200


@app.route("/routeoptimization/status/multipledriver/<task_id>", methods=["GET"])
def task_status_v1(task_id):
    """
    returns status of single trip optimization celery task
    """

    if not celery_task_id_verify(task_id):
        resp = standard_response(status="FAILED", message="Invalid task id", data={})
        return jsonify(resp), 400
    # checking from postgres
    task = ct_query_engine.get_task(task_id)
    out_data = task.out_data
    if out_data:
        order_input = dict()
        for order_dtl in task.input_data['orders']:
            operation = "deliver" if order_dtl["order_type"] == "delivery" else "pickup"
            order_input.update({
                order_dtl['order_id'] : {
                    "operation" : operation,
                    "location" : order_dtl["destination"] if operation == "deliver" else order_dtl["source"]
                }
            })
        warehouse_location = task.input_data["warehouse_location"].split(",")[::-1]
        warehouse_location = list(map(float, warehouse_location))
        total_distance = 0
        for i in  range(len(task.out_data["driver_trips"])):
            trip_dtl = task.out_data['driver_trips'][i]
            trip_orders = trip_dtl["trip_detail"]
            intermediate_locations = []
            for order in trip_orders:
                order_dtl = order_input[order["order_id"]]
                if order["operation"] == order_dtl["operation"]:
                    location = list(map(float, order_dtl["location"].split(",")[::-1]))
                    intermediate_locations.append(location)
            resp = osrm.simple_route(coord_origin=warehouse_location, coord_dest=warehouse_location,
                                         coord_intermediate=intermediate_locations)
            trip_distance = resp["routes"][0]["distance"] // 1000
            out_data["driver_trips"][i]["vehicle"]["distance_covered"] = trip_distance
            total_distance += trip_distance
        out_data["optimized_distance"] = total_distance

    if task:
        resp = standard_response(
            status=task.status, message=task.status_msg, data=out_data,
        )
    else:
        resp = standard_response(
            status="PENDING", message="task id not in persistent db", data={},
        )

    return jsonify(resp), 200


# ------------------------------------------------------------------
# ------------------------------------------------------------------
# ------------------------------------------------------------------


def check_data_single_trip(data):
    """
        Input data format is same as VRPSPD for single trip
        so reusing function
    """
    return check_data_v1(data)


def unroll_data_single_trip(data):
    """
        unrool single trip optimization data request format to match internal formats
        basically convert json object to arrays.
    """
    data["depot_location"] = data["warehouse_location"]
    data["total_orders"] = len(data["orders"])
    data["do_numbers"] = []
    data["locations_of_orders"] = []
    data["delivery_sizes"] = []
    data["type_of_orders"] = []

    for order in data["orders"]:
        data["do_numbers"].append(order["order_id"])
        data["locations_of_orders"].append([order["source"], order["destination"]])
        data["delivery_sizes"].append(order["quantity"])
        data["type_of_orders"].append(1 if order["order_type"] == "pickup" else 0)


@celery.task(bind=True)
def single_trip_optimize(self, data):
    """
        async function for single trip optimization
    """
    engine.dispose()

    celery_logger.info(f"single trip input: {data}")

    # updating status in postgres
    ct_query_engine.update_task(
        self.request.id, status_msg="Working on Optimization", input_data=data
    )

    # recalculating capacity based on max util factor
    data["capacity_of_vehicles"] = [
        data["capacity_of_vehicles"][i] * data["max_utilized_capacity_of_vehicles"][i]
        for i in range(data["no_vehicles"])
    ]

    unroll_data_single_trip(data)  # inplace dict update

    try:
        # start solving optimization
        t1 = time.time()
        solver = Single_Trip(data)
        out_data = solver.solve()
        total_time = time.time() - t1

        # check for excluded orders
        out_data["excluded_orders"] = data.get("excluded_orders", [])
        out_data["time_taken_to_solve"] = int(total_time)

        celery_logger.info(f"single trip output: {out_data}")

        # update response in postgres
        ct_query_engine.update_task(
            self.request.id,
            status="SUCCESS",
            status_msg="Optimization Completed",
            out_data=out_data,
        )

        self.update_state(state="SUCCESS", meta={"result": out_data})

    except:
        # update response in postgres
        ct_query_engine.update_task(
            self.request.id,
            status="FAILED",
            status_msg="Optimization Failed",
            # out_data=out_data,
        )
        celery_logger.info(f"Exception Handled on {self.request.id}")
        self.update_state(state="FAILED")

    return {"status": "Task completed!"}


@app.route("/routeoptimization/optimize/singletrip", methods=["POST"])
def single_trip_request_endpoint_v1():
    """
        End point for submiting single trip optimization task
        return celery task id as response
    """
    data = request.json

    # data validation
    validation_status, validation_msg = check_data_single_trip(request)
    if not validation_status:
        resp = standard_response(status="FAILED", message=validation_msg, data={})
        return jsonify(resp), 400

    # sending task to celery queue
    task = single_trip_optimize.apply_async(args=[data])
    resp = standard_response(
        status="SUCCESS", message="Submitted to job queue", data={"task_id": task.id}
    )

    # adding task information into postgres
    ct = CeleryTask_model(
        id=task.id,
        status="PENDING",
        status_msg="Submitted to job queue",
        task_type="single trip",
        input_data = data ,
    )
    ct_query_engine.insert(ct)

    return jsonify(resp), 200


@app.route("/routeoptimization/status/singletrip/<task_id>", methods=["GET"])
def task_status_single_trip(task_id):
    """
    returns status of single trip optimization celery task
    """

    if not celery_task_id_verify(task_id):
        resp = standard_response(status="FAILED", message="Invalid task id", data={})
        return jsonify(resp), 400

    # checking from postgres
    task = ct_query_engine.get_task(task_id)

    if task:
        resp = standard_response(
            status=task.status, message=task.status_msg, data=task.out_data,
        )
    else:
        resp = standard_response(
            status="PENDING", message="task id not in persistent db", data={},
        )

    return jsonify(resp), 200


# -------------------------------------------------------
# -------------------------------------------------------
# -------------------------------------------------------


def check_VRPSPDTW_data(req):
    """
        Input data format checker for VRPSPDTW
    """
    inputs = VRPSPDTW_data_schema(req)
    data = req.json

    if inputs.validate():
        last_n = len(data["orders"])
        # check if orders don't have locations
        data["new_orders"] = [
            order
            for order in data["orders"]
            if not (
                "none" in order["source"].lower()
                or "none" in order["destination"].lower()
            )
        ]
        # if some orders has no location, excluded those order
        # and remove those orders list
        if last_n != len(data["new_orders"]):
            data["excluded_orders"] = [
                order["order_id"]
                for order in data["orders"]
                if (
                    "none" in order["source"].lower()
                    or "none" in order["destination"].lower()
                )
            ]
            data["orders"] = data["new_orders"]

        # checking time window constraints
        time = data["warehouse_pickup_time"]
        if time["start_time"] > time["end_time"]:
            return (
                False,
                "Warehouse Pickup time Start time is greater than End time",
            )

        time = data["warehouse_drop_time"]
        if time["start_time"] > time["end_time"]:
            return (
                False,
                "Warehouse Drop time Start time is greater than End time",
            )

        for driver in data["drivers"]:
            if driver["duty_start_time"] > driver["duty_end_time"]:
                return (
                    False,
                    "Driver's Duty Start time is greater than duty end time",
                )

        for order in data["orders"]:
            if order["start_time"] > order["end_time"]:
                return (
                    False,
                    "Order's delivery window start time is greater than end time.",
                )

        return True, None
    else:
        return False, inputs.errors


def unroll_VRPSPDTW_data(data):
    """
        unrool VRPSPDTW data request format to match internal formats
        basically convert json object to arrays.
    """
    data["depot_location"] = data["warehouse_location"]
    data["total_orders"] = len(data["orders"])

    data["do_numbers"] = []
    data["locations_of_orders"] = []
    data["delivery_sizes"] = []
    data["type_of_orders"] = []
    data["delivery_windows"] = []
    data["customer_handover_time"] = []
    data ["order_storage"] = []

    # unrollnig orders information
    for order in data["orders"]:
        data["do_numbers"].append(order["order_id"])
        data["locations_of_orders"].append([order["source"], order["destination"]])
        data["delivery_sizes"].append(order["quantity"])
        data["type_of_orders"].append(1 if order["order_type"] == "pickup" else 0)
        data["delivery_windows"].append([order["start_time"], order["end_time"]])
        data["customer_handover_time"].append(order["handover_time"])
        
        try:
            data["order_storage"].append(order["storage"])
        except Exception as e:
            celery_logger.exception(e)
            celery_logger.debug("No Storage type provided")
    
    data["no_vehicles"] = len(data["drivers"])

    data["capacity_of_vehicles"] = []
    data["duty_time"] = []
    data["vehicle_storage"] = []


    # unrolling driver / vehicle information
    for driver in data["drivers"]:
        # recalculating capacity based on max util factor
        data["capacity_of_vehicles"].append(
            driver["capacity_of_vehicle"] * driver["max_utilized_capacity_of_vehicle"]
        )
        data["duty_time"].append([driver["duty_start_time"], driver["duty_end_time"]])
       
        try:
            data["vehicle_storage"].append(driver["storage"])
        except Exception as e:
            celery_logger.exception(e)
            celery_logger.debug("No storage type provided")

    # unroling warehouse timings
    warehouse_pickup_time = data["warehouse_pickup_time"]
    data["warehouse_pickup_time"] = (
        warehouse_pickup_time["start_time"],
        warehouse_pickup_time["end_time"],
    )

    warehouse_drop_time = data["warehouse_drop_time"]
    data["warehouse_drop_time"] = (
        warehouse_drop_time["start_time"],
        warehouse_drop_time["end_time"],
    )


@celery.task(bind=True)
def VRPSPDTW_request(self, data):
    """
        async function for mutiple driver with delivery time windows
    """
    engine.dispose()

    # updating status in postgres
    ct_query_engine.update_task(
        self.request.id, status_msg="Working on Optimization", input_data=data
    )

    unroll_VRPSPDTW_data(data)  # inplace dict updates
    celery_logger.info(f"multiple driver with time window input: {data}")

    try:
        # start solving optimization
        t1 = time.time()
        solver = VRPSPDTW_ortools(data)
        out_data = solver.solve()
        total_time = time.time() - t1

        # check for excluded orders
        out_data["excluded_orders"] = data.get("excluded_orders", []) + out_data.get(
            "dropped_orders_by_solver", []
        )
        out_data["time_taken_to_solve"] = int(total_time)

        celery_logger.info(f"multiple driver with time window output: {out_data}")

        # update response in postgres
        ct_query_engine.update_task(
            self.request.id,
            status="SUCCESS",
            status_msg="Optimization Completed",
            out_data=out_data,
        )

        self.update_state(state="SUCCESS", meta={"result": out_data})

    except Exception as e:
        # update response in postgres
        ct_query_engine.update_task(
            self.request.id,
            status="FAILED",
            status_msg="Optimization Failed",
            # out_data=out_data,
        )
        celery_logger.exception(e)
        celery_logger.info(f"Exception Handled on {self.request.id}")
        self.update_state(state="FAILED")

    return {"status": "Task completed!"}


@app.route("/routeoptimization/optimize/multipledriverwithtimewindow", methods=["POST"])
def VRPSPDTW_request_endpoint():
    """
        End point for submiting VRPSPDTW aka multiple driver with time window
        return celery task id as response
    """
    data = request.json

    # data validation
    validation_status, validation_msg = check_VRPSPDTW_data(request)
    if not validation_status:
        resp = standard_response(status="FAILED", message=validation_msg, data={})
        return jsonify(resp), 400

    # sending task to celery queue
    task = VRPSPDTW_request.apply_async(args=[data])
    resp = standard_response(
        status="SUCCESS", message="Submitted to job queue", data={"task_id": task.id}
    )

    # adding task informatino into postgres
    ct = CeleryTask_model(
        id=task.id,
        status="PENDING",
        status_msg="Submitted to job queue",
        task_type="multiple driver with time window",
        input_data = data,)
    ct_query_engine.insert(ct)

    return jsonify(resp), 200


@app.route(
    "/routeoptimization/status/multipledriverwithtimewindow/<task_id>", methods=["GET"]
)
def VRPSPDTW_task_status(task_id):
    """
    returns status of VRPSPDTW/ mutipledriver with time window celery task
    """

    if not celery_task_id_verify(task_id):
        resp = standard_response(status="FAILED", message="Invalid task id", data={})
        return jsonify(resp), 400

    task = ct_query_engine.get_task(task_id)

    if task:
        resp = standard_response(
            status=task.status, message=task.status_msg, data=task.out_data,
        )
    else:
        resp = standard_response(
            status="PENDING", message="task id not in persistent db", data={},
        )

    return jsonify(resp), 200


# --------------------------------------------
# --------------------------------------------
# --------------------------------------------


@app.route("/routeoptimization/health", methods=["GET"])
def debug_health():
    """
        debug endpoint, return last n requests information
        default n is 100.
    """
    last = request.args.get("last", default=100, type=int)
    tmp_session = db_Session()
    # quering all tasks from celery
    tasks = tmp_session.query(CeleryTask_model).all()
    tmp_session.close()

    data = dict()
    data["no_total_task"] = len(tasks)
    data["no_success_task"] = sum([1 for task in tasks if task.status == "SUCCESS"])
    data["no_pending_task"] = sum([1 for task in tasks if task.status == "PENDING"])
    task_data = []

    # sending last n tasks from postgres
    for task in tasks[-last:]:
        task_dict = dict()
        task_dict["task_id"] = task.id
        task_dict["status"] = task.status
        task_dict["status_msg"] = task.status_msg
        task_dict["input_data"] = task.input_data
        task_dict["out_data"] = task.out_data
        task_data.append(task_dict)

    data["task_data"] = task_data

    return jsonify(data), 200


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)

