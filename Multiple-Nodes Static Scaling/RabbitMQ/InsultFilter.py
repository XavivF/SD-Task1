import argparse
import Pyro4
import pika
from multiprocessing import Manager, Process
import redis
from Pyro4 import errors

class InsultFilter:
    def __init__(self, shared_insult_list, shared_censored_texts):
        self.channel_insults = "Insults_channel"
        self.insults_list = shared_insult_list  # list of insults
        self.censored_texts = shared_censored_texts # list for censored texts
        self.text_queue = "text_queue"
        self.counter_key = "COUNTER"
        self.client = redis.Redis(db=0, decode_responses=True)

    def filter(self, text):
        censored_text = ""
        current_insults = list(self.insults_list)
        for word in text.split():
            if word.lower() in current_insults:
                censored_text += "CENSORED "
            else:
                censored_text += word + " "
        return censored_text.strip()

    def filter_service(self):
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        channel = connection.channel()
        channel.queue_declare(queue=self.text_queue)
        channel.basic_qos(prefetch_count=1)

        def callback(ch, method, properties, body):
            text = body.decode('utf-8')
            filtered_text = self.filter(text)
            self.client.incr(self.counter_key)
            if filtered_text not in self.censored_texts:
                self.censored_texts.append(filtered_text)
            # print(f"Censored text: {filtered_text}")

        channel.basic_consume(queue=self.text_queue, on_message_callback=callback, auto_ack=True)
        print(f"Waiting for texts to censor at {self.text_queue}...")
        channel.start_consuming()

    def get_results(self):
        return f"Censored texts: {list(self.censored_texts)}"

    def get_processed_count(self):
        count = self.client.get(self.counter_key)
        return int(count) if count else 0

# Example of how to run the InsultFilterService
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-id", "--instance-id", type=int, default=1, help="Service instance ID", required=True)
    args = parser.parse_args()

    manager = Manager()
    # Create a shared list for insults
    shared_insults = manager.list()
    initial_insults = ["tonto", "lleig", "boig", "idiota", "estúpid", "inútil", "desastre", "fracassat", "covard",
                       "mentider","beneit", "capsigrany", "ganàpia", "nyicris", "gamarús", "bocamoll", "murri",
                       "dropo", "bleda", "xitxarel·lo"]
    shared_insults.extend(initial_insults)

    # Create a shared list for censored texts
    shared_texts = manager.list()
    # Create the service instance with the shared resources
    filter_service_instance = InsultFilter(shared_insults, shared_texts)

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
    uri = daemon.register(filter_service_instance)
    try:
        ns.register(f"rabbit.filter.{args.instance_id}", uri)
        print(f"Service registered with the name server as 'rabbit.filter.{args.instance_id}'")
    except Pyro4.errors.NamingError as e:
        print(f"Error registering the service with the name server: {e}")
        exit(1)

    print("InsultService: Clearing initial Redis keys (INSULTS_COUNTER)...")
    filter_service_instance.client.delete(filter_service_instance.counter_key)
    print("Redis keys cleared.")

    process_filter_service = Process(target=filter_service_instance.filter_service)

    # Start the worker processes
    process_filter_service.start()
    try:
        daemon.requestLoop()
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        print("Terminating worker processes...")
        process_filter_service.terminate()
        process_filter_service.join()
        daemon.shutdown()
        print("Worker processes finished.")
        print("Exiting main program.")

