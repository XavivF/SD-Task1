from random import Random
from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.server import SimpleXMLRPCRequestHandler
import random

# Restrict to a particular path.
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)

# Create server
with SimpleXMLRPCServer(('10.112.204.7', 8000),
                        requestHandler=RequestHandler) as server:
    server.register_introspection_functions()

    class Insults:
        def __init__(self):
            self.insults = []

        def add_insult(self, insult):
            self.insults.append(insult)
            return f"Insult added: {insult}"

        def get_insults(self):
            return self.insults

        def insult_me(self):
            if len(self.insults) == 0:
                return "No insults available"
            i = random.randint(0, len(self.insults)-1)
            return self.insults[i]

    insults = Insults()
    server.register_instance(insults)

    # Run the server's main loop
    print("Server is running...")
    server.serve_forever()