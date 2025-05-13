import random
import xmlrpc.client
from time import sleep
import multiprocessing
import sys
import argparse

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

def add_insults(lb_proxy):
    insults = ["tonto", "lleig", "boig", "idiota", "estúpid", "inútil", "desastre", "fracassat", "covard", "mentider"]
    for insult in insults:
        try:
            print(f"Adding insult '{insult}' via LoadBalancer...")
            lb_proxy.add_insult(insult)
        except Exception as e:
            print(f"Error adding insult via LoadBalancer: {e}", file=sys.stderr)


def send_text():
    s = xmlrpc.client.ServerProxy(load_balancer_url, allow_none=True)
    while True:
        try:
            i = random.randint(0, len(insults_text) - 1)
            text_to_send = insults_text[i]
            filtered_text = s.filter(text_to_send)
            print(f"Sending text '{text_to_send}' to filter... the result is: {filtered_text}")
            sleep(2)
        except Exception as e:
            print(f"Error in send_text: {e}", file=sys.stderr)
            sleep(5)

def broadcast():
    s = xmlrpc.client.ServerProxy(load_balancer_url, allow_none=True)
    while True:
        try:
            insult = s.insult_me()
            s.notify_subscribers(insult)
            sleep(5)
        except Exception as e:
            print(f"Error en broadcast: {e}", file=sys.stderr)
            sleep(5)


parser = argparse.ArgumentParser(description="XML-RPC InsultClient")
parser.add_argument("-lb_port", "--loadbalancer-port", type=int, required=True, help="Port to bind the load balancer to")
parser.add_argument("-sb_port", "--subscriber_port", type=int, required=True, help="Port to bind the subscriber to")

args = parser.parse_args()

load_balancer_url = f"http://localhost:{args.loadbalancer_port}/RPC2"
subscriberURL = f"http://localhost:{args.subscriber_port}/RPC2"

# Create LoadBalancer proxy
load_balancer_proxy = xmlrpc.client.ServerProxy(load_balancer_url, allow_none=True)

try:
    print("provaawdadwas")
    print(load_balancer_proxy.add_subscriber(subscriberURL))
    print("provaawdadwas despres")
except Exception as e:
    print(f"Error on registering subscriber with LoadBalancer: {e}", file=sys.stderr)
    sys.exit(1)

add_insults(load_balancer_proxy)

process_broadcast = multiprocessing.Process(target=broadcast)
process_send_text = multiprocessing.Process(target=send_text)

process_broadcast.start()
process_send_text.start()

try:
    print(
        "Press K to stop the services, press I to read the current insult list or press T to read the texts received")
    while True:
        t = input()
        if t == "I":
            try:
                print("Insult list:", load_balancer_proxy.get_insults())
            except Exception as e:
                print(f"Communication error: {e}.")
        elif t == "T":
            try:
                print("Censored texts:", load_balancer_proxy.get_results())
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
