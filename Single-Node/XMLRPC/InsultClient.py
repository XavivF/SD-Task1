import random
import xmlrpc.client
from time import sleep
import threading

insults_text = [
    "ets tonto i estas boig",
    "ets un inútil",
    "ets un desastre",
    "ets un fracassat",
    "ets un covard",
    "ets un mentider",
    "ets un estúpid",
    "ets un idiota"
]
serviceHostURL= "http://localhost:8000"
subscriberURL= "http://localhost:8001/RPC2"

def afegir_insults(s):
    insults = ["tonto", "lleig", "boig", "idiota", "estúpid", "inútil", "desastre", "fracassat", "covard", "mentider"]
    for insult in insults:
        print(s.add_insult(insult))


def enviar_text():
    s = xmlrpc.client.ServerProxy(serviceHostURL)
    while True:
        try:
            i = random.randint(0, len(insults_text) - 1)
            print(f"Enviat text {insults_text[i]}, s'ha filtrat i ara posa: {s.filter(insults_text[i])}")
            sleep(2)
        except Exception as e:
            print(f"Error in enviar_text: {e}")


def broadcast():
    s = xmlrpc.client.ServerProxy(serviceHostURL)
    while True:
        try:
            insult = s.insult_me()
            s.notify_subscribers(insult)
            print("Enviant petició d'insultar a subscriptors")
            sleep(5)
        except Exception as e:
            print(f"Error in broadcast: {e}")


hostServer = xmlrpc.client.ServerProxy(serviceHostURL)
hostServer.add_subscriber(subscriberURL)
afegir_insults(hostServer)

thread1 = threading.Thread(target=broadcast)
thread2 = threading.Thread(target=enviar_text)

thread1.start()
thread2.start()
