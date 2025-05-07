import random
import threading
import Pyro4

@Pyro4.expose
@Pyro4.behavior(instance_mode="single")
class InsultFilter:
    def __init__(self):
        self.censored_Texts = []
        self.insults_List = []
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
    print("Starting Pyro Insult Filter...")
    try:
        daemon = Pyro4.Daemon()  # Create the Pyro daemon
        ns = Pyro4.locateNS()  # Locate the name server
    except Pyro4.errors.NamingError:
        # You need to have the name server running: python3 -m Pyro4.naming
        print("Error locating the name server. Make sure it is running.")
        print("Command: python3 -m Pyro4.naming")
        exit(1)
    uri = daemon.register(InsultFilter)  # Register the service as a Pyro object
    ns.register("pyro.filter", uri)  # Register the service with a name
    print("Insult Filter is ready.")
    daemon.requestLoop()  # Start the event loop of the server to wait for calls


if __name__ == "__main__":
    main()