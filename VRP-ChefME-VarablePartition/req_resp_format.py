"""
Request Payload (Single Trip) :

{
    "warehouse_location": "23.025716,72.554297",
    "orders" : [
        {
            "order_id" : "A1",
            "source" : "23.025716,72.554297",
            "destination" : "23.028614,72.506769",
            "quantity" : 24, 
            "order_type" : "delivery"
        },
        {
            "order_id" : "A2",
            "source" : "23.025716,72.554297",
            "destination" : "23.028614,72.506769",
            "quantity" : 12, 
            "order_type" : "delivery"
        },
        {
            "order_id" : "A3",
            "source" : "23.025716,72.554297",
            "destination" : "23.028614,72.506769",
            "quantity" : 34, 
            "order_type" : "pickup"
        },

    ],
    "no_vehicles": 1,
    "capacity_of_vehicles" : [100],
    "max_utilized_capacity_of_vehicles": [1.0]
}


Response (Single Trip)

{
    "status" : "success/failure/pending",
    "message" : "",
    "data" : {
        "initial_distance" : 43,
        "optimized_distance": 35,
        "initial_trip_duration" : 360,
        "optimized_trip_duration" : 340,
        "trips" : [
            {"operation" : "pickup", "order_id" : "A1"},
            {"operation" : "pickup", "order_id" : "A2"},
            {"operation" : "deliver", "order_id" : "A2"},
            {"operation" : "deliver", "order_id" : "A2"},
            {"operation" : "pickup", "order_id" : "A3"},
        ]
    }
}


Request Payload (Single Trip) :

{
    "warehouse_location": "23.025716,72.554297",
    "orders" : [
        {
            "order_id" : "A1",
            "source" : "23.025716,72.554297",
            "destination" : "23.028614,72.506769",
            "quantity" : 24, 
            "order_type" : "delivery"
        },
        {
            "order_id" : "A2",
            "source" : "23.025716,72.554297",
            "destination" : "23.028614,72.506769",
            "quantity" : 12, 
            "order_type" : "delivery"
        },
        {
            "order_id" : "A3",
            "source" : "23.025716,72.554297",
            "destination" : "23.028614,72.506769",
            "quantity" : 34, 
            "order_type" : "pickup"
        },

    ],
    "no_vehicles": 5,
    "capacity_of_vehicles" : [100, 80, 90, 95, 120],
    "max_utilized_capacity_of_vehicles": [1.0]
}



Response (Multiple Trip)

{
    "status" : "success/failure/pending",
    "message" : "",
    "data" : {
        "trips" : [
            [
                {"operation" : "pickup", "order_id" : "A1"},
                {"operation" : "pickup", "order_id" : "A2"},
                {"operation" : "deliver", "order_id" : "A2"},
                {"operation" : "deliver", "order_id" : "A2"},
                {"operation" : "pickup", "order_id" : "A3"},
            ],
            [
                {"operation" : "pickup", "order_id" : "A4"},
                {"operation" : "pickup", "order_id" : "A5"},
                {"operation" : "pickup", "order_id" : "A6"},
                {"operation" : "deliver", "order_id" : "A4"},
                {"operation" : "pickup", "order_id" : "A7"},
                {"operation" : "deliver", "order_id" : "A5"},
                {"operation" : "deliver", "order_id" : "A6"},
            ],
        ]
    }
}

"""