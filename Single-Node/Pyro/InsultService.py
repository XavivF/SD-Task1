import random
import threading
import Pyro4

@Pyro4.expose
@Pyro4.behavior(instance_mode="single")
class InsultService:
    def __init__(self):
        self.insults_List = []
        self.censored_texts = []
        self.subscribers = []
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

    def get_insults(self):
        print(f"Insult list: {self.insults_List}")
        return self.insults_List

    def insult_me(self):
        if not self.insults_List:
            return "No insults available"
        insult = random.choice(self.insults_List)
        print(f"Selected insult: {insult}")
        return insult

    def filter_text(self, text):
        censored_text = ""
        # we use a copy of the insults list to avoid any modifications it while iterating
        current_insults = list(self.insults_List)
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
        self.censored_texts.append(censored_text)
        # print(f"Censored text: {censored_text}") # Comentem
        return censored_text.strip() # We add strip() to remove trailing spaces

    def get_censored_texts(self):
        print(f"Censored texts: {self.censored_texts}")
        return self.censored_texts

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

    def get_processed_count(self):
        with self._lock:
            return self.processed_requests_count


def main():
    print("Starting Pyro Insult Service...")
    daemon = Pyro4.Daemon()  # Create the Pyro daemon
    # We need to have the name server running: python3 -m Pyro4.naming
    ns = Pyro4.locateNS()  # Locate the name server
    uri = daemon.register(InsultService)  # Register the service as a Pyro object
    ns.register("example.insults", uri)  # Register the service with a name
    print("Insult Service is ready.")
    daemon.requestLoop()  # Start the event loop of the server to wait for calls


if __name__ == "__main__":
    main()