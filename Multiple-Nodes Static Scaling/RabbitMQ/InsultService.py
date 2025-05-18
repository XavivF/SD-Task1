import argparse
import Pyro4
import pika
import time
import random
from multiprocessing import Process, Manager
import redis

class Insults:
    def __init__(self, shared_insults_list):
        self.channel_broadcast = "Insults_broadcast"
        self.add_insult_queue = "add_insult_queue"  # Define the work queue name
        self.insults_list = shared_insults_list  # Is a shared list
        self.counter_key = "COUNTER"  # Key for Redis counter
        self.client = redis.Redis(db=0, decode_responses=True)

    def add_insult(self, insult):
        self.client.incr(self.counter_key)
        if insult not in self.insults_list:
            self.insults_list.append(insult)
        # print(f"Insult added: {insult}")

    def get_insults(self):
        return f"Insult list: {list(self.insults_list)}"

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
        try:
            while True:
                if self.insults_list:
                    insult = self.insult_me()
                    if insult is not None:
                        print(f"Sending insult to subscribers: {insult}")
                        channel.basic_publish(exchange=self.channel_broadcast, routing_key='', body=insult)
                time.sleep(5)
        except KeyboardInterrupt:
            print("Stopping the broadcast process...")

    def listen_insults(self):
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        channel = connection.channel()

        channel.queue_declare(queue=self.add_insult_queue)
        channel.basic_qos(prefetch_count=1)

        def callback(ch, method, properties, body):
            insult = body.decode('utf-8')
            # print(f"Received insult: {insult}")
            self.add_insult(insult)

        channel.basic_consume(queue=self.add_insult_queue, on_message_callback=callback, auto_ack=True)
        # print(f"Waiting for messages at {self.channel_insults}...")
        channel.start_consuming()

    def get_processed_count(self):
        count = self.client.get(self.counter_key)
        return int(count) if count else 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-id", "--instance-id", type=int, default=1, help="Service instance ID", required=True)
    args = parser.parse_args()

    manager = Manager()
    # Create a shared list for insults
    shared_insults = manager.list()
    # Create the service instance with the shared resources
    insults_service_instance = Insults(shared_insults)

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
        ns.register(f"rabbit.service.{args.instance_id}", uri)
        print(f"Service registered with the name server as 'rabbit.service.{args.instance_id}'")
    except Pyro4.errors.NamingError as e:
        print(f"Error registering the service with the name server: {e}")
        exit(1)


    print("InsultService: Clearing initial Redis keys (INSULTS_COUNTER)...")
    insults_service_instance.client.delete(insults_service_instance.counter_key)
    print("Redis keys cleared.")

    # --- Set up worker processes (RabbitMQ consumers/notifier) ---
    # Pass the service instance methods as targets for the processes
    process_listen_insults = Process(target=insults_service_instance.listen_insults)
    process_notify_subscribers = Process(target=insults_service_instance.notify_subscribers)

    # Start the worker processes
    process_listen_insults.start()
    process_notify_subscribers.start()

    try:
        daemon.requestLoop()
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        print("Terminating worker processes...")
        process_listen_insults.terminate()
        process_listen_insults.join()
        process_notify_subscribers.terminate()
        process_notify_subscribers.join()
        daemon.shutdown()
        print("Worker processes finished.")
        print("Exiting main program.")