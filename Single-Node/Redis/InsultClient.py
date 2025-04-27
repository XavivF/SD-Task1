import time

import redis
import random
import time
# Connect to Redis
client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

queue_name = "Work_queue"
channel_insults = "Insults_channel"

texts = ["Ets un gamarús , no veus que ho estàs fent tot al revés?",
        "Deixa de fer el dropo i posa't a treballar d'una vegada.",
        "Quin bocamoll , no pots guardar cap secret!",
        "No siguis tan beneit , que t'estan prenent el pèl.",
        "Amb aquest capsigrany no anirem gaire lluny.",
        "Vinga, nyicris , que qualsevol ventet t'arrossega!"]

insults = ["beneit", "capsigrany", "ganàpia", "nyicris",
    "gamarús", "bocamoll", "murri","dropo","bleda","xitxarel·lo"]

def enviar_insults():
    for insult in insults:
        client.publish(channel_insults, insult)
        print(f"Produced: {insult}")


def send_text():
    text = random.choice(texts)
    client.rpush(queue_name, text)
    print(f"Produced: {text}")

enviar_insults()
while True:
    send_text()
    time.sleep(5)