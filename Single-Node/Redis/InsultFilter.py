import redis
import Pyro4
from multiprocessing import Value, Process
import time

client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

@Pyro4.behavior(instance_mode="single")
class InsultFilter:
    def __init__(self, filter_counter):
        self.insultSet = "INSULTS"
        self.censoredTextsList = "RESULTS"
        self.workQueue = "Work_queue"
        self.counter = filter_counter # Counter for the number of times filtered text

    def add_insult(self, insult):
        with self.counter.get_lock():
             self.counter.value += 1
        client.sadd(self.insultSet, insult)
        # print(f"InsultFilter: Insult added (internal): {insult} (Counter: {self.counter.value})")
        return f"Insult added (internal): {insult}"

    def filter_text(self, text):
        # print(f"InsultFilter: Received text to filter: {text}")
        censored_text = ""
        if text is not None:
            insults = client.smembers(self.insultSet)
            for word in text.split():
                if word.lower() in insults:
                    censored_text += "CENSORED "
                else:
                    censored_text += word + " "
        return censored_text.strip() # Remove trailing space

    def get_censored_texts(self):
        results = client.lrange(self.censoredTextsList, 0, -1)
        return f"Censored texts:{results}"

    def filter_service(self):
        print("InsultFilter Service: Starting filter_service...")
        try:
            while True:
                item = client.blpop(self.workQueue)     # Blocking pop from the work queue
                if item:
                    queue_name, text = item
                    # print(f"InsultFilter Worker: Processing text from {queue_name}: Text: {text}")
                    with self.counter.get_lock():
                        self.counter.value += 1
                    filtered_text = self.filter_text(text)
                    # print(f"InsultFilter Worker: Filtered text: {filtered_text} (Counter: {self.counter.value})")
                    client.rpush(self.censoredTextsList, filtered_text)
        except KeyboardInterrupt:
            print("\nInsultFilter Service: Stopping filter_service...")
            exit(1)

    def get_status_daemon(self):
        print("InsultFilter Worker: Starting get_status_daemon...")
        try:
            while True:
                print("\n--- InsultFilter Status ---")
                print(self.get_censored_texts())
                print(f"InsultFilter processed count: {self.get_processed_count()}")
                print("------------------------------\n")
                time.sleep(10)
        except KeyboardInterrupt:
            print("\nInsultFilter Worker: Stopping get_status_daemon...")

    @Pyro4.expose
    def get_processed_count(self):
        # Access the shared counter safely
        with self.counter.get_lock():
            return self.counter.value

# --- Main execution block for InsultFilter ---
if __name__ == "__main__":
    print("Starting InsultFilter...")

    filtered_requests_counter = Value('i', 0)
    insult_filter = InsultFilter(filtered_requests_counter)     # Create the InsultFilter instance

    # --- Set up Pyro server ---
    print("Starting Pyro InsultFilter for remote access...")
    try:
        daemon = Pyro4.Daemon()  # Create the Pyro daemon
        ns = Pyro4.locateNS()  # Locate the name server
    except Pyro4.errors.NamingError as e:
        # You need to have the name server running: python3 -m Pyro4.naming
        print("Error locating the name server. Make sure it is running.")
        print("Command: python3 -m Pyro4.naming")
        exit(1)

    # Register InsultFilter service instance with the daemon and name server
    # Clients will connect to this name 'redis.insultfilter'
    filter_name = "redis.insultfilter"
    uri = daemon.register(insult_filter)
    try:
        ns.register(filter_name, uri)
        print(f"InsultFilter registered as '{filter_name}' at {uri}")
    except Pyro4.errors.NamingError as e:
        print(f"Error registering the service with the name server: {e}")
        exit(1)

    print("InsultFilter: Clearing initial Redis keys (INSULTS, RESULTS, Work_queue)...")
    client.delete(insult_filter.insultSet)
    client.delete(insult_filter.censoredTextsList)
    client.delete(insult_filter.workQueue)
    print("Redis keys cleared.")

    # --- Start background processes for InsultFilter ---
    print("InsultFilter: Starting worker processes...")
    process_filter_service = Process(target=insult_filter.filter_service)
    process_service_status = Process(target=insult_filter.get_status_daemon)

    process_filter_service.start()
    process_service_status.start()

    print("InsultFilter Pyro daemon started, waiting for remote requests...")
    print(f"Service '{filter_name}' available.")

    try:
        daemon.requestLoop()
    except KeyboardInterrupt:
        print("\nShutting down InsultFilter...")
        print("Terminating worker processes...")
        # Terminate and join worker processes
        process_filter_service.terminate()
        process_service_status.terminate()
        process_filter_service.join()
        process_filter_service.terminate()
        print("InsultFilter worker processes finished.")

        print("Shutting down Pyro daemon...")
        daemon.shutdown()
        print("Pyro daemon shut down.")
        print("Exiting InsultFilter main program.")