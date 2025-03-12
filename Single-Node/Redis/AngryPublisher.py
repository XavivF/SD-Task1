import redis
import time
import random
# Connect to Redis
client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

queue_name = "Work_queue"

# Send multiple messages
insults = ["Cap de melo", "Olaaa caracola", "Adeuu", "1234", "Beneit",
        "Capsigrany", "Ganàpia", "Nyicris", "Gamarús",
        "Tros de quòniam", "Poca-solta",
        "Bocamoll", "Tocat del bolet"]

for insult in insults:
        client.lpush("INSULTS", insult)

while 1:
    insult = insults[random.randint(0, len(insults) - 1)]
    client.rpush(queue_name, insult)
    
    print(f"Produced: {insult}")
    time.sleep(3)  # Simulating a delay in task production (5s)
