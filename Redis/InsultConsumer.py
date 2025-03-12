import redis

# Connect to Redis
client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

queue_name = "task_queue"

# Delete the list
client.delete("INSULTS")

print("Consumer is waiting for insults...")

while True:
    insult = client.blpop(queue_name, timeout=0)  # Blocks indefinitely until a task is available
    if insult:
        print(f"Insult rebut: {insult[1]}")
    if insult[1] not in client.lrange("INSULTS", 0, -1):
        client.lpush("INSULTS", insult[1])
        InsultsList = client.lrange("INSULTS", 0, -1)
        print(f"Insult list: {InsultsList}")

