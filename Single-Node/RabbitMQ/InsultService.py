import pika
import time
import random
from multiprocessing import Process, Manager, Value
import Pyro4

# Global counter for processed requests
processed_requests_counter = Value('i', 0)

@Pyro4.expose
@Pyro4.behavior(instance_mode="single")
class Insults:
    def __init__(self, shared_insults, sh_censored_texts, req_counter):
        self.channel_insults = "Insults_channel"
        self.channel_broadcast = "Insults_broadcast"
        self.insults_list = shared_insults  # Is a shared list
        self.censored_texts = sh_censored_texts
        self.work_queue = "Work_queue"
        self.counter = req_counter  # Counter for the number of insults added

    def add_insult(self, insult):
        with self.counter.get_lock():
             self.counter.value += 1
        if insult not in self.insults_list:
            self.insults_list.append(insult)
            # print(f"Insult added: {insult}")
        else:
            # print(f"This insult already exists: {insult}")
            pass

    def get_insults(self):
        return f"Insult list: {list(self.insults_list)}"

    def get_results(self):
        return f"Censored texts: {self.censored_texts}"

    def insult_me(self):
        if self.insults_list:
            insult = random.choice(self.insults_list)
            # print(f"Chosen insult: {insult}")
            return insult
        return None

    def notify_subscribers(self):
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        channel = connection.channel()
        channel.exchange_declare(exchange=self.channel_broadcast, exchange_type='fanout')

        while True:
            if self.insults_list:
                insult = self.insult_me()
                if insult is not None:
                    # print(f"Sending insult to subscribers: {insult}")
                    channel.basic_publish(exchange=self.channel_broadcast, routing_key='', body=insult)
                    # print(f"\nNotified subscribers : {insult}")
            time.sleep(5)

    def listen(self):
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        channel = connection.channel()
        channel.queue_declare(queue=self.channel_insults)

        def callback(ch, method, properties, body):
            insult = body.decode('utf-8')
            # print(f"Received insult: {insult}")
            self.add_insult(insult)

        channel.basic_consume(queue=self.channel_insults, on_message_callback=callback, auto_ack=True)
        # print(f"Waiting for messages at {self.channel_insults}...")
        channel.start_consuming()

    def filter(self, text):
        censored_text = ""
        for word in text.split():
            if word.lower() in self.insults_list:
                censored_text += "CENSORED "
            else:
                censored_text += word + " "
        return censored_text

    def filter_service(self):
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        channel = connection.channel()
        channel.queue_declare(queue=self.work_queue)

        def callback(ch, method, properties, body):
            text = body.decode('utf-8')
            filtered_text = self.filter(text)
            with self.counter.get_lock():
                self.counter.value += 1
            if filtered_text not in self.censored_texts:
                self.censored_texts.append(filtered_text)
            # print(f"Censored text: {filtered_text}")

        channel.basic_consume(queue=self.work_queue, on_message_callback=callback, auto_ack=True)
        print(f"Waiting for texts to censor at {self.work_queue}...")
        channel.start_consuming()

    @Pyro4.expose
    def get_processed_count(self):
        # Access the shared counter safely
        with self.counter.get_lock():
            return self.counter.value

if __name__ == "__main__":
    with Manager() as manager:
        shared_insults_list = manager.list()  # Crate a shared list for Insults
        shared_censored_texts = manager.list() #Create a shared list for Censored texts

        # Create the service instance with the shared resources
        insults_service_instance = Insults(shared_insults_list, shared_censored_texts, processed_requests_counter)

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
        uri = daemon.register(insults_service_instance)
        try:
            ns.register("rabbit.counter", uri)
            print("Service registered with the name server as 'rabbit.counter'")
        except Pyro4.errors.NamingError as e:
            print(f"Error registering the service with the name server: {e}")
            exit(1)

        # --- Set up worker processes (RabbitMQ consumers/notifier) ---
        # Pass the service instance methods as targets for the processes
        # These processes will run concurrently with the Pyro daemon
        process_notify = Process(target=insults_service_instance.notify_subscribers)
        process_listen_insult = Process(target=insults_service_instance.listen)
        process_filter_service = Process(target=insults_service_instance.filter_service)

        # Start the worker processes
        process_notify.start()
        process_listen_insult.start()
        process_filter_service.start()

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
            process_notify.terminate()
            process_listen_insult.terminate()
            process_filter_service.terminate()
            process_notify.join()
            process_listen_insult.join()
            process_filter_service.join()
            print("Worker processes finished.")
            # Shutdown Pyro daemon
            print("Shutting down Pyro daemon...")
            daemon.shutdown()
            print("Pyro daemon shut down.")
            print("Exiting main program.")