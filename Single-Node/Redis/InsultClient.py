import redis
import time

# Connect to Redis
client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

channel_name = "Insults_channel"

# Send multiple messages
insults = ["Cap de melo", "Olaaa caracola", "Adeuu", "1234", "Beneit",
           "Capsigrany", "Ganàpia", "Nyicris", "Gamarús",
           "Tros de quòniam", "Poca-solta",
           "Bocamoll", "Tocat del bolet"]

def enviar_insults(client, channel_name, insults):
    for insult in insults:
        client.publish(channel_name, insult)
        print(f"Produced: {insult}")

def subscribe_to_insults(self):
        pubsub = client.pubsub()
        pubsub.subscribe(self.channel_name)
        print(f"Subscribed to {self.channel_name}")
        for message in pubsub.listen():
            if message['type'] == 'message':
                insult = message['data']
                print(f"Received insult: {insult}")
                print(self.add_insult(insult))

enviar_insults(client, channel_name, insults)
subscribe_to_insults(self)