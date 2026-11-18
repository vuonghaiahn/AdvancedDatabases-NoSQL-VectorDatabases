from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
client.admin.command("ping")

db = client["shop"]
orders = db["orders"]

orders.drop()
orders.insert_many([
    {
        "_id": 1001,
        "customer": {"name": "Linh", "city": "Hanoi"},
        "status": "paid",
        "items": [
            {"sku": "BK-01", "title": "Python Basics", "qty": 2, "price": 12.5},
            {"sku": "BK-07", "title": "SQL in Practice", "qty": 1, "price": 18.0}
        ],
        "tags": ["student"]
    },
    {
        "_id": 1002,
        "customer": {"name": "Nam", "city": "Da Nang"},
        "status": "shipped",
        "items": [{"sku": "BK-03", "title": "Data Viz", "qty": 1, "price": 22.0}],
        "shipping": {"method": "express"}
    },
    {
        "_id": 1003,
        "customer": {"name": "Mai", "city": "Hanoi"},
        "status": "paid",
        "items": [{"sku": "BK-01", "title": "Python Basics", "qty": 1, "price": 12.5}],
        "coupon": "WELCOME10"
    },
    {
        "_id": 1004,
        "customer": {"name": "Hung", "city": "Hue"},
        "status": "pending",
        "items": [{"sku": "BK-04", "title": "Statistics", "qty": 2, "price": 15.0}],
        "note": "Pay on delivery"
    },
    {
        "_id": 1005,
        "customer": {"name": "An", "city": "Hanoi"},
        "status": "paid",
        "items": [{"sku": "BK-05", "title": "Machine Learning", "qty": 3, "price": 20.0}],
        "gift_wrap": True
    }
])

print("EXERCISE 1")
print("Total orders:", orders.count_documents({}))
for order in orders.find({"items.sku": "BK-01"}):
    print(order["_id"], order["customer"]["name"])

print("\nEXERCISE 2")
pipeline = [
    {"$match": {"status": {"$in": ["paid", "shipped"]}}},
    {"$unwind": "$items"},
    {"$group": {
        "_id": "$customer.city",
        "revenue": {"$sum": {"$multiply": ["$items.qty", "$items.price"]}}
    }},
    {"$sort": {"revenue": -1}}
]
for result in orders.aggregate(pipeline):
    print(result["_id"], result["revenue"])

print("\nEXERCISE 3")
test_orders = db["orders_10000"]
test_orders.drop()

documents = []
for i in range(1, 10001):
    city = "Hanoi" if i % 100 == 0 else ["Da Nang", "Hue", "HCMC"][i % 3]
    documents.append({
        "_id": i,
        "customer": {"name": f"Customer {i}", "city": city},
        "status": "paid" if i % 3 == 0 else "shipped",
        "items": [{"sku": "BK-01", "qty": 1, "price": 12.5}]
    })
test_orders.insert_many(documents)

query = {"customer.city": "Hanoi", "status": "paid"}
before = test_orders.find(query).explain()
test_orders.create_index([("customer.city", 1), ("status", 1)])
after = test_orders.find(query).explain()

for label, result in [("Before index", before), ("After index", after)]:
    plan = str(result["queryPlanner"]["winningPlan"])
    stage = "IXSCAN" if "IXSCAN" in plan else "COLLSCAN" if "COLLSCAN" in plan else plan
    stats = result["executionStats"]
    print(label)
    print("Stage:", stage)
    print("Documents examined:", stats["totalDocsExamined"])
    print("Documents returned:", stats["nReturned"])
    print("Execution time (ms):", stats["executionTimeMillis"])

client.close()
