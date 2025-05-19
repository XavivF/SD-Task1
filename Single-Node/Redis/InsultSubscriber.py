import redis

# Connect to Redis
client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

channel_broadcast = "Insults_broadcast"

def subscribe_to_insults():
        pubsub = client.pubsub()
        pubsub.subscribe(channel_broadcast)
        print(f"Subscribed to {channel_broadcast}")
        try:
            for message in pubsub.listen():
                if message['type'] == 'message':
                    insult = message['data']
                    print(f"Received insult: {insult}")
        except KeyboardInterrupt:
            print("\nStopping subscriber...")

subscribe_to_insults()