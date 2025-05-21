from xmlrpc.server import SimpleXMLRPCRequestHandler
from xmlrpc.server import SimpleXMLRPCServer
import argparse
import sys

import redis


# Restrict to a particular path.
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)

# Add argument parsing
parser = argparse.ArgumentParser(description="Insult Filter XML-RPC Server")
parser.add_argument("-p", "--port", type=int, default=8000,
                    help="Port number to listen on (default: 8000)")
args = parser.parse_args()

port = args.port

class InsultFilter:
    def __init__(self):
        self.insults = ["tonto", "lleig", "boig", "idiota", "estúpid", "inútil", "desastre", "fracassat", "covard", "mentider"]
        self.results = []   # censored text results
        self.counter_key = "COUNTER"
        self.client = redis.Redis(db=0, decode_responses=True)

    def filter(self, text):
        censored_text = ""
        for word in text.split():
            if word in self.insults:
                censored_text += "CENSORED "
            else:
                censored_text += word + " "
        if censored_text not in self.results:
            self.results.append(censored_text)
        self.client.incr(self.counter_key)
        return censored_text

    def add_insult(self, insult):
        self.insults.append(insult)
        return f"Insult added: {insult}"

    def get_results(self):
        return self.results

# Create server
try:
    with SimpleXMLRPCServer(('localhost', port),
                        requestHandler=RequestHandler) as server:
        server.register_introspection_functions()

        insult_filter = InsultFilter()
        server.register_instance(insult_filter)

        # Run the server's main loop
        print(f"Insult Filter Server is running on port {port}...")
        server.serve_forever()
except KeyboardInterrupt:
    print("\nShutting down InsultFilter...")
    sys.exit(0)
except PermissionError:
    print(f"Error: Could not bind to port {port}. Permission denied. Try a port above 1024.", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"An error occurred: {e}", file=sys.stderr)
    sys.exit(1)