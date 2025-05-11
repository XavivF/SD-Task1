from xmlrpc.server import SimpleXMLRPCRequestHandler
from xmlrpc.server import SimpleXMLRPCServer
import argparse

class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ("/RPC2",)

class Subscriber:
    def __init__(self):
        self.received_insults = []

    def notify(self, insult):
        self.received_insults.append(insult)
        print(f"New insult received: {insult}")
        return "Insult received."


parser = argparse.ArgumentParser(description="XML-RPC InsultSubscriber")
parser.add_argument("-sb_port", "--subscriber-port", type=int, required=True, help="Port to bind the subscriber to")

args = parser.parse_args()

server = SimpleXMLRPCServer(('localhost', args.subscriber_port), requestHandler=RequestHandler, allow_none=True)
subscriber_service = Subscriber()

server.register_function(subscriber_service.notify, "notify")

print(f"Subscriber running on port {args.subscriber_port}...")
try:
    server.serve_forever()
except KeyboardInterrupt:
    print("\nShutting down InsultSubscriber...")