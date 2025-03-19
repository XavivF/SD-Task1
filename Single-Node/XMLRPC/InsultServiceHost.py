from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.server import SimpleXMLRPCRequestHandler
import xmlrpc.client
import random

# Restrict to a particular path.
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)

# Create server
with SimpleXMLRPCServer(('localhost', 8000),
                        requestHandler=RequestHandler) as server:
    server.register_introspection_functions()

    class Insults:
        def __init__(self):
            self.insults = []
            self.results = []
            self.subscribers = []

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
            self.insults.append(insult)
            return f"Insult added: {insult}"

        def get_insults(self):
            return self.insults

        def insult_me(self):
            if len(self.insults) == 0:
                return "No insults available"
            i = random.randint(0, len(self.insults)-1)
            print(f"Insult escollit: {self.insults[i]}")
            return self.insults[i]

        def filter(self, text):
            censored_text = ""
            for word in text.split():
                if word in self.insults:
                    censored_text += "CENSORED "
                else:
                    censored_text += word + " "
            self.results.append(censored_text)
            print(f"Filtered text: {censored_text}")
            return censored_text

        def get_results(self):
            return self.results

    insults = Insults()
    server.register_instance(insults)

    # Run the server's main loop
    print("Server is running...")
    server.serve_forever()