from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import math
import random as rd

from location_util_osm import location_to_latlong, distance_matrix

# from location_util_google import distance_matrix

rd.seed(10)


def euclidean_dist(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def clamp(A, min_val, max_val):
    """
    clamp given value between min and max
    """
    return sorted([A, min_val, max_val])[1]


class Single_Trip:
    """

        BASE Code: VRPSPD_ortools_v1.py


        Vehicle Routing Problem with simultaneous pickup and delivery ( with capacity constraints)
        using OR tools

        tweaks to get full optimization over all constraints:
            dummy variables
            source location : + demand
            dest location : - demand

        Important Changelogs:
         * modified to work with single trip and additional calculation of cost saving
    """

    def __init__(self, data):
        """
            Important Note : make sure input validation is runned and data dict is in correct form.
            preprocess the data
        """
        self.AVG_SPEED = data.get("avg_speed", 50)  # in km/h
        self.DUTY_TIME = data.get("max_single_trip_duration", 12)  # in hr
        self.MAX_DISTANCE_PER_TRIP = int(self.AVG_SPEED * self.DUTY_TIME)  # in km
        self.AVG_HANDOVER_TIME = data.get("handover_time", 0)  # in minutes
        self.n_orders = len(data["delivery_sizes"]) // 2  # number of orders
        # converting time to distance
        self.AVG_HANDOVER_DISTANCE = (self.AVG_HANDOVER_TIME / 60) * self.AVG_SPEED
        self.user_max_time = data.get("max_solver_time", 3 * 60)  # in seconds
        # time allocated to solver
        self.SINGLE_TRIP_MAX_SOLVE_TIME = min(
            60 * 5, 2 * self.n_orders, self.user_max_time
        )  # in seconds
        self.data = self._preprocess(data)

    def _preprocess(self, raw_data):
        """
            Converting request dict to usable form of ortools

            Important things function is doing:
                1. Adding dummy nodes
                2. Adding positive and negative flows to maintain vehicle capacity
                3. creating distance matrix
        """
        data = {}
        data["locations"], data["pickups_deliveries"] = [raw_data["depot_location"]], []
        data["demands"] = [0]
        data["do_info"] = [("warehouse", "init")]
        cnt = 1
        for i, k, do in zip(
            raw_data["locations_of_orders"],
            raw_data["delivery_sizes"],
            raw_data["do_numbers"],
        ):
            data["locations"].append(i[0])
            data["locations"].append(i[1])
            data["pickups_deliveries"].append([cnt, cnt + 1])
            # action defined based on node
            data["do_info"].append((do, "collect"))
            data["do_info"].append((do, "drop"))
            # positive, negative demand
            data["demands"].append(k)
            data["demands"].append(-k)
            cnt += 2

        # calculating distance matrix
        data["distance_matrix"] = distance_matrix(data["locations"])
        data["num_vehicles"] = raw_data["no_vehicles"]
        data["vehicle_capacities"] = raw_data["capacity_of_vehicles"]
        data["depot"] = 0
        data["type_of_orders"] = raw_data["type_of_orders"]

        return data

    def generate_output(self, manager, routing, solution):
        """
            generate important output plannig answer from optimized response
        """
        total_distance = 0
        full_plan = []
        for vehicle_id in range(self.data["num_vehicles"]):
            index = routing.Start(vehicle_id)
            vehicle_plan = []
            route_distance = 0
            total_handover_excluded = 0
            while not routing.IsEnd(index):
                actual_id = manager.IndexToNode(index)

                order_id, operation = self.data["do_info"][actual_id]
                vehicle_plan.append({"operation": operation, "order_id": order_id})
                # calculating distance
                previous_index = index
                index = solution.Value(routing.NextVar(index))
                route_distance += routing.GetArcCostForVehicle(
                    previous_index, index, vehicle_id
                )
                # checking continous delivery location
                if (
                    index % 2 == 0
                    and index != 0
                    and not routing.IsEnd(index)
                    and self.data["distance_matrix"][previous_index][index] == 0
                ):
                    total_handover_excluded += 1

            full_plan.append(vehicle_plan[1:])
            # removing handover distance from total distance
            route_distance = route_distance - self.AVG_HANDOVER_DISTANCE * (
                len(vehicle_plan[1:]) // 2
            )
            # adding excluded handover distance back
            route_distance += total_handover_excluded * self.AVG_HANDOVER_DISTANCE

            total_distance += route_distance

        optimized_distance = total_distance

        # base distance calculations
        init_distance = 0
        last = 0  # starting from warehouse

        N = len(self.data["type_of_orders"])

        for i in range(N):
            if self.data["type_of_orders"][i]:  # pick-up
                curr = 2 * i + 1
            else:  # delivery
                curr = 2 * i + 2
            init_distance += int(self.data["distance_matrix"][last][curr])
            last = curr

        init_distance += int(self.data["distance_matrix"][last][0])
        return full_plan, optimized_distance, init_distance

    def solve(self):
        """
        solving optimization
        """
        manager = pywrapcp.RoutingIndexManager(
            len(self.data["distance_matrix"]),
            self.data["num_vehicles"],
            self.data["depot"],
        )

        # Create Routing Model.
        routing = pywrapcp.RoutingModel(manager)

        # Define cost of each arc.
        def distance_callback(from_index, to_index):
            """Returns the distance between the two nodes."""
            # Convert from routing variable Index to distance matrix NodeIndex.
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            # checking continous delivery location
            handover_time = (
                self.AVG_HANDOVER_DISTANCE
                if (
                    to_node % 2 == 0
                    and to_node != 0
                    and self.data["distance_matrix"][from_node][to_node] != 0
                )
                else 0
            )

            return self.data["distance_matrix"][from_node][to_node] + handover_time

        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        # Add Distance constraint.
        dimension_name = "Distance"
        routing.AddDimension(
            transit_callback_index,
            0,  # no slack
            self.MAX_DISTANCE_PER_TRIP,  # vehicle maximum travel distance
            True,  # start cumul to zero
            dimension_name,
        )

        distance_dimension = routing.GetDimensionOrDie(dimension_name)

        # Define Transportation Requests.
        for request in self.data["pickups_deliveries"]:
            pickup_index = manager.NodeToIndex(request[0])
            delivery_index = manager.NodeToIndex(request[1])
            routing.AddPickupAndDelivery(pickup_index, delivery_index)
            routing.solver().Add(
                routing.VehicleVar(pickup_index) == routing.VehicleVar(delivery_index)
            )
            routing.solver().Add(
                distance_dimension.CumulVar(pickup_index)
                <= distance_dimension.CumulVar(delivery_index)
            )

        def demand_callback(from_index):
            """Returns the demand of the node."""
            # Convert from routing variable Index to demands NodeIndex.
            from_node = manager.IndexToNode(from_index)
            return self.data["demands"][from_node]

        demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)

        routing.AddDimensionWithVehicleCapacity(
            demand_callback_index,
            0,  # null capacity slack
            self.data["vehicle_capacities"],  # vehicle maximum capacities
            True,  # start cumul to zero
            "Capacity",
        )

        # Setting first solution heuristic.
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
        )

        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )

        search_parameters.time_limit.seconds = self.SINGLE_TRIP_MAX_SOLVE_TIME

        solution = routing.SolveWithParameters(search_parameters)

        data = dict()

        # generating response
        if solution:
            full_plan, optimized_distance, init_distance = self.generate_output(
                manager, routing, solution
            )
            data["optimized_status"] = True
            data["trips"] = full_plan
            data["initial_distance"] = max(init_distance, 0)
            data["optimized_distance"] = max(optimized_distance, 0)
            data["initial_trip_duration"] = (
                init_distance / self.AVG_SPEED
            ) * 60  # in minutes
            data["optimized_trip_duration"] = (
                optimized_distance / self.AVG_SPEED
            ) * 60  # in minutes

            data["saved_distance"] = max(init_distance - optimized_distance, 0)  # in km
            data["saved_time"] = (
                data["saved_distance"] / self.AVG_SPEED
            ) * 60  # in minutes

            data["optimized_trip_duration"] = max(data["optimized_trip_duration"], 0)
            data["initial_trip_duration"] = max(data["initial_trip_duration"], 0)
            data["saved_time"] = max(data["saved_time"], 0)

            return data

        else:
            data["optimized_status"] = False
            return data


if __name__ == "__main__":

    depot_location_name = "23.025716,72.554297"
    depot_location = depot_location_name
    total_orders = 3
    type_of_orders = [0, 1, 0]  # 0 for delivery, 1 for pickup
    delivery_sizes = [0, 0, 0]
    do_numbers = ["1", "2", "3"]

    locations_of_orders = [
        ["23.025716,72.554297", "23.028614,72.506769"],
        ["22.977225,72.603538", "23.025716,72.554297"],
        ["23.025716,72.554297", "22.985649,72.484991"],
    ]

    no_vehicles = 1
    capcaity_of_vehicles = [100 for _ in range(no_vehicles)]

    data = dict()

    data["capacity_of_vehicles"] = capcaity_of_vehicles
    data["depot_location"] = depot_location
    data["total_orders"] = total_orders
    data["do_numbers"] = do_numbers
    data["no_vehicles"] = no_vehicles
    data["delivery_sizes"] = delivery_sizes
    data["type_of_orders"] = type_of_orders
    data["locations_of_orders"] = locations_of_orders

    solver = Single_Trip(data)
    data = solver.solve()
    if data["optimized_status"]:
        for idx, i in enumerate(data["trips"]):
            print(f"vehicle: {idx} path:{i}")
            # print(data["optimized_distance"], data["init_distance"])
            print(data["saved_distance"], data["saved_time"])

