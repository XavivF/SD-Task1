import random
import xmlrpc.client
from time import sleep
import threading

insults_text = [
    "ets tonto i estas boig",
    "ets molt inútil",
    "ets una mica desastre",
    "ets massa fracassat",
    "ets un poc covard",
    "ets molt molt mentider",
    "ets super estúpid",
    "ets bastant idiota"
]
serviceHostURL= "http://localhost:8000"
subscriberURL= "http://localhost:8001/RPC2"

def add_insults(s):
    insults = ["tonto", "lleig", "boig", "idiota", "estúpid", "inútil", "desastre", "fracassat", "covard", "mentider"]
    for insult in insults:
        print(s.add_insult(insult))


def send_text():
    s = xmlrpc.client.ServerProxy(serviceHostURL)
    while True:
        try:
            i = random.randint(0, len(insults_text) - 1)
            print(f"Sent text {insults_text[i]}, has been filtered and now says: {s.filter(insults_text[i])}")
            sleep(2)
        except Exception as e:
            print(f"Error in send_text: {e}")


def broadcast():
    s = xmlrpc.client.ServerProxy(serviceHostURL)
    while True:
        try:
            insult = s.insult_me()
            s.notify_subscribers(insult)
            print("Sent petition to insult subscribers.")
            sleep(5)
        except Exception as e:
            print(f"Error in broadcast: {e}")


hostServer = xmlrpc.client.ServerProxy(serviceHostURL)
hostServer.add_subscriber(subscriberURL)
add_insults(hostServer)

thread1 = threading.Thread(target=broadcast)
thread2 = threading.Thread(target=send_text)

thread1.start()
thread2.start()
