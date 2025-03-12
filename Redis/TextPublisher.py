import redis
import time
import random
# Connect to Redis
client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

queue_name = "Work_queue"

# Send multiple messages
texts = ["Informació actualitzada disponible",
    "Dades correctament processades",
    "Accés restringit temporalment",
    "Operació completada amb èxit",
    "S'ha enviat la sol·licitud",
    "Carregant contingut, espera",
    "Cap resultat trobat"]

while 1:
    text = texts[random.randint(0, len(texts) - 1)]
    client.rpush(queue_name, text)
    print(f"Produced: {text}")
    time.sleep(5)  # Simulating a delay in task production (5s)
