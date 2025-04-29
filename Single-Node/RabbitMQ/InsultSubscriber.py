import pika

class InsultSubscriber:
    def __init__(self):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue='INSULTS')

    def listen(self):
        def callback(ch, method, properties, body):
            insult = body.decode('utf-8')
            print(f"Received insult: {insult}")

        self.channel.basic_consume(queue='INSULTS', on_message_callback=callback, auto_ack=True)
        print("Waiting for insults...")
        self.channel.start_consuming()