import xmlrpc.client
from time import sleep

def broadcast():
    while True:
        print(s.insult_me())
        sleep(5)

s = xmlrpc.client.ServerProxy('http://localhost:8000')
s.add_subscriber("http://localhost:8001/RPC2")
print(s.add_insult("tonto"))
print(s.add_insult("lleig"))
print(s.add_insult("boig"))
print(s.get_insults())
print(s.insult_me())
#s.notify_subscribers("tonto")

text = "ets tonto i estas boig"
print(s.filter(text))

text = "ets llest i estas boig"
print(s.filter(text))
print(s.get_results())
broadcast()
