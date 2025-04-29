import redis
import time
import threading

# Connect to Redis
client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

class Insults:
    def __init__(self):
        self.channel_insults = "Insults_channel"
        self.channel_broadcast = "Insults_broadcast"
        self.insultSet = "INSULTS"
        self.censoredTextsList = "RESULTS"
        self.workQueue = "Work_queue"

    def add_insult(self, insult):
        client.sadd(self.insultSet, insult)
        print(f"Insult added: {insult}")
        return f"Insult added: {insult}"

    def get_insults(self):
        insult = client.smembers(self.insultSet)
        return f"Insult list: {insult}"

    def get_results(self):
        results = client.lrange(self.censoredTextsList, 0, -1)
        return f"Textos censorats:{results}"

    def insult_me(self):
        if client.scard(self.insultSet) != 0:
            insult = client.srandmember(self.insultSet)
            print(f"Insult escollit: {insult}")
            return insult
        return "Insult list is empty"

    def notify_subscribers(self):
        while True:
            insult = insults.insult_me()
            if insult:
                client.publish(self.channel_broadcast, insult)
                print(f"\nNotified subscribers.")
            time.sleep(5)

    def listen(self):
        while True:
            for message in pubsub.listen():
                print(f"Process message {message['data']}")
                if message['type'] == 'message':
                    insult = message['data']
                    print(f"Received insult: {insult}")
                    self.add_insult(insult)

    def filter(self, text):
        censored_text = ""
        if text is not None:
            for word in text.split():
                if word.lower() in client.smembers(self.insultSet):
                    censored_text += "CENSORED "
                else:
                    censored_text += word + " "
        return censored_text

    def filter_service(self):
        while True:
            text = client.blpop(self.workQueue)[1]
            filtered_text = self.filter(text)
            client.lpush(self.censoredTextsList, filtered_text)

insults = Insults()
pubsub = client.pubsub()
pubsub.subscribe(insults.channel_insults)

client.delete(insults.insultSet)
client.delete(insults.censoredTextsList)
client.delete(insults.workQueue)

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
    except KeyboardInterrupt:
        print("Exiting...")
        break
    time.sleep(5)