from multiprocessing import Value
from xmlrpc.server import SimpleXMLRPCRequestHandler
from xmlrpc.server import SimpleXMLRPCServer
import argparse
import sys

# Global counter for processed requests
processed_requests_counter = Value('i', 0)

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
    def __init__(self, req_counter):
        self.insults = []   # received insults
        self.results = []   # censored text results
        self.counter = req_counter

    def filter(self, text):
        with self.counter.get_lock():
            self.counter.value += 1
        censored_text = ""
        for word in text.split():
            if word in self.insults:
                censored_text += "CENSORED "
            else:
                censored_text += word + " "
        if censored_text not in self.results:
            self.results.append(censored_text)
        print(f"Filtered text: {censored_text}")
        return censored_text

    def add_insult(self, insult):
        with self.counter.get_lock():
            self.counter.value += 1
        self.insults.append(insult)
        return f"Insult added: {insult}"

    def get_results(self):
        return self.results

    def get_processed_count(self):
        with self.counter.get_lock():
            count =  self.counter.value
        print(f"Instance on port {port} returning processed count: {count}")
        return count

# Create server
try:
    with SimpleXMLRPCServer(('localhost', port),
                        requestHandler=RequestHandler) as server:
        server.register_introspection_functions()

        insult_filter = InsultFilter(processed_requests_counter)
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