# insult_service.py
import pika
import time
import random
import os  # Afegit per si s'usa os.getpid()
import Pyro4
import config
from redis_manager import redis_cli
from multiprocessing import Process, Value, Lock  # Value i Lock potser ja no es necessiten tant aquí


# El comptador local 'insults_added_by_service_counter' ja no és tan rellevant
# si workers externs afegeixen insults a Redis.
# Les estadístiques globals vindran de Redis directament.

@Pyro4.expose
@Pyro4.behavior(instance_mode="session")
class InsultServicePyro:
    def __init__(self):
        print("InsultServicePyro instance created.")
        # El broadcaster es llança des de start_insult_service_components

    # El mètode add_insult ja no és necessari aquí si els clients publiquen a una cua
    # i els InsultProcessorWorkers fan la feina. Si es volgués mantenir una forma
    # de cridar-lo via Pyro per conveniència, hauria de publicar a la cua.
    # Per ara, el traiem per claredat del flux.
    # def add_insult(self, insult: str) -> str: ...

    def get_insults(self) -> list:
        """Gets all insults from Redis."""
        return redis_cli.get_all_insults()

    def get_service_stats(self) -> dict:
        """Returns statistics related to insults and broadcasting."""
        return {
            "insults_in_redis_total": len(redis_cli.get_all_insults()),
            "insults_processed_total_redis": redis_cli.r.get(config.REDIS_INSULTS_PROCESSED_COUNTER_KEY) or 0,
            "num_broadcaster_processes_configured": config.NUM_INSULT_NOTIFIERS
        }

    @staticmethod
    def _notify_subscribers_process(instance_id: int):
        # Aquest mètode es manté igual que a la resposta anterior
        print(f"[InsultService-Notifier-{instance_id}] Starting notifier process...")
        conn_params = pika.URLParameters(config.RABBITMQ_URL)

        while True:
            try:
                connection = pika.BlockingConnection(conn_params)
                channel = connection.channel()
                channel.exchange_declare(exchange=config.INSULTS_BROADCAST_EXCHANGE_NAME, exchange_type='fanout',
                                         durable=True)
                print(f"[InsultService-Notifier-{instance_id}] Connected to RabbitMQ for broadcasting.")

                while True:
                    all_insults = redis_cli.get_all_insults()
                    if all_insults:
                        insult_to_broadcast = random.choice(all_insults)
                        channel.basic_publish(exchange=config.INSULTS_BROADCAST_EXCHANGE_NAME,
                                              routing_key='',
                                              body=insult_to_broadcast,
                                              properties=pika.BasicProperties(delivery_mode=2))
                        # print(f"[InsultService-Notifier-{instance_id}] Broadcasted insult: {insult_to_broadcast}") # Log opcional, pot ser sorollós
                    time.sleep(5)
            except pika.exceptions.AMQPConnectionError as e:
                print(f"[InsultService-Notifier-{instance_id}] RabbitMQ connection error: {e}. Retrying in 5s...")
                time.sleep(5)
            except Exception as e:
                print(
                    f"[InsultService-Notifier-{instance_id}] Unexpected error: {e}. Restarting notifier logic in 5s...")
                time.sleep(5)


def start_insult_service_components():
    processes = []
    for i in range(config.NUM_INSULT_NOTIFIERS):
        notifier_process = Process(target=InsultServicePyro._notify_subscribers_process,
                                   args=(i,),
                                   daemon=True)
        processes.append(notifier_process)
        notifier_process.start()

    print(f"InsultService background component(s) started: {config.NUM_INSULT_NOTIFIERS} notifiers.")
    return processes