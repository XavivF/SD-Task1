import argparse
import random
import time
from multiprocessing import Event, Process
import Pyro4
import pika
import config


class InsultClientDynamic:
    def __init__(self):
        self.pyro_ns = None
        try:
            self.pyro_ns = Pyro4.locateNS(host=config.PYRO_NS_HOST, port=config.PYRO_NS_PORT)
        except Pyro4.errors.NamingError:
            print(
                f"Client: Pyro Name Server not found at {config.PYRO_NS_HOST}:{config.PYRO_NS_PORT}. Some functions might fail.")

        self.insult_service_proxy = None
        self.scaler_manager_proxy = None

        if self.pyro_ns:
            try:
                insult_service_uri = self.pyro_ns.lookup(config.PYRO_INSULT_SERVICE_NAME)
                self.insult_service_proxy = Pyro4.Proxy(insult_service_uri)
                print(f"Client: Connected to InsultService at {insult_service_uri}")
            except Pyro4.errors.NamingError:
                print(f"Client: InsultService '{config.PYRO_INSULT_SERVICE_NAME}' not found in Pyro NS.")

            try:
                scaler_manager_uri = self.pyro_ns.lookup(config.PYRO_SCALER_MANAGER_NAME)
                self.scaler_manager_proxy = Pyro4.Proxy(scaler_manager_uri)
                print(f"Client: Connected to ScalerManager at {scaler_manager_uri}")
            except Pyro4.errors.NamingError:
                print(f"Client: ScalerManager '{config.PYRO_SCALER_MANAGER_NAME}' not found in Pyro NS.")

        self.rabbit_connection = None
        self.rabbit_channel = None
        self._connect_rabbitmq()
        self.insults_samples = ["beneit", "capsigrany", "ganàpia", "nyicris", "gamarús", "bocamoll", "murri", "dropo",
                                "bleda", "xitxarel·lo"]
        self.texts_samples = [
            "Ets un beneit de cap a peus.", "No siguis capsigrany i pensa abans de parlar.",
            "Aquest ganàpia no sap el que fa.", "Sempre estàs tan nyicris que no pots ni aixecar una cadira.",
            "Quin gamarús! Ha tornat a fer el mateix error.", "No siguis bocamoll i guarda el secret.",
            "És un murri... sempre s’escapa de tot.", "No siguis dropo i posa't a treballar.",
            "Ets una mica bleda i espavila una mica.", "Aquest xitxarel·lo es pensa que ho sap tot.",
            "Aquest text no te cap insult.", "M'agrada la xocolata."
        ]

    def _connect_rabbitmq(self):
        try:
            self.rabbit_connection = pika.BlockingConnection(pika.URLParameters(config.RABBITMQ_URL))
            self.rabbit_channel = self.rabbit_connection.channel()
            self.rabbit_channel.queue_declare(queue=config.TEXT_QUEUE_NAME, durable=True)
            self.rabbit_channel.queue_declare(queue=config.INSULTS_PROCESSING_QUEUE_NAME, durable=True)
            print("Client: Connected to RabbitMQ and declared queues.")
        except pika.exceptions.AMQPConnectionError as e:
            print(f"Client: Error connecting to RabbitMQ: {e}")
            self.rabbit_channel = None

    def send_text_to_filter(self, text: str):
        if not self.rabbit_channel or self.rabbit_channel.is_closed:  # type: ignore
            print("Client: RabbitMQ channel not available for text. Attempting to reconnect...")
            self._connect_rabbitmq()
            if not self.rabbit_channel:
                print("Client: Reconnect failed. Cannot send text.")
                return
        try:
            self.rabbit_channel.basic_publish(  # type: ignore
                exchange='',
                routing_key=config.TEXT_QUEUE_NAME,
                body=text,
                properties=pika.BasicProperties(delivery_mode=2)
            )
        except pika.exceptions.AMQPConnectionError as e:
            print(f"Client: Error sending text to RabbitMQ: {e}")

    def publish_new_insult_to_queue(self, insult: str):
        if not self.rabbit_channel or self.rabbit_channel.is_closed:  # type: ignore
            print("Client: RabbitMQ channel not available for insult. Attempting to reconnect...")
            self._connect_rabbitmq()
            if not self.rabbit_channel:
                print("Client: Reconnect failed. Cannot publish insult.")
                return

        try:
            self.rabbit_channel.basic_publish(
                exchange='',
                routing_key=config.INSULTS_PROCESSING_QUEUE_NAME,
                body=insult
            )
            print(f"Client: Published new insult to queue '{config.INSULTS_PROCESSING_QUEUE_NAME}': '{insult}'")
        except pika.exceptions.AMQPConnectionError as e:
            print(f"Client: Error publishing insult to RabbitMQ queue: {e}")

    def get_all_insults_from_service(self):
        if self.insult_service_proxy:
            try:
                return self.insult_service_proxy.get_insults()
            except Exception as e:
                print(f"Client: Error calling InsultService.get_insults(): {e}")
        else:
            print("Client: InsultService proxy not available.")
        return []

    def get_scaler_stats(self):
        if self.scaler_manager_proxy:
            try:
                return self.scaler_manager_proxy.get_scaler_stats()
            except Exception as e:
                print(f"Client: Error calling ScalerManager.get_scaler_stats(): {e}")
        else:
            print("Client: ScalerManager proxy not available.")
        return {}

    def get_censored_texts_sample_from_scaler(self, count=5):
        if self.scaler_manager_proxy:
            try:
                return self.scaler_manager_proxy.get_censored_texts_sample(count)
            except Exception as e:
                print(f"Client: Error calling ScalerManager.get_censored_texts_sample(): {e}")
        else:
            print("Client: ScalerManager proxy not available.")
        return []

    def close_rabbitmq_connection(self):
        if self.rabbit_connection and self.rabbit_connection.is_open:
            self.rabbit_connection.close()
            print("Client: RabbitMQ connection closed.")


def continuous_text_and_insult_sender(dynamic_client: InsultClientDynamic, stop_event):
    """ Envia textos i insults aleatoris contínuament """
    text_counter = 0
    insult_counter = 0
    while not stop_event.is_set():
        # Envia un text
        text = random.choice(dynamic_client.texts_samples)
        dynamic_client.send_text_to_filter(text)
        text_counter += 1

        if text_counter % 5 == 0:
            insult = random.choice(dynamic_client.insults_samples) + "_" + str(random.randint(100, 999))  # Per fer-los únics
            dynamic_client.publish_new_insult_to_queue(insult)
            insult_counter += 1

        sleep_time = random.uniform(0.05, 0.5)

        start_sleep = time.time()
        while time.time() - start_sleep < sleep_time:
            if stop_event.is_set():
                break
            time.sleep(0.05)
    print(f"Sender process stopped. Sent {text_counter} texts and {insult_counter} insults.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dynamic Scaling Insult Client")
    parser.add_argument("--send-continuous", action="store_true", help="Continuously send texts and insults.")
    parser.add_argument("--add-insult", type=str, help="Add a new insult to the processing queue.")
    parser.add_argument("--num-texts", type=int, default=10, help="Number of random texts to send if not continuous.")
    parser.add_argument("--num-insults", type=int, default=2,
                        help="Number of random insults to send if not continuous.")

    parser.add_argument("--get-insults", action="store_true", help="Get all insults from InsultService (Redis).")
    parser.add_argument("--get-scaler-stats", action="store_true", help="Get stats from ScalerManager.")
    parser.add_argument("--get-censored-sample", action="store_true",
                        help="Get a sample of censored texts.")  # Assegura que ScalerManager té aquest mètode
    args = parser.parse_args()

    client = InsultClientDynamic()
    sender_process = None
    stop_sender_event = None

    try:
        if args.send_continuous:
            stop_sender_event = Event()
            sender_process = Process(target=continuous_text_and_insult_sender, args=(client, stop_sender_event),
                                     daemon=True)
            sender_process.start()
            print("Continuous text and insult sender started. Press Ctrl+C to stop client and sender.")
            while True: time.sleep(1)

        elif args.add_insult:
            client.publish_new_insult_to_queue(args.add_insult)

        elif args.get_insults:
            insults = client.get_all_insults_from_service()
            print("Current insults from InsultService (via Redis):", insults)

        elif args.get_scaler_stats:
            stats = client.get_scaler_stats()
            print("ScalerManager Stats:")
            if stats:
                for pool_name, pool_stats in stats.items():
                    if isinstance(pool_stats, dict):
                        print(f"  Pool: {pool_name}")
                        for key, value in pool_stats.items():
                            print(f"    {key}: {value}")
                    else:
                        print(f"  {pool_name}: {pool_stats}")
            else:
                print("  No stats received.")


        elif args.get_censored_sample:
            # Assegura't que ScalerManager te un mètode exposat com:
            # @Pyro4.expose
            # def get_censored_texts_sample(self, count=10):
            #     return redis_cli.get_censored_texts(0, count -1)
            # Afegeix-lo si no hi és. Ja estava a la versió anterior de ScalerManager.
            sample = client.get_censored_texts_sample_from_scaler()
            print("Censored Texts Sample:", sample)

        else:
            print(f"Sending {args.num_texts} texts and {args.num_insults} insults...")
            for _ in range(args.num_texts):
                client.send_text_to_filter(random.choice(client.texts_samples))
                time.sleep(random.uniform(0.05, 0.2))
            for _ in range(args.num_insults):
                client.publish_new_insult_to_queue(
                    random.choice(client.insults_samples) + "_" + str(random.randint(1000, 9999)))
                time.sleep(random.uniform(0.05, 0.2))
            print("Texts and insults sent.")

            if client.scaler_manager_proxy:
                time.sleep(2)
                stats = client.get_scaler_stats()
                print("\nScalerManager Stats after sending:")
                if stats:
                    for pool_name, pool_stats in stats.items():
                        if isinstance(pool_stats, dict):
                            print(f"  Pool: {pool_name}")
                            for key, value in pool_stats.items():
                                print(f"    {key}: {value}")
                        else:
                            print(f"  {pool_name}: {pool_stats}")
                else:
                    print("  No stats received.")

    except KeyboardInterrupt:
        print("\nClient interrupted by user.")
    finally:
        if sender_process and stop_sender_event:
            print("Stopping continuous sender...")
            stop_sender_event.set()  # type: ignore
            sender_process.join(timeout=5)
            if sender_process.is_alive():
                sender_process.terminate()
        client.close_rabbitmq_connection()
        print("Client finished.")