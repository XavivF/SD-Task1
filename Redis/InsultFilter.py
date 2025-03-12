import redis

# Connect to Redis
client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

queue_name = "Work_queue"

# Delete the list

print("Consumer is waiting for insults...")

while True:
    insult = client.blpop(queue_name, timeout=0)  # Blocks indefinitely until a task is available
    if insult:
        
    # Censorar insults i guardar a la llista RESULTS
        text_Censorat = ""
        if insult[1] in client.lrange("INSULTS", 0, -1):
            text_Censorat = "CENSORED"
        else:
            text_Censorat = insult[1]
        client.lpush("RESULTAT", text_Censorat)
        print(f"Missatge rebut: {insult[1]}" + "\tText censorat: " + text_Censorat)
