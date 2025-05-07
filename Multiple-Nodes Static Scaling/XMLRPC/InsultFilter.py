from multiprocessing import Value
from xmlrpc.server import SimpleXMLRPCRequestHandler
from xmlrpc.server import SimpleXMLRPCServer

# Global counter for processed requests
processed_requests_counter = Value('i', 0)

# Restrict to a particular path.
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)

# Create server
with SimpleXMLRPCServer(('localhost', 8010),
                        requestHandler=RequestHandler) as server:
    server.register_introspection_functions()

    class InsultFilter:
        def __init__(self, req_counter):
            self.insults = []   # received insults
            self.results = []   # censored text
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
                return self.counter.value

    insult_filter = InsultFilter(processed_requests_counter)
    server.register_instance(insult_filter)
    # Run the server's main loop
    print("Server is running...")
    server.serve_forever()