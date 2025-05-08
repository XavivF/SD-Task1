import argparse

import Pyro4
import pika
import random
import time
import multiprocessing

class InsultClient:
    def __init__(self, num_instances):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        self.channel = self.connection.channel()
        self.text_queue = "text_queue"
        self.insults_exchange = "insults_exchange"
        self.channel.exchange_declare(exchange=self.insults_exchange, exchange_type='fanout')
        self.channel.queue_declare(queue=self.text_queue)
        self.insult_service_proxies = []
        self.insult_filter_proxies = []
        for j in range(1, num_instances+1):
            try:
                service_proxy = Pyro4.Proxy(f"PYRONAME:rabbit.service.{j}")
                self.insult_service_proxies.append(service_proxy)
                print(f"Connected to Pyro service instance: rabbit.service.{j}")
            except Pyro4.errors.NamingError:
                print(f"Warning: Pyro service instance 'rabbit.service.{j}' not found.")
            except Exception as e:
                print(f"Error connecting to Pyro service instance 'rabbit.service.{j}': {e}")

            try:
                filter_proxy = Pyro4.Proxy(f"PYRONAME:rabbit.filter.{j}")
                self.insult_filter_proxies.append(filter_proxy)
                print(f"Connected to Pyro filter instance: rabbit.filter.{j}")
            except Pyro4.errors.NamingError:
                print(f"Warning: Pyro filter instance 'rabbit.filter.{j}' not found.")
            except Exception as e:
                print(f"Error connecting to Pyro filter instance 'rabbit.filter.{j}': {e}")

        if not self.insult_service_proxies and not self.insult_filter_proxies:
            print("Error: No Pyro service or filter instances found. Make sure they are running and registered.")

        self.insults = ["beneit", "capsigrany", "ganàpia", "nyicris",
                        "gamarús", "bocamoll", "murri", "dropo", "bleda", "xitxarel·lo"]
        self.llista_insults = [
            "Ets un beneit de cap a peus.",
            "No siguis capsigrany i pensa abans de parlar.",
            "Aquest ganàpia no sap el que fa.",
            "Sempre estàs tan nyicris que no pots ni aixecar una cadira.",
            "Quin gamarús ! ha tornat a fer el mateix error.",
            "No siguis bocamoll i guarda el secret.",
            "És un murri ... sempre s’escapa de tot.",
            "No siguis dropo i posa't a treballar.",
            "Ets una mica bleda i espavila una mica.",
            "Aquest xitxarel·lo es pensa que ho sap tot."
        ]

    def send_text(self):
        while True:
            text = random.choice(self.llista_insults)
            self.channel.basic_publish(exchange='', routing_key=self.text_queue, body=text)
            print(f"Sent to RabbitMQ: {text}")
            time.sleep(5)

    def send_insults(self):
        for insult in self.insults:
            self.channel.basic_publish(exchange=self.insults_exchange, routing_key='', body=insult)
            print(f"New insult sent to both services: {insult}")

    def start_sending(self):
        try:
            while True:
                self.send_text()
                time.sleep(5)
        except KeyboardInterrupt:
            print("Interrupted by user, stopping...")
            self.connection.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--num-instances", type=int, default=1, help="Number of instances running", required=True)
    args = parser.parse_args()
    client = InsultClient(args.num_instances)
    client.send_insults()  # Send new insults
    time.sleep(1)

    process_send_text = multiprocessing.Process(target=client.start_sending)

    process_send_text.start()

    try:
        print(
            "Press K to stop the services, press I to read the current insult list or press T to read the texts received")
        while True:
            t = input()
            if t == "I":
                try:
                    for i in range(args.num_instances):
                        print(f"Insult list from instance {i+1}:",
                              client.insult_service_proxies[i].get_insults())
                except Pyro4.errors.CommunicationError as e:
                    print(f"Communication error: {e}.")
            elif t == "T":
                try:
                    for i in range(args.num_instances):
                        print(f"Insult filter censored texts from instance {i+1}:",
                              client.insult_filter_proxies[i].get_results())
                except Pyro4.errors.CommunicationError as e:
                    print(f"Communication error: {e}.")
            elif t == "K":
                print("Stopping services...")
                process_send_text.terminate()
                process_send_text.join()
                break
            else:
                print("Unknown command.")
    except KeyboardInterrupt:
        print("Interrupted by user, stopping...")
        process_send_text.terminate()
        process_send_text.join()