import pika
import time
import threading

class Insults:
    def __init__(self):
        self.channel_insults = "Insults_channel"
        self.channel_broadcast = "Insults_broadcast"
        self.insults_set = set()  # Simulating a set
        self.censored_texts = []  # Simulating a list
        self.work_queue = "Work_queue"

        # RabbitMQ configuration
        self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=self.channel_insults)
        self.channel.queue_declare(queue=self.channel_broadcast)
        self.channel.queue_declare(queue=self.work_queue)

    def add_insult(self, insult):
        if insult not in self.insults_set:
            self.insults_set.add(insult)
            print(f"Insult added: {insult}")
        else:
            print(f"Insult already exists: {insult}")

    def get_insults(self):
        return f"Insult list: {list(self.insults_set)}"

    def get_results(self):
        return f"Censored texts: {self.censored_texts}"

    def insult_me(self):
        if self.insults_set:
            insult = next(iter(self.insults_set))
            print(f"Selected insult: {insult}")
            return insult
        return "The insult list is empty"

    def notify_subscribers(self):
        while True:
            insult = self.insult_me()
            if insult:
                self.channel.basic_publish(exchange='', routing_key=self.channel_broadcast, body=insult)
                print(f"\nNotified subscribers: {insult}")
            time.sleep(5)

    def listen(self):
        def callback(ch, method, properties, body):
            insult = body.decode('utf-8')
            print(f"Received insult: {insult}")
            self.add_insult(insult)

        self.channel.basic_consume(queue=self.channel_insults, on_message_callback=callback, auto_ack=True)
        print(f"Waiting for messages on {self.channel_insults}...")
        self.channel.start_consuming()

    def filter(self, text):
        censored_text = ""
        for word in text.split():
            if word.lower() in self.insults_set:
                censored_text += "CENSORED "
            else:
                censored_text += word + " "
        return censored_text

    def filter_service(self):
        def callback(ch, method, properties, body):
            text = body.decode('utf-8')
            filtered_text = self.filter(text)
            self.censored_texts.append(filtered_text)
            print(f"Censored text: {filtered_text}")

        self.channel.basic_consume(queue=self.work_queue, on_message_callback=callback, auto_ack=True)
        print(f"Waiting for texts to censor on {self.work_queue}...")
        self.channel.start_consuming()

insults = Insults()

thread1 = threading.Thread(target=insults.notify_subscribers)
thread2 = threading.Thread(target=insults.listen)
thread3 = threading.Thread(target=insults.filter_service)

thread1.start()
thread2.start()
thread3.start()

while True:
    try:
        print(insults.get_insults())
        print(insults.get_results())
        time.sleep(5)
    except KeyboardInterrupt:
        print("Exiting...")
        break