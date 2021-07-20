from flask_inputs.validators import JsonSchema
from flask_inputs import Inputs

# json scheme for VRPSPD
VRPSPD_data_format = {
    "type": "object",
    "required": [
        # "avg_speed",
        # "max_single_trip_duration",
        "warehouse_location",
        "orders",
        "no_vehicles",
        "capacity_of_vehicles",
        "max_utilized_capacity_of_vehicles",
    ],
    "properties": {
        "avg_speed": {"type": "number"},
        "max_solver_time": {"type": "number"},
        "max_single_trip_duration": {"type": "number"},
        "handover_time": {"type": "number"},
        "warehouse_location": {"type": "string"},
        "orders": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "order_id",
                    "source",
                    "destination",
                    "quantity",
                    "order_type",
                ],
                "properties": {
                    "order_id": {"type": "string"},
                    "source": {"type": "string"},
                    "destination": {"type": "string"},
                    "quantity": {"type": "number"},
                    "order_type": {"type": "string"},
                },
            },
        },
        "no_vehicles": {"type": "number"},
        "capacity_of_vehicles": {"type": "array", "items": {"type": "number"}},
        "max_utilized_capacity_of_vehicles": {
            "type": "array",
            "items": {"type": "number"},
        },
    },
}


class VRPSPD_data_schema(Inputs):
    """
        creat JsonSchema verifier
    """

    json = [JsonSchema(schema=VRPSPD_data_format)]


# json scheme for VRPSPDTW
VRPSPDTW_data_format = {
    "type": "object",
    "required": [
        "avg_speed",
        "pickup_time",
        "warehouse_location",
        "warehouse_pickup_time",
        "warehouse_drop_time",
        "orders",
        "drivers",
    ],
    "properties": {
        "avg_speed": {"type": "number"},
        "max_solver_time": {"type": "number"},
        # "handover_time": {"type": "number"},
        "pickup_time": {"type": "number"},
        "warehouse_location": {"type": "string"},
        "warehouse_pickup_time": {
            "type": "object",
            "required": ["start_time", "end_time"],
            "properties": {
                "start_time": {"type": "number"},
                "end_time": {"type": "number"},
            },
        },
        "warehouse_drop_time": {
            "type": "object",
            "required": ["start_time", "end_time"],
            "properties": {
                "start_time": {"type": "number"},
                "end_time": {"type": "number"},
            },
        },
        "orders": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "order_id",
                    "source",
                    "destination",
                    "quantity",
                    "order_type",
                    "start_time",
                    "end_time",
                    "handover_time",
                ],
                "properties": {
                    "order_id": {"type": "string"},
                    "source": {"type": "string"},
                    "destination": {"type": "string"},
                    "quantity": {"type": "number"},
                    "order_type": {"type": "string"},
                    "start_time": {"type": "number"},
                    "end_time": {"type": "number"},
                    "handover_time": {"type": "number"},
                },
            },
        },
        "drivers": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "duty_start_time",
                    "duty_end_time",
                    "capacity_of_vehicle",
                    "max_utilized_capacity_of_vehicle",
                ],
                "properties": {
                    "duty_start_time": {"type": "number"},
                    "duty_end_time": {"type": "number"},
                    "capacity_of_vehicle": {"type": "number"},
                    "max_utilized_capacity_of_vehicle": {"type": "number"},
                },
            },
        },
    },
}


class VRPSPDTW_data_schema(Inputs):
    """
        creat JsonSchema verifier
    """

    json = [JsonSchema(schema=VRPSPDTW_data_format)]
