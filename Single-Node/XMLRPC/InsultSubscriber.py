from xmlrpc.server import SimpleXMLRPCRequestHandler
from xmlrpc.server import SimpleXMLRPCServer


class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ("/RPC2",)

class Subscriber:
    def __init__(self):
        self.received_insults = []

    def notify(self, insult):
        self.received_insults.append(insult)
        print(f"New insult received: {insult}")
        return "Insult received."

server = SimpleXMLRPCServer(('localhost', 8001), requestHandler=RequestHandler, allow_none=True)
subscriber_service = Subscriber()

server.register_function(subscriber_service.notify, "notify")

print(f"Subscriber running on port 8001...")
server.serve_forever()
