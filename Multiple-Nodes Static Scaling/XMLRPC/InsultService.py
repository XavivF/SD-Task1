import random
import xmlrpc.client
from xmlrpc.server import SimpleXMLRPCRequestHandler
from xmlrpc.server import SimpleXMLRPCServer
import argparse
import sys

import redis


# Restrict to a particular path.
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)

# Add argument parsing
parser = argparse.ArgumentParser(description="Insult Service XML-RPC Server")
parser.add_argument("-p", "--port", type=int, default=8000,
                    help="Port number to listen on (default: 8000)")
args = parser.parse_args()

port = args.port

class Insults:
    def __init__(self):
        self.insults = []   # received insults
        self.subscribers = [] # Subscribers for this specific instance
        self.counter_key = "COUNTER"
        self.client = redis.Redis(db=0, decode_responses=True)

    def add_subscriber(self, url):
        if url not in self.subscribers:
            self.subscribers.append(url)
            print(f"Subscriber {url} added to instance on port {port}.")
            return f"Subscriber {url} added to instance on port {port}."
        print(f"Subscriber {url} already exists on instance on port {port}.")
        return f"Subscriber {url} already exists on instance on port {port}."

    def notify_subscribers(self, insult):
        print(f"Instance on port {port} notifying {len(self.subscribers)} subscribers.")
        for subscriber_url in self.subscribers:
            try:
                proxy = xmlrpc.client.ServerProxy(subscriber_url)
                proxy.notify(insult)
                print(f"Subscriber {subscriber_url} notified by instance on port {port}. Insult: {insult}")
            except Exception as exception:
                print(f"Error notifying {subscriber_url} from instance on port {port}: {exception}", file=sys.stderr)
        return f"Subscribers of instance on port {port} notified."

    def add_insult(self, insult):
        self.insults.append(insult)
        self.client.incr(self.counter_key)
        # print(f"Instance on port {port} added insult: {insult}. Count: {self.counter.value}")
        return f"Insult added by instance on port {port}: {insult}"

    def get_insults(self):
        return self.insults

    def insult_me(self):
        if len(self.insults) == 0:
            print(f"Instance on port {port}: No insults available.")
            return "No insults available"
        i = random.randint(0, len(self.insults)-1)
        chosen_insult = self.insults[i]
        print(f"Instance on port {port} chose insult: {chosen_insult}.")
        return chosen_insult

# Create server
try:
    with SimpleXMLRPCServer(('localhost', port),
                            requestHandler=RequestHandler) as server:
        server.register_introspection_functions()

        insults_instance = Insults()
        server.register_instance(insults_instance)

        # Run the server's main loop
        print(f"Insult Service Server is running on port {port}...")
        server.serve_forever()
except KeyboardInterrupt:
    print("\nShutting down InsultService...")
    sys.exit(0)
except PermissionError:
    print(f"Error: Could not bind to port {port}. Permission denied. Try a port above 1024.", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"An error occurred: {e}", file=sys.stderr)
    sys.exit(1)