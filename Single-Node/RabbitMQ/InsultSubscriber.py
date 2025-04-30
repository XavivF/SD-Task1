import pika

class InsultSubscriber:
    def __init__(self):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        self.channel = self.connection.channel()
        self.channel.exchange_declare(exchange='Insults_broadcast', exchange_type='fanout')
        result = self.channel.queue_declare(queue='', exclusive=True)
        queue_name = result.method.queue
        self.queue_name = queue_name
        self.channel.queue_bind(exchange='Insults_broadcast', queue=queue_name)

    def listen(self):
        def callback(ch, method, properties, body):
            insult = body.decode('utf-8')
            print(f"Received insult: {insult}")

        self.channel.basic_consume(queue=self.queue_name, on_message_callback=callback, auto_ack=True)
        print("Waiting for insults...")
        self.channel.start_consuming()

if __name__ == "__main__":
    subscriber = InsultSubscriber()
    try:
        subscriber.listen()
    except KeyboardInterrupt:
        print("Process interrupted by user.")
        subscriber.connection.close()