import redis
import random
import time
import multiprocessing

# Connect to Redis
client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

censoredTextsSet = "RESULTS"
insultSet = "INSULTS"
queue_name = "Work_queue"
queue_insults = "Insults_queue"

insults = ["beneit", "capsigrany", "ganàpia", "nyicris",
    "gamarús", "bocamoll", "murri","dropo","bleda","xitxarel·lo"]

llista_insults = [
            "Ets un beneit de cap a peus.",
            "No siguis capsigrany i pensa abans de parlar.",
            "Aquest ganàpia no sap el que fa.",
            "Sempre estàs tan nyicris que no pots ni aixecar una cadira.",
            "Quin gamarús ! ha tornat a fer el mateix error.",
            "No siguis bocamoll i guarda el secret.",
            "És un murri ... sempre s’escapa de tot.",
            "No siguis dropo i posa't a treballar.",
            "Ets una mica bleda i espavila una mica.",
            "Aquest xitxarel·lo es pensa que ho sap tot."
        ]

def send_insults():
    for insult in insults:
        client.rpush(queue_insults, insult)
        print(f"Produced: {insult}")

def send_text():
    while True:
        text = random.choice(llista_insults)
        client.rpush(queue_name, text)
        print(f"Produced: {text}")
        time.sleep(5)

if __name__ == "__main__":

    send_insults()
    pr_send_text = multiprocessing.Process(target=send_text)
    pr_send_text.start()

    try:
        print(
            "Press K to stop the services, press I to read the current insult list or press T to read the texts received")
        while True:
            t = input()
            if t == "I":
                print(f"Insult list:", client.smembers(insultSet))
            elif t == "T":
                print(f"Text list:", client.smembers(censoredTextsSet))
            elif t == "K":
                print("Stopping services...")
                pr_send_text.terminate()
                pr_send_text.join()
                break
            else:
                print("Unknown command.")
    except KeyboardInterrupt:
        print("Interrupted by user, stopping...")
        pr_send_text.terminate()
        pr_send_text.join()