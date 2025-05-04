import redis
import time
import Pyro4
from multiprocessing import Process, Value

# Connect to Redis
client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# Global counter for processed requests
processed_requests_counter = Value('i', 0)

@Pyro4.expose
@Pyro4.behavior(instance_mode="single")
class Insults:
    def __init__(self, req_counter):
        self.channel_insults = "Insults_channel"
        self.channel_broadcast = "Insults_broadcast"
        self.insultSet = "INSULTS"
        self.censoredTextsList = "RESULTS"
        self.workQueue = "Work_queue"
        self.counter = req_counter  # Counter for the number of insults added

    def add_insult(self, insult):
        with self.counter.get_lock():
             self.counter.value += 1
        client.sadd(self.insultSet, insult)
        print(f"Insult added: {insult}")
        return f"Insult added: {insult}"

    def get_insults(self):
        insult = client.smembers(self.insultSet)
        return f"Insult list: {insult}"

    def get_results(self):
        results = client.lrange(self.censoredTextsList, 0, -1)
        return f"Textos censorats:{results}"

    def insult_me(self):
        if client.scard(self.insultSet) != 0:
            insult = client.srandmember(self.insultSet)
            print(f"Insult escollit: {insult}")
            return insult
        return "Insult list is empty"

    def notify_subscribers(self):
        while True:
            insult = insults.insult_me()
            if insult:
                client.publish(self.channel_broadcast, insult)
                print(f"\nNotified subscribers.")
            time.sleep(5)

    def listen(self):
        while True:
            for message in pubsub.listen():
                print(f"Process message {message['data']}")
                if message['type'] == 'message':
                    insult = message['data']
                    print(f"Received insult: {insult}")
                    self.add_insult(insult)

    def filter(self, text):
        censored_text = ""
        if text is not None:
            for word in text.split():
                if word.lower() in client.smembers(self.insultSet):
                    censored_text += "CENSORED "
                else:
                    censored_text += word + " "
        return censored_text

    def filter_service(self):
        while True:
            text = client.blpop(self.workQueue)[1]
            with self.counter.get_lock():
                self.counter.value += 1
            filtered_text = self.filter(text)
            client.lpush(self.censoredTextsList, filtered_text)

    @Pyro4.expose
    def get_processed_count(self):
        # Access the shared counter safely
        with self.counter.get_lock():
            return self.counter.value

    def get_insults_daemon(self):
        while True:
            print(insults.get_insults())
            print(insults.get_results())
            time.sleep(5)

insults = Insults(processed_requests_counter)

# --- Set up Pyro server ---
print("Starting Pyro Insult Service for remote access...")
try:
    daemon = Pyro4.Daemon()  # Create the Pyro daemon
    ns = Pyro4.locateNS()  # Locate the name server
except Pyro4.errors.NamingError as e:
    # You need to have the name server running: python3 -m Pyro4.naming
    print("Error locating the name server. Make sure it is running.")
    print("Command: python3 -m Pyro4.naming")
    exit(1)

# Register the Insults service instance with the daemon and name server
# Clients will connect to this name 'rabbit.counter'
uri = daemon.register(insults)
try:
    ns.register("redis.counter", uri)
    print("Service registered with the name server as 'redis.counter'")
except Pyro4.errors.NamingError as e:
    print(f"Error registering the service with the name server: {e}")
    exit(1)

pubsub = client.pubsub()
pubsub.subscribe(insults.channel_insults)

client.delete(insults.insultSet)
client.delete(insults.censoredTextsList)
client.delete(insults.workQueue)

process1 = Process(target=insults.notify_subscribers)
process2 = Process(target=insults.listen)
process3 = Process(target=insults.filter_service)
process4 = Process(target=insults.get_insults_daemon)

process1.start()
process2.start()
process3.start()
process4.start()

print("Pyro daemon started, waiting for remote requests...")
while True:
    try:
        daemon.requestLoop()
    except KeyboardInterrupt:
        print("Exiting...")
        process1.terminate()
        process2.terminate()
        process3.terminate()
        process4.terminate()
        process1.join()
        process2.join()
        process3.join()
        process4.join()
        print("Worker processes finished.")
        print("Shutting down Pyro daemon...")
        daemon.shutdown()
        print("Pyro daemon shut down.")
        print("Exiting main program.")
        break