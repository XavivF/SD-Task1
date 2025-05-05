import redis
import time
import Pyro4
from multiprocessing import Process, Value

# Connect to Redis
client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

@Pyro4.behavior(instance_mode="single")
class InsultService:
    def __init__(self, service_counter):
        self.channel_insults = "Insults_channel"
        self.channel_broadcast = "Insults_broadcast"
        self.insultSet = "INSULTS"
        self.counter = service_counter  # Counter for the number of insults added

    def add_insult(self, insult):
        with self.counter.get_lock():
             self.counter.value += 1
        client.sadd(self.insultSet, insult)
        print(f"InsultService added: {insult} (Counter: {self.counter.value})")
        return f"Insult added: {insult}"

    def get_insults(self):
        insults_list = client.smembers(self.insultSet)
        return f"Insult list: {insults_list}"

    def insult_me(self):
        if client.scard(self.insultSet) != 0:
            insult = client.srandmember(self.insultSet)
            print(f"InsultService: chosen: {insult}")
            return insult
        return "Insult list is empty"

    # --- Background processes for this service ---

    def notify_subscribers(self):
        print("InsultService Worker: Starting notify_subscribers...")
        try:
            while True:
                insult = self.insult_me()
                if insult and insult != "Insult list is empty":
                    client.publish(self.channel_broadcast, insult)
                    # print(f"InsultService Worker: Notified subscribers with: {insult}")
                time.sleep(5)
        except KeyboardInterrupt:
            print("\nInsultService Worker: Stopping notify_subscribers...")

    def listen(self):
        print("InsultService Worker: Starting listen...")
        pubsub = client.pubsub()
        pubsub.subscribe(self.channel_insults)
        try:
            for message in pubsub.listen():
                if message['type'] == 'message':
                    insult = message['data']
                    print(f"InsultService Worker: Received insult via channel: {insult}")
                    self.add_insult(insult)
        except KeyboardInterrupt:
            print("\nInsultService Worker: Stopping listen process...")

    def get_status_daemon(self):
        print("InsultService Worker: Starting get_status_daemon...")
        try:
            while True:
                print("\n--- InsultService Status ---")
                print(self.get_insults())
                print(f"InsultService processed count: {self.get_processed_count()}")
                print("------------------------------\n")
                time.sleep(10)
        except KeyboardInterrupt:
            print("\nInsultService Worker: Stopping get_status_daemon...")

    @Pyro4.expose
    def get_processed_count(self):
        # Access the shared counter safely
        with self.counter.get_lock():
            return self.counter.value

# --- Main execution block for InsultService ---
if __name__ == "__main__":
    print("Starting InsultService...")

    processed_requests_counter = Value('i', 0)
    insults_service = InsultService(processed_requests_counter)     # Create the InsultService instance

    # --- Set up Pyro server ---
    print("Starting Pyro InsultService for remote access...")
    try:
        daemon = Pyro4.Daemon() # Create the Pyro daemon
        ns = Pyro4.locateNS()  # Locate the name server
    except Pyro4.errors.NamingError as e:
        print("Error locating the name server. Make sure it is running.")
        print("Command: python3 -m Pyro4.naming")
        exit(1)

    # Register the Insults service instance with the daemon and name server
    # Clients will connect to this name 'redis.insultservice'
    service_name = "redis.insultservice"
    uri = daemon.register(insults_service)
    try:
        ns.register(service_name, uri)
        print(f"InsultService registered as '{service_name}' at {uri}")
    except Pyro4.errors.NamingError as e:
        print(f"Error registering the service with the name server: {e}")
        exit(1)

    print("InsultService: Clearing initial Redis keys (INSULTS)...")
    client.delete(insults_service.insultSet)
    print("Redis keys cleared.")


    # --- Start background processes for InsultService ---
    print("InsultService: Starting worker processes...")
    process_service_notify = Process(target=insults_service.notify_subscribers)
    process_service_listen = Process(target=insults_service.listen)
    process_service_status = Process(target=insults_service.get_status_daemon)

    process_service_notify.start()
    process_service_listen.start()
    process_service_status.start()

    print("InsultService Pyro daemon started, waiting for remote requests...")
    print(f"Service '{service_name}' available.")

    try:
        daemon.requestLoop()
    except KeyboardInterrupt:
        print("\nShutting down InsultService...")
        print("Terminating worker processes...")
        process_service_notify.terminate()
        process_service_listen.terminate()
        process_service_status.terminate()

        process_service_notify.join()
        process_service_listen.join()
        process_service_status.join()
        print("InsultService worker processes finished.")

        print("Shutting down Pyro daemon...")
        daemon.shutdown()
        print("Pyro daemon shut down.")
        print("Exiting InsultService main program.")