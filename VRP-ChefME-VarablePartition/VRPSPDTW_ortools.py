from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import math
import random as rd
from utils import possible_orderings
import pprint
from location_util_osm import location_to_latlong, distance_matrix
import numpy as np
import logging

logger = logging.getLogger(__name__)
# from location_util_google import distance_matrix

rd.seed(10)
pp = pprint.PrettyPrinter(indent=4)


def euclidean_dist(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


class VRPSPDTW_ortools:
    """
        Vehicle Routing Problem with simultaneous pickup and delivery ( with capacity constraints)
        and delivery time window
        
        tweaks to get full optimization over all constraints:
            dummy variables
            source location : + demand
            dest location : - demand

        Important Changelogs:
            1. added time windows for vehicle
            2. delivery window for each orders
            3. duty window for each driver
            4. different handovertime for each orders
    """

    def __init__(self, data):
        """
            Important Note : make sure input validation is runned and data dict is in correct form.
        """
        self.AVG_SPEED = data.get("avg_speed", 50)  # in km/h

        self.ROUNDTRIP = data.get("round",1) # 0 if not round trip, 1 if it is; default value 1
        
        self.REPEAT_HANDOVER = data.get("repeat_handover",0) #0 to exclude same location times, 1 to add for same locations as well
        
        self.DUTY_TIME = data.get("max_single_trip_duration", 8)  # in hr

        self.AVG_PICKUP_TIME = data.get("pickup_time", 0)  # in minutes
        # converting time to distance
        self.AVG_PICKUP_DISTANCE = (self.AVG_PICKUP_TIME / 60) * self.AVG_SPEED

        self.n_orders = len(data["delivery_sizes"]) // 2
        self.user_max_time = data.get("max_solver_time", 20 * 60)  # in seconds: Change: Default solver time from  min to min
        self.MAX_SOLVE_TIME = min( 
            20 * 60, self.n_orders * 3, self.user_max_time
        )  # in seconds : Change: Default solve time from  5 min to  20 min
        self.data = self._preprocess(data)

    def _preprocess(self, raw_data):
        """
            Converting request dict to usable form of ortools

            Important things function is doing:
                1. Adding dummy nodes
                2. Adding positive and negative flows to maintain vehicle capacity
                3. creating distance matrix
        """

        def change_time_to_dist(time):
            """
                converting time to distance scale
            """
            return tuple(map(lambda x: int((x / 60) * self.AVG_SPEED), time))

        data = {}
        data["locations"], data["pickups_deliveries"] = [raw_data["depot_location"]], []
        data["demands"] = [0]
        data["do_info"] = [("warehouse", "")]
        # adding warehouse window to 24*7
        # this parameter is ignore and doesn't effect solver
        data["time_windows"] = [(0, 24 * self.AVG_SPEED)]
        data["type_of_orders"] = raw_data["type_of_orders"]
        # converting timings to distance
        data["duty_time"] = list(map(change_time_to_dist, raw_data["duty_time"]))
        data["warehouse_pickup_time"] = change_time_to_dist(
            raw_data["warehouse_pickup_time"]
        )
        data["warehouse_drop_time"] = change_time_to_dist(
            raw_data["warehouse_drop_time"]
        )
        data["extra_distance"] = [0]
        
        if not self.REPEAT_HANDOVER:
            self.warehouse_locations_set = set([0])

        


        
        cnt = 1
        for i, k, do, order_type, time_window, handover_time in zip(
            raw_data["locations_of_orders"],
            raw_data["delivery_sizes"],
            raw_data["do_numbers"],
            raw_data["type_of_orders"],
            raw_data["delivery_windows"],
            raw_data["customer_handover_time"],
        ):
            data["locations"].append(i[0])
            data["locations"].append(i[1])
            data["pickups_deliveries"].append([cnt, cnt + 1])
            data["do_info"].append((do, "pickup"))
            data["do_info"].append((do, "deliver"))
            # positive and negative demand
            data["demands"].append(k)
            data["demands"].append(-k)

            # creatingtime constraints for locations from inputs
            # extra)distance represent either pickup time or handover time
            # depending on which node we are on
            if order_type:  # pickup
                data["time_windows"].append(change_time_to_dist(time_window))
                
                if not self.REPEAT_HANDOVER:
                    self.warehouse_locations_set.add(cnt + 1)
                    
                data["time_windows"].append(data["warehouse_drop_time"])
                data["extra_distance"].append(
                    int((handover_time / 60) * self.AVG_SPEED)
                )
                data["extra_distance"].append(self.AVG_PICKUP_DISTANCE)
            else:  # deliver
                
                if not self.REPEAT_HANDOVER:
                    self.warehouse_locations_set.add(cnt)
                    
                data["time_windows"].append(data["warehouse_pickup_time"])
                data["time_windows"].append(change_time_to_dist(time_window))
                data["extra_distance"].append(self.AVG_PICKUP_DISTANCE)
                data["extra_distance"].append(
                    int((handover_time / 60) * self.AVG_SPEED)
                )

            cnt += 2




        # calculating distance matix
        data["distance_matrix"] = distance_matrix(data["locations"])

        #if not a round-trip -> tweaking the distance matrix accordingly
        if not self.ROUNDTRIP:
            for row in data["distance_matrix"]:
                row[0] = 0
        data["num_vehicles"] = raw_data["no_vehicles"]
        data["vehicle_capacities"] = raw_data["capacity_of_vehicles"]
        data["depot"] = 0

        try:
            data["order_storage"] = raw_data["order_storage"]
            data["vehicle_storage"] = raw_data["vehicle_storage"]
        
        except Exception as e:
            logger.exception(e)
            logger.debug("Storage type not provided")

        return data

    def generate_output(self, manager, routing, solution):
        """
            generate output plannig dict from optimized response
        """
        
        #Only include those vehicles in consideration for certain orders which
        #have the required storage type
        #If storage type is not 
        try:
            for k in range(len(self.data["order_storage"])):
                temp_drivers = [-1]
                for i in range(len(self.data["vehicle_storage"])):
                    if self.data["order_storage"][k] in self.data["vehicle_storage"][i]:
                        temp_drivers.append(i)
                index = manager.NodeToIndex(k)
                routing.VehicleVar(index).SetValues(temp_drivers)

        except Exception as e:
            logger.exception(e)
            logger.debug("Storage type not provided")


        full_plan = []
        distance_covered_by_vehicles = []
        max_capacity_used_by_vehicles = []
        total_working_hour_of_vehicles = []
        final_working_time = []

        distance_dimension = routing.GetDimensionOrDie("Distance")

        for vehicle_id in range(self.data["num_vehicles"]):
            index = routing.Start(vehicle_id)
            vehicle_plan = []
            route_distance = 0
            cap = 0
            max_cap = 0
            total_handover_excluded = 0
            distance_spend_on_pickup = 0
            distance_spend_on_handover = 0
            while not routing.IsEnd(index):
                actual_id = manager.IndexToNode(index)

                distance_var = distance_dimension.CumulVar(index)

                order_id, operation = self.data["do_info"][actual_id]
                # appending trip information
                # estimated time is to complete including operation
                vehicle_plan.append(
                    {
                        "operation": operation,
                        "order_id": order_id,
                        "estimated_time": (solution.Max(distance_var) / self.AVG_SPEED)
                        * 60,
                    }
                )

                previous_index = index
                index = solution.Value(routing.NextVar(index))

                # removing handover time where we have contiouns delivery to same location
                handover_excluded_flag = False
                pickup_exlucded_flag = False
                
                if not self.REPEAT_HANDOVER:
                    if (
                        index % 2 == 0
                        and index != 0
                        and not routing.IsEnd(index)
                        and self.data["distance_matrix"][previous_index][index] == 0
                    ):
                        total_handover_excluded += 1
                        handover_excluded_flag = True

                    if (
                        index % 2 == 1
                        and index not in self.warehouse_locations_set
                        and not routing.IsEnd(index)
                        and self.data["distance_matrix"][previous_index][index] == 0
                    ):
                        pickup_exlucded_flag = True
                        # total_handover_excluded += 1
                else:
                    if (
                        index % 2 == 0
                        and index != 0
                        and not routing.IsEnd(index)
                        #and self.data["distance_matrix"][previous_index][index] == 0
                    ):
                        total_handover_excluded += 1
                        handover_excluded_flag = True

                    if (
                        index % 2 == 1
                        #and index not in self.warehouse_locations_set
                        and not routing.IsEnd(index)
                        #and self.data["distance_matrix"][previous_index][index] == 0
                    ):
                        # total_handover_excluded += 1
                        pickup_exlucded_flag = True
                
                route_distance += routing.GetArcCostForVehicle(
                    previous_index, index, vehicle_id
                )
                # removing handover distance from travel distance
                remove_handover_distance = (
                    self.data["extra_distance"][index]
                    if not routing.IsEnd(index)
                    and index % 2 == 0
                    and not handover_excluded_flag
                    else 0
                )
                # removing pickup distance from travel distance
                remove_pickup_distance = (
                    self.data["extra_distance"][index]
                    if not routing.IsEnd(index) and index % 2 == 1
                    and not pickup_exlucded_flag
                    else 0
                )

                route_distance = route_distance - (
                    remove_pickup_distance + remove_handover_distance
                )
                # calculating total handover and pickup distance for further calculating
                distance_spend_on_handover += remove_handover_distance
                distance_spend_on_pickup += remove_pickup_distance
                # calculating current vehicle capacity
                cap += self.data["demands"][actual_id]
                max_cap = max(cap, max_cap)

            distance_var = distance_dimension.CumulVar(index)
            final_working_time.append(
                (solution.Max(distance_var) / self.AVG_SPEED) * 60
            )

            full_plan.append(vehicle_plan[1:])
            # covertnig distance to time
            time_spend_on_distance = (route_distance / self.AVG_SPEED) * 60
            time_spend_on_handover = (distance_spend_on_handover * 60) / self.AVG_SPEED
            time_spend_on_pickup = (distance_spend_on_pickup * 60) / self.AVG_SPEED
            # combining all working times
            total_working_hour_of_vehicles.append(
                (
                    time_spend_on_distance,
                    math.ceil(time_spend_on_handover),
                    math.ceil(time_spend_on_pickup),
                )
            )

            distance_covered_by_vehicles.append(route_distance)
            max_capacity_used_by_vehicles.append(max_cap)

        return (
            full_plan,
            distance_covered_by_vehicles,
            max_capacity_used_by_vehicles,
            total_working_hour_of_vehicles,
            final_working_time,
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
            
            if not self.REPEAT_HANDOVER:
                # if to_node location is customers where we have to handover time
                handover_time = (
                    self.data["extra_distance"][to_node]
                    if (
                        to_node % 2 == 0
                        and to_node != 0
                        and self.data["distance_matrix"][from_node][to_node] != 0
                    )
                    else 0
                )
                # if to_node location has pickup operation
                pickup_time = (
                    self.data["extra_distance"][to_node] if to_node % 2 == 1 else 0
                )
                # removing pickup distance from same locations including warehouse
                delta_pickup_time = (
                    self.data["extra_distance"][to_node] 
                    if (to_node % 2 == 1 #and to_node not in self.warehouse_locations_set #if want to add every pickup time at warehouse, uncomment
                        and self.data["distance_matrix"][from_node][to_node] == 0 ) 
                    else 0
                )
                
            else:
                handover_time = (
                    self.data["extra_distance"][to_node]
                    if (
                        to_node % 2 == 0
                        and to_node != 0
                        #and self.data["distance_matrix"][from_node][to_node] != 0
                    )
                    else 0
                )
                # if to_node location has pickup operation
                pickup_time = (
                    self.data["extra_distance"][to_node] if to_node % 2 == 1 else 0
                )
                
                # delta was to remove the extra pickup time from same location, which will be zero here in case we require each additional handover to be added.
                #In case you need to add additional handover on top of the one provided, to add dynamically
                #Assign a negative value to delta_pickup_time or any function which outputs negative value
                delta_pickup_time = 0
                
                
            # returning total distance
            return (
                self.data["distance_matrix"][from_node][to_node]
                + handover_time
                + pickup_time
                - delta_pickup_time
            )

        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        # Add Distance constraint.
        dimension_name = "Distance"
        routing.AddDimension(
            transit_callback_index,
            24 * self.AVG_SPEED,  # waiting time
            24 * self.AVG_SPEED,  # vehicle maximum travel distance
            False,  # start cumul to zero
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

        # adding timing constraints
        # --------------------------------------------
        # adding locations timing constraints
        for location_idx, time_window in enumerate(self.data["time_windows"]):
            if location_idx == 0:
                continue
            index = manager.NodeToIndex(location_idx)
            distance_dimension.CumulVar(index).SetRange(time_window[0], time_window[1])

        # adding driver's duty timing constraints
        for vehicle_id, time_window in zip(
            range(self.data["num_vehicles"]), self.data["duty_time"]
        ):
            index = routing.Start(vehicle_id)
            distance_dimension.CumulVar(index).SetRange(*time_window)
            index = routing.End(vehicle_id)
            distance_dimension.CumulVar(index).SetRange(*time_window)

        # adding condition to complete trip in less time
        for i in range(self.data["num_vehicles"]):
            routing.AddVariableMinimizedByFinalizer(
                distance_dimension.CumulVar(routing.Start(i))
            )
            routing.AddVariableMinimizedByFinalizer(
                distance_dimension.CumulVar(routing.End(i))
            )

        # --------------------------------------------------------------------
        # penatly
        penalty = int(
            (
                # self.AVG_SPEED
                max([max(row) for row in self.data["distance_matrix"]])
                + self.AVG_PICKUP_DISTANCE
                + max(self.data["extra_distance"])
            )
        )

        for node in range(1, len(self.data["distance_matrix"])):
            routing.AddDisjunction([manager.NodeToIndex(node)], penalty)

        # ---------------------------------------------------------------------

        # Setting first solution heuristic.
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
        )

        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )

        search_parameters.time_limit.seconds = self.MAX_SOLVE_TIME
        # Solve the problem.
        solution = routing.SolveWithParameters(search_parameters)

        if solution:
            (
                full_plan,
                distance_covered_by_vehicles,
                max_capacity_used_by_vehicles,
                total_working_hour_of_vehicles,
                final_working_time,
            ) = self.generate_output(manager, routing, solution)

            # creating output response dict
            data = dict()

            total_optimized_distance = sum(distance_covered_by_vehicles)
            data["optimized_distance"] = total_optimized_distance
            data["optimized_status"] = True
            data["no_driver_utilized"] = sum([1 for plan in full_plan if len(plan) > 0])

            # data["trips"] = full_plan
            # data["total_working_hour_of_vehicles"] = []

            # for dist_time, drop_time, pickup_time in total_working_hour_of_vehicles:
            #     temp_dict = dict()
            #     temp_dict["time_spend_on_driving"] = dist_time
            #     temp_dict["time_spend_on_pickup"] = pickup_time
            #     temp_dict["time_spend_on_drop"] = drop_time
            #     data["total_working_hour_of_vehicles"].append(temp_dict)

            # data["driver_trip_completed_time"] = final_working_time
            # data["optimized_trip_duration"] = max(final_working_time)

            # data["max_capacity_used_by_vehicles"] = max_capacity_used_by_vehicles
            # avg_load = list(filter(lambda x: x > 0, max_capacity_used_by_vehicles))

            # data["distance_covered_by_vehicles"] = distance_covered_by_vehicles

            # generating nested dict for output response
            # check API documentation
            data["driver_trips"] = []
            for (
                trip,
                working_hours,
                distance_covered,
                max_cap,
                duty_complete_time,
            ) in zip(
                full_plan,
                total_working_hour_of_vehicles,
                distance_covered_by_vehicles,
                max_capacity_used_by_vehicles,
                final_working_time,
            ):
                temp_dict = dict()
                temp_dict["trip_detail"] = trip

                temp_vehicle_dict = dict()
                temp_vehicle_dict["max_capacity_used"] = max_cap
                temp_vehicle_dict["distance_covered"] = distance_covered
                temp_dict["vehicle"] = temp_vehicle_dict

                temp_driver_dict = dict()
                temp_driver_dict["duty_completed_time"] = duty_complete_time
                temp_driver_dict["time_spend_on_driving"] = working_hours[0]
                temp_driver_dict["time_spend_on_drop"] = working_hours[1]
                temp_driver_dict["time_spend_on_pickup"] = working_hours[2]
                temp_dict["driver"] = temp_driver_dict

                data["driver_trips"].append(temp_dict)

            (
                data["all_possible_orderings"],
                data["tried_orderings"],
            ) = possible_orderings(len(self.data["demands"][1:]) // 2)

            # clamping values
            def clamp(A, min_val, max_val):
                return sorted([A, min_val, max_val])[1]

            data["optimized_distance"] = max(data["optimized_distance"], 0)

            # calculating dropped orders
            total_orders = set([do_id for do_id, operations in self.data["do_info"]])
            completed_orders = set(
                [orders["order_id"] for trip in full_plan for orders in trip]
            )

            # if solver dropped any order due to penalty
            data["dropped_orders_by_solver"] = list(
                total_orders - completed_orders - set(["warehouse"])
            )

            return data
        else:
            data = dict()
            data["optimized_status"] = False
            return data


if __name__ == "__main__":

    depot_location_name = "23.025716,72.554297"
    depot_location = depot_location_name
    total_orders = 3
    type_of_orders = [0, 0, 0]  # 0 for delivery, 1 for pickup
    delivery_sizes = [2, 2, 2]
    do_numbers = ["1", "2", "3"]

    locations_of_orders = [
        ["23.025716,72.554297", "23.028614,72.506769"],
        ["22.977225,72.603538", "23.025716,72.554297"],
        ["23.025716,72.554297", "22.985649,72.484991"],
    ]

    no_vehicles = 3
    capacity_of_vehicles = [100 for _ in range(no_vehicles)]
    delivery_window = [(7 * 60, 8 * 60), (10 * 60, 17 * 60), (7 * 60, 12 * 60)]

    data = dict()

    data["avg_speed"] = 50  # in km/h
    data["pickup_time"] = 10  # in minutes
    data["delivery_windows"] = delivery_window
    data["warehouse_pickup_time"] = (5 * 60, 10 * 60)
    data["warehouse_drop_time"] = (5 * 60, 17 * 60)
    data["duty_time"] = [(6 * 60, 9 * 60), (8 * 60, 12 * 60)]
    data["customer_handover_time"] = [10, 20, 30]
    data["order_storage"] = ["F","C","D"]
    data["vehicle_storage"] = ["F","FCD","FCD"]

    data["capacity_of_vehicles"] = capacity_of_vehicles
    data["depot_location"] = depot_location
    data["total_orders"] = total_orders
    data["do_numbers"] = do_numbers
    data["no_vehicles"] = no_vehicles
    data["delivery_sizes"] = delivery_sizes
    data["type_of_orders"] = type_of_orders
    data["locations_of_orders"] = locations_of_orders

    # print(data["duty_time"])

    solver = VRPSPDTW_ortools(data)
    data = solver.solve()
    if data["optimized_status"]:
        # for idx, i in enumerate(data["trips"]):
        #     pp.pprint(i)

        pp.pprint(data)

