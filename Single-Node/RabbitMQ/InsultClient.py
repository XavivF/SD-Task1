import pika
import random
import time

class InsultClient:
    def __init__(self):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        self.channel = self.connection.channel()
        self.work_queue = "Work_queue"
        self.insults_queue = "Insults_channel"
        self.channel.queue_declare(queue=self.work_queue)
        self.channel.queue_declare(queue=self.insults_queue)

        self.insults = ["beneit", "capsigrany", "ganàpia", "nyicris",
                        "gamarús", "bocamoll", "murri", "dropo", "bleda", "xitxarel·lo"]
        self.llista_insults = [
            "Ets un beneit de cap a peus.",
            "No siguis capsigrany i pensa abans de parlar.",
            "Aquest ganàpia no sap el que fa.",
            "Sempre estàs tan nyicris que no pots ni aixecar una cadira.",
            "Quin gamarús ! ha tornat a fer el mateix error.",
            "No siguis bocamoll i guarda el secret.",
            "És un murri ... sempre s’escapa de tot.",
            "No siguis dropo i posa't a treballar.",
            "Ets una mica bleda i espavila una mica.",
            "Aquest xitxarel·lo es pensa que ho sap tot."
        ]

    def send_text(self):
        text = random.choice(self.llista_insults)
        self.channel.basic_publish(exchange='', routing_key=self.work_queue, body=text)
        print(f"Sent to RabbitMQ: {text}")

    def send_insults(self):
        for insult in self.insults:
            self.channel.basic_publish(exchange='', routing_key=self.insults_queue, body=insult)
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
    time.sleep(1)
    client.start_sending()  # Send text with insults