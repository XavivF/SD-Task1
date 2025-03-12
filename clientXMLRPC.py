import xmlrpc.client

s = xmlrpc.client.ServerProxy('http://10.112.204.7:8000')
print(s.add_insult("ets tonto"))
print(s.add_insult("ets molt tonto"))
print(s.add_insult("ets super tonto"))
print(s.get_insults())
print(s.insult_me())
print(s.insult_me())
print(s.insult_me())
print(s.insult_me())
print(s.insult_me())

# Print list of available methods
#print(s.system.listMethods())