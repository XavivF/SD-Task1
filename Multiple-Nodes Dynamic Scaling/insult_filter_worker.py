import pika
import time
import config
from redis_manager import redis_cli  # Usarem la instància singleton
from multiprocessing import Event


class InsultFilterWorker:
    def __init__(self, worker_id: str, stop_event: Event):
        self.worker_id = worker_id
        self.stop_event = stop_event
        self.connection = None
        self.channel = None
        self.insults = ["tonto", "lleig", "boig", "idiota", "estúpid", "inútil", "desastre", "fracassat", "covard", "mentider",
                        "beneit", "capsigrany", "ganàpia", "nyicris", "gamarús", "bocamoll", "murri", "dropo", "bleda", "xitxarel·lo"]
        print(f"[Worker {self.worker_id}] Initialized.")

    def connect_rabbitmq(self):
        try:
            self.connection = pika.BlockingConnection(pika.URLParameters(config.RABBITMQ_URL))
            self.channel = self.connection.channel()
            self.channel.queue_declare(queue=config.TEXT_QUEUE_NAME, durable=True)
            self.channel.exchange_declare(exchange=config.INSULTS_EXCHANGE_NAME, exchange_type='fanout')
            self.channel.basic_qos(prefetch_count=1)
            print(f"[Worker {self.worker_id}] Connected to RabbitMQ.")
        except pika.exceptions.AMQPConnectionError as e:
            print(f"[Worker {self.worker_id}] Error connecting to RabbitMQ: {e}. Retrying in 5s...")
            time.sleep(5)
            self.connect_rabbitmq()  # Retry

    def filter_text(self, text: str) -> str:
        current_insults = self.insults

        words = text.split()
        censored_words = []
        for word in words:
            if word in current_insults:
                censored_words.append("CENSORED")
            else:
                censored_words.append(word)
        return " ".join(censored_words)

    def run(self):
        # print(f"[Worker {self.worker_id}] Starting...")
        self.connect_rabbitmq()
        if not self.channel:
            # print(f"[Worker {self.worker_id}] Cannot start without RabbitMQ channel. Exiting.")
            return

        while not self.stop_event.is_set():
            try:
                method_frame, properties, body = self.channel.basic_get(queue=config.TEXT_QUEUE_NAME, auto_ack=True)
                if method_frame:
                    text_to_filter = body.decode('utf-8')
                    censored_text = self.filter_text(text_to_filter)
                    redis_cli.add_censored_text(censored_text)
                    redis_cli.increment_processed_count()
                else:
                    time.sleep(0.01)
            except pika.exceptions.StreamLostError:
                print(f"[Worker {self.worker_id}] RabbitMQ connection lost. Reconnecting...")
                self.connect_rabbitmq()
            except Exception as e:
                print(f"[Worker {self.worker_id}] Error during processing: {e}")
                if method_frame and self.channel and self.channel.is_open:  # type: ignore
                    try:
                        self.channel.basic_nack(delivery_tag=method_frame.delivery_tag, requeue=True)  # Requeue or not
                    except Exception as ne:
                        print(f"[Worker {self.worker_id}] Error NACKing message: {ne}")
                time.sleep(1)  # Wait a bit before retrying or next loop

        # print(f"[Worker {self.worker_id}] Stop event received. Shutting down.")
        if self.connection and self.connection.is_open:
            self.connection.close()
        # print(f"[Worker {self.worker_id}] Shutdown complete.")


# Per provar el worker individualment (opcional)
if __name__ == '__main__':
    print("Running InsultFilterWorker in standalone mode for testing.")

    test_stop_event = Event()
    worker = InsultFilterWorker(worker_id="test_worker_0", stop_event=test_stop_event)
    try:
        worker.run()
    except KeyboardInterrupt:
        print("Standalone worker interrupted.")
        test_stop_event.set()
    print("Standalone worker finished.")