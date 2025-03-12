import redis

# Connect to Redis
client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

channel_name = "Insults_channel"

# Subscribe to channel
pubsub = client.pubsub()
pubsub.subscribe(channel_name)

print(f"Subscribed to {channel_name}, waiting for insults...")

# Continuously listen for messages
for message in pubsub.listen():
    if message["type"] == "message":
        print(f"Received: {message['data']}")

