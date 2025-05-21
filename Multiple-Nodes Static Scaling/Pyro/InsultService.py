import argparse
import random
import Pyro4
import sys
import redis
from Pyro4 import errors

@Pyro4.expose
@Pyro4.behavior(instance_mode="single")
class InsultService:
    def __init__(self):
        self.insults_List = []
        self.subscribers = []
        self.counter_key = "COUNTER"
        self.client = redis.Redis(db=0, decode_responses=True)

    def add_insult(self, insult):
        if insult not in self.insults_List:
            self.insults_List.append(insult)
        self.client.incr(self.counter_key)

    def get_insults(self):
        return self.insults_List

    def insult_me(self):
        if not self.insults_List:
            return "No insults available"
        insult = random.choice(self.insults_List)
        print(f"Selected insult: {insult}")
        return insult

    def subscribe(self, url):
        try:
            client_proxy = Pyro4.Proxy(url)
            self.subscribers.append(client_proxy)
            print("New subscriber added.")
        except Exception as e:
             print(f"Error afegint subscriptor {url}: {e}")

    def notify_subscribers(self, insult):
        for subscriber in self.subscribers:
            try:
                print(f"Notifying subscriber: {subscriber} with:" + insult) # Comentem
                subscriber.receive_insult(insult)
            except Pyro4.errors.CommunicationError:
                print("Failed to contact a subscriber.")


def main():
    parser = argparse.ArgumentParser(description="Pyro Insult Service")
    parser.add_argument("--port", type=int, default=8000, required=True,
                        help="Port to bind the daemon to (default: 8000)")

    parser.add_argument("-id", "--instance-id", type=int, default=1, required=True,
                        help="Service instance ID (e.g., 1, 2, 3)")
    args = parser.parse_args()
    pyro_name = f"pyro.service.{args.instance_id}"
    print(f"Starting Pyro Insult Service with ID {args.instance_id} and name '{pyro_name}'...")

    try:
        daemon = Pyro4.Daemon(host=None, port=args.port)   # Create the Pyro daemon with the specified port
        ns = Pyro4.locateNS()
    except Pyro4.errors.NamingError:
        # You need to have the name server running: python3 -m Pyro4.naming
        print("Error locating the name server. Make sure it is running.")
        print("Command: python3 -m Pyro4.naming")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred during Pyro initialization: {e}", file=sys.stderr)
        sys.exit(1)

    uri = daemon.register(InsultService)    # Register the service as a Pyro object
    # Register the instance with the unique name
    try:
        ns.register(pyro_name, uri)
        print(f"Insult Service registered as '{pyro_name}' with URI: {uri}")
    except Pyro4.errors.NamingError as e:
        print(f"Error registering service '{pyro_name}' with the name server: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Insult Service ID {args.instance_id} is ready.")
    daemon.requestLoop()  # Start the event loop of the server to wait for calls

if __name__ == "__main__":
    main()