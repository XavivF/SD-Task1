import redis
import time
import random

# Connect to Redis
client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

channel_name = "Insults_channel"

# Publish multiple insults


while 1:
    length = client.llen("INSULTS")
    insult = client.lindex("INSULTS", random.randint(0, length - 1))
    client.publish(channel_name, insult)
    print(f"Broadcasted: {insult}")
    time.sleep(2)  # Simulating delay between messages
