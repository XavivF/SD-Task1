import pika
import time
import config
from redis_manager import redis_cli
from multiprocessing import Event


class InsultProcessorWorker:
    def __init__(self, worker_id: str, stop_event: Event):
        self.worker_id = worker_id
        self.stop_event = stop_event
        self.connection = None
        self.channel = None
        print(f"[InsultProcessorWorker {self.worker_id}] Initialized.")

    def connect_rabbitmq(self):
        try:
            self.connection = pika.BlockingConnection(pika.URLParameters(config.RABBITMQ_URL))
            self.channel = self.connection.channel()
            self.channel.queue_declare(queue=config.INSULTS_PROCESSING_QUEUE_NAME, durable=True)
            self.channel.basic_qos(prefetch_count=1)
            print(
                f"[InsultProcessorWorker {self.worker_id}] Connected to RabbitMQ, consuming from '{config.INSULTS_PROCESSING_QUEUE_NAME}'.")
        except pika.exceptions.AMQPConnectionError as e:
            print(f"[InsultProcessorWorker {self.worker_id}] Error connecting to RabbitMQ: {e}. Retrying in 5s...")
            time.sleep(5)
            self.connect_rabbitmq()  # Reintent

    def run(self):
        print(f"[InsultProcessorWorker {self.worker_id}] Starting...")
        self.connect_rabbitmq()
        if not self.channel:
            print(f"[InsultProcessorWorker {self.worker_id}] Cannot start without RabbitMQ channel. Exiting.")
            return

        while not self.stop_event.is_set():
            try:
                method_frame, properties, body = self.channel.basic_get(queue=config.INSULTS_PROCESSING_QUEUE_NAME,
                                                                    auto_ack=True)
                if method_frame:
                    insult_to_process = body.decode('utf-8')
                    redis_cli.add_insult(insult_to_process)
                    redis_cli.r.incr(config.REDIS_PROCESSED_COUNTER_KEY)
                else:
                    time.sleep(0.01)
            except pika.exceptions.StreamLostError:
                print(f"[InsultProcessorWorker {self.worker_id}] RabbitMQ connection lost. Reconnecting...")
                self.connect_rabbitmq()
            except Exception as e:
                print(f"[InsultProcessorWorker {self.worker_id}] Error during processing: {e}")
                if method_frame and self.channel and self.channel.is_open:
                    try:
                        self.channel.basic_nack(delivery_tag=method_frame.delivery_tag, requeue=True)
                    except Exception as ne:
                        print(f"[InsultProcessorWorker {self.worker_id}] Error NACKing message: {ne}")
                time.sleep(1)

        print(f"[InsultProcessorWorker {self.worker_id}] Stop event received. Shutting down.")
        if self.connection and self.connection.is_open:
            self.connection.close()
        print(f"[InsultProcessorWorker {self.worker_id}] Shutdown complete.")