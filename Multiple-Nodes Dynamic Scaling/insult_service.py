import pika
import time
import random
import Pyro4
import config
from redis_manager import redis_cli
from multiprocessing import Process

@Pyro4.expose
@Pyro4.behavior(instance_mode="session")
class InsultServicePyro:
    def __init__(self):
        print("InsultServicePyro instance created.")


    def get_insults(self) -> list:
        """Gets all insults from Redis."""
        return redis_cli.get_all_insults()

    def get_service_stats(self) -> dict:
        """Returns statistics related to insults and broadcasting."""
        return {
            "insults_in_redis_total": len(redis_cli.get_all_insults()),
            "insults_processed_total_redis": redis_cli.r.get(config.REDIS_PROCESSED_COUNTER_KEY) or 0,
            "num_broadcaster_processes_configured": config.NUM_INSULT_NOTIFIERS
        }

    @staticmethod
    def notify_subscribers_process(instance_id: int):
        print(f"[InsultService-Notifier-{instance_id}] Starting notifier process...")
        conn_params = pika.URLParameters(config.RABBITMQ_URL)

        while True:
            try:
                connection = pika.BlockingConnection(conn_params)
                channel = connection.channel()
                channel.exchange_declare(exchange=config.INSULTS_BROADCAST_EXCHANGE_NAME, exchange_type='fanout')
                print(f"[InsultService-Notifier-{instance_id}] Connected to RabbitMQ for broadcasting.")

                while True:
                    all_insults = redis_cli.get_all_insults()
                    if all_insults:
                        insult_to_broadcast = random.choice(all_insults)
                        channel.basic_publish(exchange=config.INSULTS_BROADCAST_EXCHANGE_NAME,
                                              routing_key='',
                                              body=insult_to_broadcast,
                                              properties=pika.BasicProperties(delivery_mode=2))
                    time.sleep(5)
            except pika.exceptions.AMQPConnectionError as e:
                print(f"[InsultService-Notifier-{instance_id}] RabbitMQ connection error: {e}. Retrying in 5s...")
                time.sleep(5)
            except Exception as e:
                print(f"[InsultService-Notifier-{instance_id}] Unexpected error: {e}. Restarting notifier logic in 5s...")
                time.sleep(5)


def start_insult_service_components():
    processes = []
    for i in range(config.NUM_INSULT_NOTIFIERS):
        notifier_process = Process(target=InsultServicePyro.notify_subscribers_process,
                                   args=(i,),
                                   daemon=True)
        processes.append(notifier_process)
        notifier_process.start()

    print(f"InsultService background component(s) started: {config.NUM_INSULT_NOTIFIERS} notifiers.")
    return processes