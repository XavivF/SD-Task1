import threading
import Pyro4
import argparse
import sys

@Pyro4.expose
@Pyro4.behavior(instance_mode="single")
class InsultFilter:
    def __init__(self):
        self.censored_Texts = []
        self.insults_List = ["beneit", "capsigrany", "ganàpia", "nyicris", "gamarús", "bocamoll", "murri", "dropo", "bleda", "xitxarel·lo"]
        self.processed_requests_count = 0
        self._lock = threading.Lock() # Lock to securely access the counter

    def add_insult(self, insult):
        with self._lock:
            self.processed_requests_count += 1
        if insult not in self.insults_List:
            self.insults_List.append(insult)
            # print(f"Insult added: {insult}")
        # else:
            # print(f"Insult already exists: {insult}")

    def filter_text(self, text):
        censored_text = ""
        # we use a copy of the insults list to avoid any modifications it while iterating
        current_insults = list(self.insults_List) # Use the insult list available to this service
        for word in text.split():
            if word.lower() in current_insults:
                censored_text += "CENSORED "
            else:
                censored_text += word + " "
        return censored_text

    def filter_service(self, text):
        with self._lock:
            self.processed_requests_count += 1
        censored_text = self.filter_text(text)
        self.censored_Texts.append(censored_text)
        return censored_text.strip() # We add strip() to remove trailing spaces

    def get_censored_texts(self):
        return self.censored_Texts

    def get_processed_count(self):
        with self._lock:
            return self.processed_requests_count

def main():
    parser = argparse.ArgumentParser(description="Pyro Insult Filter")
    parser.add_argument("--port", type=int, default=8000, required=True,
                        help="Port to bind the daemon to (default: 8000)")

    parser.add_argument("-id", "--instance-id", type=int, default=1, required=True,
                        help="Filter instance ID (e.g., 1, 2, 3)")
    args = parser.parse_args()
    pyro_name = f"pyro.filter.{args.instance_id}"
    print(f"Starting Pyro Insult Filter with ID {args.instance_id} and name '{pyro_name}'...")

    try:
        daemon = Pyro4.Daemon(host=None, port=args.port)  # Create the Pyro daemon with the specified port
        ns = Pyro4.locateNS()
    except Pyro4.errors.NamingError:
        # You need to have the name server running: python3 -m Pyro4.naming
        print("Error locating the name server. Make sure it is running.")
        print("Command: python3 -m Pyro4.naming")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred during Pyro initialization: {e}", file=sys.stderr)
        sys.exit(1)

    uri = daemon.register(InsultFilter)  # Register the service as a Pyro object
    # Register the instance with the unique name
    try:
        ns.register(pyro_name, uri)
        print(f"Insult Filter registered as '{pyro_name}' with URI: {uri}")
    except Pyro4.errors.NamingError as e:
        print(f"Error registering service '{pyro_name}' with the name server: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Insult Filter ID {args.instance_id} is ready.")
    daemon.requestLoop()  # Start the event loop of the server to wait for calls


if __name__ == "__main__":
    main()