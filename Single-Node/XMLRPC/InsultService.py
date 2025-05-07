import random
import xmlrpc.client
from multiprocessing import Value
from xmlrpc.server import SimpleXMLRPCRequestHandler
from xmlrpc.server import SimpleXMLRPCServer

# Global counter for processed requests
processed_requests_counter = Value('i', 0)

# Restrict to a particular path.
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)

# Create server
with SimpleXMLRPCServer(('localhost', 8000),
                        requestHandler=RequestHandler) as server:
    server.register_introspection_functions()

    class Insults:
        def __init__(self, req_counter):
            self.insults = []   # received insults
            self.results = []   # censored text
            self.subscribers = []
            self.counter = req_counter

        def add_subscriber(self, url):
            if url not in self.subscribers:
                self.subscribers.append(url)
                return f"Subscriber {url} added."
            return f"Subscriber {url} already exists."

        def notify_subscribers(self, insult):
            for subscriber_url in self.subscribers:
                try:
                    proxy = xmlrpc.client.ServerProxy(subscriber_url)
                    proxy.notify(insult)
                    print(f"Subscriber {subscriber_url} notified. Insult: {insult}")
                    print("Notified subscriber.")
                except Exception as e:
                    print(f"Error notifying {subscriber_url}: {e}")
            return "Subscribers notified."

        def add_insult(self, insult):
            with self.counter.get_lock():
                self.counter.value += 1
            self.insults.append(insult)
            return f"Insult added: {insult}"

        def get_insults(self):
            return self.insults

        def insult_me(self):
            if len(self.insults) == 0:
                return "No insults available"
            i = random.randint(0, len(self.insults)-1)
            print(f"Chosen insult: {self.insults[i]}")
            return self.insults[i]

        def get_processed_count(self):
            with self.counter.get_lock():
                return self.counter.value

    insults = Insults(processed_requests_counter)
    server.register_instance(insults)
    # Run the server's main loop
    print("Server is running...")
    server.serve_forever()