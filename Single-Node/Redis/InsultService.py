import redis
import random
import time
import threading
# Connect to Redis
client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

class Insults:
    def __init__(self):
        self.results = []
        self.channel_insults = "Insults_channel"
        self.channel_broadcast = "Insults_broadcast"
        self.insultList = "INSULTS"

    def add_insult(self, insult):
        current_insults = client.smembers(self.insultList)
        if insult not in current_insults:
            client.sadd(self.insultList, insult)
            print(f"Insult added: {insult}")
            return f"Insult added: {insult}"
        else:
            print(f"Insult already exists")
            return f"Insult already exists"

    def get_insults(self):
        insult = client.smembers(self.insultList)
        return f"Insult list: {insult}"

    def insult_me(self):
        if client.scard(self.insultList) != 0:
            insult = client.srandmember(self.insultList)
            print(f"Insult escollit: {insult}")
            return insult

    def delete_all(self):
        while client.scard(self.insultList) > 0:
            client.srem(self.insultList)
        print(self.get_insults())
        print("List deleted")

    def notify_subscribers(self):
        while True:
            insult = insults.insult_me()
            if insult:
                client.publish(self.channel_broadcast, insult)
                print("Notified subscribers.")
            time.sleep(5)

    def listen(self):
        while True:
            for message in pubsub.listen():
                print(f"Process message {message['data']}")
                if message['type'] == 'message':
                    insult = message['data']
                    print(f"Received insult: {insult}")
                    self.add_insult(insult)

insults = Insults()
pubsub = client.pubsub()
pubsub.subscribe(insults.channel_insults)

insults.delete_all()

#thread1 = threading.Thread(target=insults.notify_subscribers)
thread2 = threading.Thread(target=insults.listen)

#thread1.start()
thread2.start()

while True:
    print(insults.get_insults())
    time.sleep(5)