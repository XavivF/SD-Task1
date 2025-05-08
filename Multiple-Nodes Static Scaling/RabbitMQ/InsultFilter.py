import argparse
import Pyro4
import pika
from multiprocessing import Manager, Value, Process

processed_requests_counter = Value('i', 0)

@Pyro4.expose
@Pyro4.behavior(instance_mode="single")
class InsultFilter:
    def __init__(self, req_counter, shared_insult_list, shared_censored_texts):
        self.channel_insults = "Insults_channel"
        self.insults_list = shared_insult_list  # list of insults
        self.censored_texts = shared_censored_texts # list for censored texts
        self.text_queue = "text_queue"
        self.insults_exchange = "insults_exchange"
        self.counter = req_counter  # Shared counter for processed requests

    def add_insult(self, insult):
        with self.counter.get_lock():
             self.counter.value += 1
        if insult not in self.insults_list:
            self.insults_list.append(insult)
            print(f"Insult added: {insult}")

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

        def callback(ch, method, properties, body):
            text = body.decode('utf-8')
            filtered_text = self.filter(text)
            with self.counter.get_lock():
                self.counter.value += 1
            if filtered_text not in self.censored_texts:
                self.censored_texts.append(filtered_text)
            # print(f"Censored text: {filtered_text}")

        channel.basic_consume(queue=self.text_queue, on_message_callback=callback, auto_ack=True)
        print(f"Waiting for texts to censor at {self.text_queue}...")
        channel.start_consuming()

    def listen_insults(self):
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        channel = connection.channel()

        # Declare the same fanout exchange as the publisher
        channel.exchange_declare(exchange=self.insults_exchange, exchange_type='fanout')

        # Declare a unique, temporary queue for this worker
        # queue='' generates a unique name, exclusive=True deletes the queue when connection closes
        unique_queue = channel.queue_declare(queue='', exclusive=True)
        unique_queue_name = unique_queue.method.queue

        # Bind the worker's queue to the fanout exchange
        channel.queue_bind(exchange=self.insults_exchange, queue=unique_queue_name)

        def callback(ch, method, properties, body):
            insult = body.decode('utf-8')
            # print(f"Received insult: {insult}")
            self.add_insult(insult)

        channel.basic_consume(queue=unique_queue_name, on_message_callback=callback, auto_ack=True)
        # print(f"Waiting for messages at {self.channel_insults}...")
        channel.start_consuming()

    def get_results(self):
        return f"Censored texts: {list(self.censored_texts)}"

    def get_processed_count(self):
        with self.counter.get_lock():
            return self.counter.value

# Example of how to run the InsultFilterService
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-id", "--instance-id", type=int, default=1, help="Service instance ID", required=True)
    args = parser.parse_args()

    manager = Manager()
    # Create a shared list for insults
    shared_insults = manager.list()
    # Create a shared list for censored texts
    shared_texts = manager.list()
    # Create the service instance with the shared resources
    filter_service_instance = InsultFilter(processed_requests_counter, shared_insults, shared_texts)

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

    process_filter_service = Process(target=filter_service_instance.filter_service)
    process_listen_insults = Process(target=filter_service_instance.listen_insults)

    # Start the worker processes
    process_filter_service.start()
    process_listen_insults.start()
    # --- Start the Pyro request loop ---
    # This loop will block and wait for incoming Pyro calls while
    # The worker processes run concurrently.
    print("Pyro daemon started, waiting for requests...")
    try:
        daemon.requestLoop()  # Start the event loop of the server to wait for calls
    except KeyboardInterrupt:
        print("Pyro daemon interrupted. Shutting down...")
    finally:
        # Cleanly terminate worker processes if the Pyro daemon is stopped
        print("Terminating worker processes...")
        process_filter_service.terminate()
        process_listen_insults.terminate()
        process_filter_service.join()
        process_listen_insults.join()
        print("Worker processes finished.")
        # Shutdown Pyro daemon
        print("Shutting down Pyro daemon...")
        daemon.shutdown()
        print("Pyro daemon shut down.")
        print("Exiting main program.")

