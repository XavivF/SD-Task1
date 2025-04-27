import redis
import time

# Connect to Redis
client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)


channel_broadcast = "Insults_broadcast"
# Send multiple messages


def subscribe_to_insults():
        pubsub = client.pubsub()
        pubsub.subscribe(channel_broadcast)
        print(f"Subscribed to {channel_broadcast}")
        for message in pubsub.listen():
            if message['type'] == 'message':
                insult = message['data']
                print(f"Received insult: {insult}")


subscribe_to_insults()