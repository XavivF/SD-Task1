import random
import xmlrpc.client
from time import sleep
import multiprocessing

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

serviceURL = "http://localhost:8000"
subscriberURL = "http://localhost:8001/RPC2"
filterURL = "http://localhost:8010/RPC2"

def add_insults(s):
    insults = ["tonto", "lleig", "boig", "idiota", "estúpid", "inútil", "desastre", "fracassat", "covard", "mentider"]
    for insult in insults:
        print(s.add_insult(insult))


def send_text():
    s = xmlrpc.client.ServerProxy(filterURL)
    while True:
        try:
            i = random.randint(0, len(insults_text) - 1)
            print(f"Sent text {insults_text[i]}, has been filtered and now says: {s.filter(insults_text[i])}")
            sleep(2)
        except Exception as e:
            print(f"Error in send_text: {e}")


def broadcast():
    s = xmlrpc.client.ServerProxy(serviceURL)
    while True:
        try:
            insult = s.insult_me()
            s.notify_subscribers(insult)
            print("Sent petition to insult subscribers.")
            sleep(5)
        except Exception as e:
            print(f"Error in broadcast: {e}")


hostService = xmlrpc.client.ServerProxy(serviceURL)
hostFilter = xmlrpc.client.ServerProxy(filterURL)
hostService.add_subscriber(subscriberURL)
add_insults(hostService)
add_insults(hostFilter)

process_broadcast = multiprocessing.Process(target=broadcast)
process_send_text = multiprocessing.Process(target=send_text)

process_broadcast.start()
process_send_text.start()

while True:
    try:
        print(
            "Press K to stop the services, press I to read the current insult list or press T to read the texts received")
        while True:
            t = input()
            if t == "I":
                try:
                    print("Insult list:", hostService.get_insults())
                except Exception as e:
                    print(f"Communication error: {e}.")
            elif t == "T":
                try:
                    print("Censored texts:", hostFilter.get_results())
                except Exception as e:
                    print(f"Communication error: {e}.")
            elif t == "K":
                print("Stopping services...")
                process_broadcast.terminate()
                process_send_text.terminate()
                process_broadcast.join()
                process_send_text.join()
                break
            else:
                print("Unknown command.")
    except KeyboardInterrupt:
        print("Interrupted by user, stopping...")
        process_broadcast.terminate()
        process_send_text.terminate()
        process_broadcast.join()
        process_send_text.join()
