import pika
import random
import time

class InsultClient:
    def __init__(self):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        self.channel = self.connection.channel()
        self.queue_name = "Work_queue"
        self.channel_insults = "Insults_channel"
        self.channel.queue_declare(queue=self.queue_name)
        self.channel.queue_declare(queue=self.channel_insults)

        self.insults = ["beneit", "capsigrany", "ganàpia", "nyicris",
                        "gamarús", "bocamoll", "murri", "dropo", "bleda", "xitxarel·lo"]

    def send_text(self):
        # Generate a text containing at least one insult
        insult = random.choice(self.insults)
        text = f"This is a text with an insult: {insult}"
        self.channel.basic_publish(exchange='', routing_key=self.queue_name, body=text)
        print(f"Sent to RabbitMQ: {text}")

    def send_insults(self):
        for insult in self.insults:
            self.channel.basic_publish(exchange='', routing_key=self.channel_insults, body=insult)
            print(f"New insult sent to service: {insult}")

    def start_sending(self, interval=5):
        try:
            while True:
                self.send_text()
                time.sleep(interval)
        except KeyboardInterrupt:
            print("Interrupted by user, stopping...")
            self.connection.close()

if __name__ == "__main__":
    client = InsultClient()
    client.send_insults()  # Send new insults
    client.start_sending()  # Send text with insults