from pymilvus import MilvusClient
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")
client = MilvusClient("shop_demo.db")

docs = [
    {"id": 1, "text": "How to teach a young dog to sit", "topic": "pets"},
    {"id": 2, "text": "Puppy leash training for beginners", "topic": "pets"},
    {"id": 3, "text": "Understanding dog behavior and barking", "topic": "pets"},
    {"id": 4, "text": "Feeding a kitten: what and when", "topic": "pets"},
    {"id": 5, "text": "How to care for a newborn puppy", "topic": "pets"},
    {"id": 6, "text": "Training your dog to stay and come", "topic": "pets"},
    {"id": 7, "text": "Tips for keeping a pet cat healthy", "topic": "pets"},
    {"id": 8, "text": "Best exercises for a healthy back", "topic": "health"},
    {"id": 9, "text": "How to reduce stress with daily habits", "topic": "health"},
    {"id": 10, "text": "Healthy diet and balanced nutrition", "topic": "health"},
    {"id": 11, "text": "Simple stretching routines for beginners", "topic": "health"},
    {"id": 12, "text": "Why sleep is important for your health", "topic": "health"},
    {"id": 13, "text": "How to improve cardiovascular fitness", "topic": "health"},
    {"id": 14, "text": "Preventing back pain while working", "topic": "health"},
    {"id": 15, "text": "Stock market basics for beginners", "topic": "finance"},
    {"id": 16, "text": "How to invest in index funds", "topic": "finance"},
    {"id": 17, "text": "Understanding interest rates and inflation", "topic": "finance"},
    {"id": 18, "text": "How bonds and stocks are different", "topic": "finance"},
    {"id": 19, "text": "Personal budgeting and saving money", "topic": "finance"},
    {"id": 20, "text": "Risk management for long term investors", "topic": "finance"},
]

vectors = model.encode(
    [d["text"] for d in docs],
    normalize_embeddings=True
)

data = [
    {**d, "vector": v.tolist()}
    for d, v in zip(docs, vectors)
]

for name, metric in [("docs_cosine", "COSINE"), ("docs_l2", "L2")]:
    if client.has_collection(name):
        client.drop_collection(name)

    client.create_collection(
        collection_name=name,
        dimension=384,
        metric_type=metric
    )

    client.insert(collection_name=name, data=data)

print("EXERCISE 1")

queries = {
    "pets": "puppy training tips",
    "health": "exercises to reduce back pain",
    "finance": "beginner guide to investing in stocks"
}

for topic, text in queries.items():
    query = model.encode([text], normalize_embeddings=True).tolist()

    hits = client.search(
        collection_name="docs_cosine",
        data=query,
        limit=3,
        output_fields=["text", "topic"]
    )

    print("\nTopic:", topic)
    print("Nearest results:")

    for hit in hits[0]:
        print(
            round(hit["distance"], 3),
            hit["entity"]["topic"],
            hit["entity"]["text"]
        )

    filtered_hits = client.search(
        collection_name="docs_cosine",
        data=query,
        limit=3,
        filter=f'topic == "{topic}"',
        output_fields=["text", "topic"]
    )

    print("Filtered results:")

    for hit in filtered_hits[0]:
        print(hit["entity"]["topic"], hit["entity"]["text"])


print("\nEXERCISE 2")

query = model.encode(
    ["puppy training tips"],
    normalize_embeddings=True
).tolist()

cosine_hits = client.search(
    collection_name="docs_cosine",
    data=query,
    limit=5,
    output_fields=["text"]
)

l2_hits = client.search(
    collection_name="docs_l2",
    data=query,
    limit=5,
    output_fields=["text"]
)

cosine_ids = [hit["id"] for hit in cosine_hits[0]]
l2_ids = [hit["id"] for hit in l2_hits[0]]

print("Cosine ranking:", cosine_ids)
print("L2 ranking:", l2_ids)
print("Same ranking:", cosine_ids == l2_ids)


print("\nEXERCISE 3")

question = "How can I teach my puppy to sit?"

query = model.encode(
    [question],
    normalize_embeddings=True
).tolist()

hits = client.search(
    collection_name="docs_cosine",
    data=query,
    limit=3,
    filter='topic == "pets"',
    output_fields=["text"]
)

chunks = [hit["entity"]["text"] for hit in hits[0]]

prompt = (
    "Use the following context to answer the question:\n\n"
    + "\n".join(chunks)
    + "\n\nQuestion: "
    + question
    + "\nAnswer:"
)

print(prompt)

client.close()
