import pika
import config
import time


class InsultSubscriber:
    def __init__(self):
        self.connection = None
        self.channel = None
        print("InsultSubscriber initialized.")

    def connect_rabbitmq(self):
        while True:
            try:
                self.connection = pika.BlockingConnection(pika.URLParameters(config.RABBITMQ_URL))
                self.channel = self.connection.channel()
                self.channel.exchange_declare(exchange=config.INSULTS_BROADCAST_EXCHANGE_NAME, exchange_type='fanout')

                # Declara una cua exclusiva i temporal per aquest subscriptor
                result = self.channel.queue_declare(queue='', exclusive=True, durable=True)
                self.queue_name = result.method.queue

                self.channel.queue_bind(exchange=config.INSULTS_BROADCAST_EXCHANGE_NAME, queue=self.queue_name)
                print(
                    f"InsultSubscriber: Connected to RabbitMQ, listening on queue '{self.queue_name}' for exchange '{config.INSULTS_BROADCAST_EXCHANGE_NAME}'.")
                return  # Connexió exitosa
            except pika.exceptions.AMQPConnectionError as e:
                print(f"InsultSubscriber: RabbitMQ connection error: {e}. Retrying in 5 seconds...")
                time.sleep(5)

    def listen(self):
        self.connect_rabbitmq()

        def callback(ch, method, properties, body):
            insult = body.decode('utf-8')
            print(f"InsultSubscriber: Received insult: {insult}")

        self.channel.basic_consume(queue=self.queue_name, on_message_callback=callback, auto_ack=True)

        print("InsultSubscriber: Waiting for insults. Press Ctrl+C to stop.")
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            print("InsultSubscriber: Process interrupted by user.")
        except pika.exceptions.ConnectionClosedByBroker:
            print("InsultSubscriber: Connection closed by broker. Attempting to reconnect...")
            self.listen()  # Torna a intentar connectar i escoltar
        except pika.exceptions as e:
            print(f"InsultSubscriber: Caught an error: {e}. Reconnecting...")
            self.listen()
        finally:
            if self.connection and self.connection.is_open:
                self.connection.close()
            print("InsultSubscriber: Stopped.")


if __name__ == "__main__":
    subscriber = InsultSubscriber()
    subscriber.listen()