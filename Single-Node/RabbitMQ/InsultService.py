import pika
import time
import random
from multiprocessing import Process, Manager

class Insults:
    def __init__(self, shared_insults, sh_censored_texts):
        self.channel_insults = "Insults_channel"
        self.channel_broadcast = "Insults_broadcast"
        self.insults_list = shared_insults  # Is a shared list
        self.censored_texts = sh_censored_texts
        self.work_queue = "Work_queue"

    def add_insult(self, insult):
        if insult not in self.insults_list:
            self.insults_list.append(insult)
            print(f"Insult added: {insult}")
        else:
            print(f"This insult already exists: {insult}")

    def get_insults(self):
        return f"Insult list: {list(self.insults_list)}"

    def get_results(self):
        return f"Censored texts: {self.censored_texts}"

    def insult_me(self):
        if self.insults_list:
            insult = random.choice(self.insults_list)
            print(f"Chosen insult: {insult}")
            return insult
        return None

    def notify_subscribers(self):
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        channel = connection.channel()
        channel.queue_declare(queue=self.channel_broadcast)

        while True:
            if self.insults_list:
                insult = self.insult_me()
                if insult is not None:
                    print(f"Sending insult to subscribers: {insult}")
                    channel.basic_publish(exchange='', routing_key=self.channel_broadcast, body=insult)
                    print(f"\nNotified subscribers : {insult}")
            time.sleep(5)

    def listen(self):
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        channel = connection.channel()
        channel.queue_declare(queue=self.channel_insults)

        def callback(ch, method, properties, body):
            insult = body.decode('utf-8')
            print(f"Received insult: {insult}")
            self.add_insult(insult)

        channel.basic_consume(queue=self.channel_insults, on_message_callback=callback, auto_ack=True)
        print(f"Waiting for messages at {self.channel_insults}...")
        channel.start_consuming()

    def filter(self, text):
        censored_text = ""
        for word in text.split():
            if word.lower() in self.insults_list:
                censored_text += "CENSORED "
            else:
                censored_text += word + " "
        return censored_text

    def filter_service(self):
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        channel = connection.channel()
        channel.queue_declare(queue=self.work_queue)

        def callback(ch, method, properties, body):
            text = body.decode('utf-8')
            filtered_text = self.filter(text)
            if filtered_text not in self.censored_texts:
                self.censored_texts.append(filtered_text)
            print(f"Censored text: {filtered_text}")

        channel.basic_consume(queue=self.work_queue, on_message_callback=callback, auto_ack=True)
        print(f"Waiting for texts to censor at {self.work_queue}...")
        channel.start_consuming()

if __name__ == "__main__":
    with Manager() as manager:
        shared_insults_list = manager.list()  # Crate a shared list
        shared_censored_texts = manager.list()
        insults = Insults(shared_insults_list, shared_censored_texts)

        process1 = Process(target=insults.notify_subscribers)
        process2 = Process(target=insults.listen)
        process3 = Process(target=insults.filter_service)

        process1.start()
        process2.start()
        process3.start()

        try:
            while True:
                print(insults.get_insults())
                print(insults.get_results())
                time.sleep(5)
        except KeyboardInterrupt:
            print("Exiting...")
            process1.terminate()
            process2.terminate()
            process3.terminate()
            process1.join()
            process2.join()
            process3.join()