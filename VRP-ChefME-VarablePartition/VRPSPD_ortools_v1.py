from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import math
import random as rd
from utils import possible_orderings

from location_util_osm import location_to_latlong, distance_matrix

# from location_util_google import distance_matrix

rd.seed(10)


def euclidean_dist(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


# clamping values
def clamp(A, min_val, max_val):
    return sorted([A, min_val, max_val])[1]


class VRPSPD_ortools:
    """
        Vehicle Routing Problem with simultaneous pickup and delivery ( with capacity constraints)
        using OR tools

        tweaks to get full optimization over all constraints:
            dummy variables
            source location : + demand
            dest location : - demand

        Important Changelogs:
            1. handover time is added into distance matrix
            2. duty time is considered
    """

    def __init__(self, data):
        """
            Important Note : make sure input validation is runned and data dict is in correct form.
        """
        self.AVG_SPEED = data.get("avg_speed", 50)  # in km/h
        self.DUTY_TIME = data.get("max_single_trip_duration", 8)  # in hr
        self.MAX_DISTANCE_PER_TRIP = int(self.AVG_SPEED * self.DUTY_TIME)  # in km
        self.AVG_HANDOVER_TIME = data.get("handover_time", 15)  # in minutes
        # converting time to distanece
        self.AVG_HANDOVER_DISTANCE = (self.AVG_HANDOVER_TIME / 60) * self.AVG_SPEED
        self.n_orders = len(data["delivery_sizes"]) // 2
        self.user_max_time = data.get("max_solver_time", 20 * 60)  # in seconds: Change: Changed default 5 min to 20 min
        # solver time
        self.V1_MAX_SOLVE_TIME = min(
            20 * 60, self.n_orders * 3, self.user_max_time      
        )  # in seconds: Change: Changed default 5 min to 20 min
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
        data["do_info"] = [("warehouse", "")]
        cnt = 1
        for i, k, do in zip(
            raw_data["locations_of_orders"],
            raw_data["delivery_sizes"],
            raw_data["do_numbers"],
        ):
            data["locations"].append(i[0])
            data["locations"].append(i[1])
            data["pickups_deliveries"].append([cnt, cnt + 1])
            # action defined base on node
            data["do_info"].append((do, "pickup"))
            data["do_info"].append((do, "deliver"))
            # positive negative demand
            data["demands"].append(k)
            data["demands"].append(-k)
            cnt += 2

        # calculating distance matrix
        data["distance_matrix"] = distance_matrix(data["locations"])
        # print (data['distance_matrix'])
        data["num_vehicles"] = raw_data["no_vehicles"]
        data["vehicle_capacities"] = raw_data["capacity_of_vehicles"]
        data["depot"] = 0

        return data

    def generate_output(self, manager, routing, solution):
        """
            generate important output plannig answer from optimized response
        """

        full_plan = []
        distance_covered_by_vehicles = []
        max_capacity_used_by_vehicles = []
        total_working_hour_of_vehicles = []

        for vehicle_id in range(self.data["num_vehicles"]):
            index = routing.Start(vehicle_id)
            vehicle_plan = []
            route_distance = 0
            cap = 0
            max_cap = 0
            total_handover_excluded = 0
            while not routing.IsEnd(index):
                actual_id = manager.IndexToNode(index)

                order_id, operation = self.data["do_info"][actual_id]
                vehicle_plan.append({"operation": operation, "order_id": order_id})

                previous_index = index
                index = solution.Value(routing.NextVar(index))

                # checking continous delivery location
                if (
                    index % 2 == 0
                    and index != 0
                    and not routing.IsEnd(index)
                    and self.data["distance_matrix"][previous_index][index] == 0
                ):
                    total_handover_excluded += 1

                # calculating distance
                route_distance += routing.GetArcCostForVehicle(
                    previous_index, index, vehicle_id
                )
                # calculating current capacity of vehicle
                cap += self.data["demands"][actual_id]
                max_cap = max(cap, max_cap)

            full_plan.append(vehicle_plan[1:])

            # calculting route distance for each vehicle
            # by subtracting all orders handover time plus consecutive order
            # which is going to save time
            total_orders_done_by_vehicle = len(vehicle_plan[1:]) // 2
            route_distance = route_distance - self.AVG_HANDOVER_DISTANCE * (
                total_orders_done_by_vehicle
            )
            route_distance += total_handover_excluded * self.AVG_HANDOVER_DISTANCE
            # converting distance to time
            time_spend_on_distance = (route_distance / self.AVG_SPEED) * 60
            time_spend_on_handover = self.AVG_HANDOVER_TIME * (
                total_orders_done_by_vehicle - total_handover_excluded
            )
            # combining timings information
            total_working_hour_of_vehicles.append(
                (time_spend_on_distance, time_spend_on_handover)
            )
            distance_covered_by_vehicles.append(route_distance)
            max_capacity_used_by_vehicles.append(max_cap)

        return (
            full_plan,
            distance_covered_by_vehicles,
            max_capacity_used_by_vehicles,
            total_working_hour_of_vehicles,
        )

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

        search_parameters.time_limit.seconds = self.V1_MAX_SOLVE_TIME
        # Solve the problem.
        solution = routing.SolveWithParameters(search_parameters)

        if solution:
            (
                full_plan,
                distance_covered_by_vehicles,
                max_capacity_used_by_vehicles,
                total_working_hour_of_vehicles,
            ) = self.generate_output(manager, routing, solution)

            data = dict()
            # generating output response dict
            total_optimized_distance = sum(distance_covered_by_vehicles)
            data["optimized_distance"] = total_optimized_distance
            data["optimized_status"] = True
            data["trips"] = full_plan
            # calculating driver utilized
            data["no_driver_utilized"] = sum([1 for plan in full_plan if len(plan) > 0])

            data["total_working_hour_of_vehicles"] = total_working_hour_of_vehicles
            # calculating total trip duration from distace travelled time and handover time
            data["optimized_trip_duration"] = max(
                [x + y for x, y in total_working_hour_of_vehicles]
            )  # in minutes

            data["max_capacity_used_by_vehicles"] = max_capacity_used_by_vehicles
            # calculating avg load of vehicles by filter only used vehivles
            avg_load = list(filter(lambda x: x > 0, max_capacity_used_by_vehicles))
            data["avg_load_of_vehicles"] = sum(avg_load) / len(avg_load)
            data["distance_covered_by_vehicles"] = distance_covered_by_vehicles

            (
                data["all_possible_orderings"],
                data["tried_orderings"],
            ) = possible_orderings(len(self.data["demands"][1:]) // 2)

            data["optimized_trip_duration"] = clamp(
                data["optimized_trip_duration"], 0, self.DUTY_TIME * 60
            )
            data["optimized_distance"] = max(data["optimized_distance"], 0)

            return data
        else:
            data = dict()
            data["optimized_status"] = False
            return data


if __name__ == "__main__":

    print("VRPSPD Optimization")

    # solver = VRPSPD_ortools(depot_location, total_orders, do_numbers, type_of_orders, locations_of_orders, delivery_sizes, no_vehicles, capcaity_of_vehicles)
    # status, full_plan = solver.solve()
    # if status:
    #     for idx, i in enumerate(full_plan):
    #         print (f"vehicle: {idx} path:{i}")
