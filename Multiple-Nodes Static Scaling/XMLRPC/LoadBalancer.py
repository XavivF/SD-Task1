import xmlrpc.client
from xmlrpc.server import SimpleXMLRPCRequestHandler, SimpleXMLRPCServer
import argparse
import threading
import sys
import redis

class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)

class XmlrpcLoadBalancer:
    def __init__(self, service_urls, filter_urls):
        self.service_proxies = [xmlrpc.client.ServerProxy(url, allow_none=True) for url in service_urls]
        self.filter_proxies = [xmlrpc.client.ServerProxy(url, allow_none=True) for url in filter_urls]
        self.num_services = len(self.service_proxies)
        self.num_filters = len(self.filter_proxies)
        self.current_service_index = 0
        self.current_filter_index = 0
        self.service_lock = threading.Lock()
        self.filter_lock = threading.Lock()  # Lock to protect the index in round-robin
        self.counter_key = "COUNTER"  # Key for Redis counter
        self.client = redis.Redis(db=0, decode_responses=True)


    def get_next_service_proxy(self):
        with self.service_lock:
            if not self.service_proxies:
                raise Exception("No InsultService backends available.")
            proxy = self.service_proxies[self.current_service_index]
            self.current_service_index = (self.current_service_index + 1) % self.num_services
            return proxy

    def get_next_filter_proxy(self):
        with self.filter_lock:
            if not self.filter_proxies:
                raise Exception("No InsultFilter backends available.")
            proxy = self.filter_proxies[self.current_filter_index]
            self.current_filter_index = (self.current_filter_index + 1) % self.num_filters
            return proxy

    # --- Methods for the InsultService ---
    def add_insult(self, insult):
        try:
            proxy = self.get_next_service_proxy()
            self.client.incr(self.counter_key)  # INCR Redis Counter
            # print(f"LB: Add insult '{insult}' to service: {proxy._XmlRpcClient__host_port_path}")
            return proxy.add_insult(insult)
        except Exception as error:
            print(f"ERROR on LB add_insult: {error}", file=sys.stderr)
            raise

    def insult_me(self):
        try:
            proxy = self.get_next_service_proxy()
            self.client.incr(self.counter_key)  # INCR Redis Counter
            # print(f"LB: Requesting insult from service: {proxy._XmlRpcClient__host_port_path}")
            return proxy.insult_me()  # L'InsultService escollit notificarà els seus subscriptors.
        except Exception as error:
            print(f"ERROR on LB insult_me: {error}", file=sys.stderr)
            raise

    def get_insults(self):
        if self.num_services > 0:
            try:
                response = []
                for proxy in self.service_proxies:
                    response.extend(proxy.get_insults())
                return response
            except Exception as error:
                print(f"ERROR obtaining results from service backend: {error}", file=sys.stderr)
                raise
        return []

    # --- Method for the InsultFilter ---
    def filter(self, text):
        try:
            proxy = self.get_next_filter_proxy()
            self.client.incr(self.counter_key)  # INCR Redis Counter
            # print(f"LB: Filtering text '{text}' via filter: {proxy._XmlRpcClient__host_port_path}")
            return proxy.filter(text)
        except Exception as error:
            print(f"ERROR on LB filter: {error}", file=sys.stderr)
            raise

    def get_results(self):
        if self.num_filters > 0:
            try:
                response = []
                for proxy in self.filter_proxies:
                    response.extend(proxy.get_results())
                return response
            except Exception as error:
                print(f"ERROR obtaining results from filter backend: {error}", file=sys.stderr)
                raise
        return []
    # --- Method to add a subscriber to all backends ---
    def add_subscriber(self, url):
        print(f"LB: Adding subscriber {url} to all InsultService backends.")
        errors = 0
        for proxy in self.service_proxies:
            try:
                proxy.add_subscriber(url)
                print(f"LoadBalancer: Subscriber added via {proxy._XmlRpcClient__host_port_path}")
            except Exception as error:
                errors += 1
                print(f"LoadBalancer: Error adding subscriber via {proxy._XmlRpcClient__host_port_path}: {error}",
                      file=sys.stderr)
        if errors > 0:

            raise Exception(f"Errors adding subscribers on {errors} services.")
        return "Subscriber added to all services."

    def notify_subscribers(self, insult):
        print(f"LB: Forwarding notify_subscribers for insult '{insult}' to all insult services.")
        errors = 0
        for proxy in self.service_proxies:
            try:
                proxy.notify_subscribers(insult)  # Each InsultService notifies its subscribers
            except Exception as error:
                errors += 1
                print(f"LB: Error notifying subscribers via {proxy._pyroUri}: {error}", file=sys.stderr)
        if errors > 0:
            print(f"LB: {errors} errors occurred during notify_subscribers_balanced.", file=sys.stderr)

    # --- Method to get the total request count ---
    def get_processed_count(self):
        count = self.client.get(self.counter_key)
        print(f"Load Balancer returning processed count: {count}")
        return int(count) if count else 0

# --- Load Balancer Server Configuration and Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="XML-RPC Load Balancer")
    parser.add_argument("--port", type=int, default=9000, help="Port to bind the load balancer to")
    parser.add_argument("--service_urls", nargs='+', default=[],
                        help="List of URLs of instances of InsultService (e.g., http://localhost:8001/RPC2 http://localhost:8002/RPC2)")
    parser.add_argument("--filter_urls", nargs='+', default=[],
                        help="List of URLs of instances of InsultFilter (e.g., http://localhost:8011/RPC2 http://localhost:8012/RPC2)")

    args = parser.parse_args()

    lb_instance = XmlrpcLoadBalancer(args.service_urls, args.filter_urls)

    print(f"llsita proxies: {lb_instance.service_proxies}")

    # Create server
    try:
        with SimpleXMLRPCServer(('localhost', args.port), requestHandler=RequestHandler, allow_none=True) as server:
            server.register_introspection_functions()

            # Register the load balancer instance
            server.register_instance(lb_instance)

            # Register the key method for performance testing
            server.register_function(lb_instance.get_processed_count, "get_processed_count")

            print("LoadBalancer: Clearing initial Redis key (COUNTER)...")
            lb_instance.client.delete(lb_instance.counter_key)
            print("Redis keys cleared.")

            print(f"Load Balancer running on localhost:{args.port}...")
            print(f"Filter servers: {args.filter_urls}")
            print(f"Service servers: {args.service_urls}")
            server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down LoadBalancer...")
        lb_instance.client.close()
        sys.exit(0)
    except PermissionError:
        print(f"Error: Could not bind to port {args.port}. Permission denied. Try a port above 1024.", file=sys.stderr)
        sys.exit(1)
    except Exception as exception:
        print(f"An error occurred: {exception}", file=sys.stderr)
        sys.exit(1)