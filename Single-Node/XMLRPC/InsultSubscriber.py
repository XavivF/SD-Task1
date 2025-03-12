from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.server import SimpleXMLRPCRequestHandler
import sys

class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ("/RPC2",)

class Subscriber:
    def __init__(self):
        self.received_insults = []

    def notify(self, insult):
        self.received_insults.append(insult)
        print(f"New insult received: {insult}")
        return "Insult received."

server = SimpleXMLRPCServer(('localhost', int(sys.argv[1])), requestHandler=RequestHandler, allow_none=True)
subscriber_service = Subscriber()

server.register_function(subscriber_service.notify, "notify")

print(f"Subscriber running on port {sys.argv[1]}...")
server.serve_forever()
