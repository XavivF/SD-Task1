import redis
import random
import time
# Connect to Redis
client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

class Insults:
    def __init__(self):
        self.results = []
        self.channel_name = "Insults_channel"
        self.insultList = "INSULTS"
        self.len = client.llen(self.insultList)

    def add_insult(self, insult):
        current_insults = client.lrange(self.insultList, 0, -1)
        if insult not in current_insults:
            insult = client.lpush(self.insultList, insult)
            self.len+=1
            return f"Insult added: {insult}"
        else:
            return f"Insult already exists"

    def get_insults(self):
        insult = client.lrange(self.insultList, 0, -1)
        return f"Insult list: {insult}"

    def insult_me(self):
        if self.len == 0:
            return "No insults available"
        else:
            i = random.randint(0, self.len - 1)
            insult = client.lindex("INSULTS", random.randint(0, self.len - 1))
            print("i: " + str(i))
            print(f"Insult escollit: {insult}")
            return insult

    def delete_all(self):
        while self.len > 0:
            client.lpop(self.insultList)
            self.len-=1
        print(self.get_insults())
        return "List deleted"

    def notify_subscribers(self):
        pubsub = client.pubsub()
        insult = insults.insult_me()
        client.publish(self.channel_name, insult)
        print("Notified subscribers.")
        return "Subscribers notified."

insults = Insults()

print(insults.delete_all())

while True:
    print(insults.insult_me())
    print(insults.get_insults())
    # Start listening for insults
    insults.notify_subscribers()
    time.sleep(5)
