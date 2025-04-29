import time

import redis
import random
import time
# Connect to Redis
client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

queue_name = "Work_queue"
channel_insults = "Insults_channel"

insults = ["beneit", "capsigrany", "ganàpia", "nyicris",
    "gamarús", "bocamoll", "murri","dropo","bleda","xitxarel·lo"]

def send_insults():
    for insult in insults:
        client.publish(channel_insults, insult)
        print(f"Produced: {insult}")


def send_text():
    insult = random.choice(insults)
    text = f"This is a text with an insult: {insult}"
    client.rpush(queue_name, text)
    print(f"Produced: {text}")

send_insults()
while True:
    send_text()
    time.sleep(5)