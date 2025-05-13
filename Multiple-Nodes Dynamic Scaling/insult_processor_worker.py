# insult_processor_worker.py
import pika
import time
import os
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

    def _connect_rabbitmq(self):
        try:
            self.connection = pika.BlockingConnection(pika.URLParameters(config.RABBITMQ_URL))
            self.channel = self.connection.channel()
            # Declara la cua de la qual consumirà
            self.channel.queue_declare(queue=config.INSULTS_PROCESSING_QUEUE_NAME, durable=True)
            self.channel.basic_qos(prefetch_count=1)  # Processa un missatge a la vegada
            print(
                f"[InsultProcessorWorker {self.worker_id}] Connected to RabbitMQ, consuming from '{config.INSULTS_PROCESSING_QUEUE_NAME}'.")
        except pika.exceptions.AMQPConnectionError as e:
            print(f"[InsultProcessorWorker {self.worker_id}] Error connecting to RabbitMQ: {e}. Retrying in 5s...")
            time.sleep(5)
            self._connect_rabbitmq()  # Reintent

    def run(self):
        print(f"[InsultProcessorWorker {self.worker_id}] Starting...")
        self._connect_rabbitmq()
        if not self.channel:
            print(f"[InsultProcessorWorker {self.worker_id}] Cannot start without RabbitMQ channel. Exiting.")
            return

        while not self.stop_event.is_set():
            try:
                method_frame, properties, body = self.channel.basic_get(queue=config.INSULTS_PROCESSING_QUEUE_NAME,
                                                                        auto_ack=False)
                if method_frame:
                    insult_to_process = body.decode('utf-8')
                    print(f"[InsultProcessorWorker {self.worker_id}] Received insult to process: '{insult_to_process}'")

                    added = redis_cli.add_insult(insult_to_process)
                    if added:
                        print(f"[InsultProcessorWorker {self.worker_id}] Insult '{insult_to_process}' added to Redis.")
                    else:
                        print(
                            f"[InsultProcessorWorker {self.worker_id}] Insult '{insult_to_process}' already in Redis.")

                    redis_cli.r.incr(config.REDIS_INSULTS_PROCESSED_COUNTER_KEY)  # Incrementa comptador global

                    self.channel.basic_ack(delivery_tag=method_frame.delivery_tag)
                else:
                    time.sleep(0.1)  # Espera si no hi ha missatges
            except pika.exceptions.StreamLostError:
                print(f"[InsultProcessorWorker {self.worker_id}] RabbitMQ connection lost. Reconnecting...")
                self._connect_rabbitmq()
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