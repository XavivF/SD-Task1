import argparse
import Pyro4
import sys
import threading
import redis
@Pyro4.expose
@Pyro4.behavior(instance_mode="single")
class LoadBalancer:
    def __init__(self, filter_service_names, insult_service_names):
        self.ns = Pyro4.locateNS()
        self.filter_proxies = []
        self.insult_proxies = []
        self.get_proxies(filter_service_names)
        self.get_proxies(insult_service_names)
        self.filter_rr = 0
        self.service_rr = 0
        self.lock = threading.Lock()
        self.counter_key = "COUNTER"  # Key for Redis counter
        self.client = redis.Redis(db=0, decode_responses=True)

    def get_proxies(self, service_names):
        for name in service_names:
            try:
                uri = self.ns.lookup(name)
                proxy = Pyro4.Proxy(uri)
                proxy._pyroTimeout = 5 # Timeout for calls
                if name.startswith("pyro.filter."):
                    self.filter_proxies.append(proxy)
                elif name.startswith("pyro.service."):
                    self.insult_proxies.append(proxy)
                print(f"Proxy created for {name} ({uri})")
            except Pyro4.errors.NamingError:
                print(f"WARNING: Pyro service name '{name}' not found in Name Server.", file=sys.stderr)
            except Exception as e:
                print(f"ERROR creating proxy for name {name}: {e}", file=sys.stderr)
        return None

    def add_insult(self, insult):
        try:
            with self.lock:
                service_proxy = self.insult_proxies[self.service_rr]
                self.service_rr = (self.service_rr + 1) % len(self.insult_proxies)
            service_proxy.add_insult(insult)
            self.client.incr(self.counter_key)  # INCR Redis Counter
            # print(f"Insult added: {insult} to {service_proxy._pyroUri}")
        except Exception as e:
            print(f"ERROR: Exception during adding insult: {e}", file=sys.stderr)

    def filter_service(self, text):
        try:
            with self.lock:
                filter_proxy = self.filter_proxies[self.filter_rr]
                self.filter_rr = (self.filter_rr + 1) % len(self.filter_proxies)
            result = filter_proxy.filter_service(text) # Call to the real InsultFilter method
            self.client.incr(self.counter_key)  # INCR Redis Counter
            # print("Filtered text:", result)
            return result
        except Exception as e:
            return f"ERROR: Exception during filtering: {e}"

    def insult_me(self):
        try:
            with self.lock:
                service_proxy = self.insult_proxies[self.service_rr]
                self.service_rr = (self.service_rr + 1) % len(self.insult_proxies)
            insult = service_proxy.insult_me()
            print(f"Insult received: {insult} from {service_proxy._pyroUri}")
            return insult
        except Exception as e:
            return f"ERROR: Exception during getting insult: {e}"

    def subscribe(self, url):
        print(f"LB: Adding subscriber {url} to all insult services.")
        for proxy in self.insult_proxies:
            try:
                proxy.subscribe(url) # Each InsultService subscribes its subscribers
                print(f"LB: Subscriber added via {proxy._pyroUri}")
            except Exception as e:
                print(f"LB: Error adding subscriber via {proxy._pyroUri}: {e}", file=sys.stderr)
        return None


    def get_insults(self):
        if self.insult_proxies:
            try:
                response = []
                for proxy in self.insult_proxies:
                    response.extend(proxy.get_insults())
                return response
            except Exception as e:
                print(f"ERROR in load balancer (get_insults_balanced): {e}", file=sys.stderr)
                return None
        print("WARNING: No insult services available for get_insults_balanced.", file=sys.stderr)
        return None

    def get_censored_texts(self):
        if self.filter_proxies:
            try:
                response = []
                for proxy in self.filter_proxies:
                    response.extend(proxy.get_censored_texts())
                return response
            except Exception as e:
                print(f"ERROR in load balancer (get_censored_texts_balanced): {e}", file=sys.stderr)
                return None
        print("WARNING: No filter services available for get_censored_texts_balanced.", file=sys.stderr)
        return None

    def notify_subscribers(self, insult):
        print(f"LB: Forwarding notify_subscribers for insult '{insult}' to all insult services.")
        errors = 0
        for proxy in self.insult_proxies:
            try:
                proxy.notify_subscribers(insult) # Each InsultService notifies its subscribers
            except Exception as e:
                errors += 1
                print(f"LB: Error notifying subscribers via {proxy._pyroUri}: {e}", file=sys.stderr)
        if errors > 0:
            print(f"LB: {errors} errors occurred during notify_subscribers_balanced.", file=sys.stderr)

    # --- Method to get the total request count ---
    def get_processed_count(self):
        count = self.client.get(self.counter_key)
        print(f"Load Balancer returning processed count: {count}")
        return int(count) if count else 0

def main():
    parser = argparse.ArgumentParser(description="Pyro Load Balancer")
    parser.add_argument("-ns", "--names-service", nargs='+', default=[],
                        help="List of InsultService pyro names separated by spaces (e.g., pyro.service.1 pyro.service.2)")
    parser.add_argument("-nf", "--names-filter", nargs='+', default=[],
                        help="List of InsultFilter pyro names separated by spaces (e.g., pyro.filter.1 pyro.filter.2)")

    args = parser.parse_args()
    if not args.names_service and not args.names_filter:
        print("Error: At least one service name must be provided for either filter or service.", file=sys.stderr)
        print("Usage: python LoadBalancer.py -ns <service_names> -nf <filter_names>", file=sys.stderr)
        sys.exit(1)
    load_balancer_pyro_name = "pyro.loadbalancer"
    try:
        daemon = Pyro4.Daemon()
        ns = Pyro4.locateNS()
        lb_instance = LoadBalancer(args.names_filter, args.names_service)
        uri = daemon.register(lb_instance)
        ns.register(load_balancer_pyro_name, uri)

        print("LoadBalancer: Clearing initial Redis key (COUNTER)...")
        lb_instance.client.delete(lb_instance.counter_key)
        print("Redis keys cleared.")

        print(f"LoadBalancer registered as '{load_balancer_pyro_name}' with URI: {uri}")
        print(f"The LoadBalancer is ready. URI: {uri}")
    except Pyro4.errors.NamingError:
        print("Error: Could not locate the Pyro Name Server. Ensure it is running.", file=sys.stderr)
        print("Run: python -m Pyro4.naming", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error starting the LoadBalancer: {e}", file=sys.stderr)
        sys.exit(1)

    print("The LoadBalancer is running. Press Ctrl+C to exit.")
    daemon.requestLoop()

if __name__ == "__main__":
    main()