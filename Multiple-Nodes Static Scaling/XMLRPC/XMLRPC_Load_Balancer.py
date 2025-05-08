import xmlrpc.client
from xmlrpc.server import SimpleXMLRPCRequestHandler, SimpleXMLRPCServer
import argparse
import threading
import sys

class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)

class XmlrpcLoadBalancer:
    def __init__(self, backend_urls):
        self._backend_urls = backend_urls
        self.backend_proxies = [xmlrpc.client.ServerProxy(url, allow_none=True) for url in backend_urls]
        self.num_backends = len(self.backend_proxies)
        self.current_server_index = 0
        self.lock = threading.Lock()  # Lock to protect the index in round robin

    def get_next_proxy(self):
        with self.lock:
            proxy = self.backend_proxies[self.current_server_index]
            self.current_server_index = (self.current_server_index + 1) % self.num_backends
            return proxy

    # --- Methods for the InsultService ---
    def add_insult(self, insult):
        proxy = self.get_next_proxy()
        return proxy.add_insult(insult)

    def insult_me(self):
         proxy = self.get_next_proxy()
         return proxy.insult_me()

    # --- Method for the InsultFilter ---
    def filter(self, text):
        proxy = self.get_next_proxy()
        return proxy.filter(text)

    # --- Method to get the total request count ---
    def get_total_processed_count(self):
        total_count = 0
        for proxy in self.backend_proxies:
            try:
                # Assumes all backends implement get_processed_count
                count = proxy.get_processed_count()
                total_count += count
                print("Total count: " + str(total_count))
            except Exception as e:
                print(f"Error getting count from backend: {e}")
        return total_count

# --- Load Balancer Server Configuration and Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="XML-RPC Load Balancer")
    parser.add_argument("--port", type=int, required=True, help="Port to bind the load balancer to")
    parser.add_argument("--backend_urls", nargs='+', required=True,
                        help="List of backend service URLs (e.g., http://localhost:port1/RPC2 http://localhost:port2/RPC2)")
    parser.add_argument("--mode", choices=['service', 'filter'], required=True,
                        help="Mode of the load balancer ('service' or 'filter')")

    args = parser.parse_args()

    # Initialize the load balancer with the backend URLs
    lb = XmlrpcLoadBalancer(args.backend_urls)

# Create server
try:
    with SimpleXMLRPCServer(('localhost', args.port), requestHandler=RequestHandler, allow_none=True) as server:
        server.register_introspection_functions()

        # Register the load balancer methods.
        # Only register the methods corresponding to the mode ('service' or 'filter')
        if args.mode == 'service':
            server.register_function(lb.add_insult, "add_insult")
            server.register_function(lb.insult_me, "insult_me")
        elif args.mode == 'filter':
            server.register_function(lb.filter, "filter")

        # Register the key method for performance testing
        server.register_function(lb.get_total_processed_count, "get_processed_count")  # Or another name, but get_processed_count might be convenient for stress testing

        print(f"Load Balancer running on localhost:{args.port} in mode '{args.mode}'...")
        print(f"Backend servers: {args.backend_urls}")
        server.serve_forever()
except KeyboardInterrupt:
    print("\nShutting down LoadBalancer...")
    sys.exit(0)
except PermissionError:
    print(f"Error: Could not bind to port {port}. Permission denied. Try a port above 1024.", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"An error occurred: {e}", file=sys.stderr)
    sys.exit(1)