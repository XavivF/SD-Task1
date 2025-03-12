import pika
import time
import random

# Send multiple messages
insults = ["Cap de melo", "Olaaa caracola", "Adeuu", "1234", "Beneit",
        "Capsigrany", "Ganàpia", "Nyicris", "Gamarús",
        "Tros de quòniam", "Poca-solta",
        "Bocamoll", "Tocat del bolet"]

def get_insult():
    return insults[random.randint(0, len(insults) - 1)]

def main():
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    channel.queue_declare(queue='INSULTS')

    try:
        while True:
            insult = get_insult()
            channel.basic_publish(exchange='', routing_key='INSULTS', body=insult)
            print(f" [x] Sent '{insult}'")
            time.sleep(5)
    except KeyboardInterrupt:
        print("\nInsultProducer stopped.")
    finally:
        connection.close()

if __name__ == "__main__":
    main()

