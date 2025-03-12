import Pyro4

insult = Pyro4.Proxy("PYRONAME:example.insults")

insult.add_insult("ets tonto")
insult.add_insult("ets molt tonto")
insult.add_insult("ets super tonto")
insult.get_insults()
insult.insult_me()
insult.insult_me()
insult.insult_me()
insult.insult_me()
insult.insult_me()