import Pyro4

@Pyro4.expose
class InsultSubscriber:
    def receive_insult(self, insult):
        print(f"Received broadcast insult: {insult}")

def main():
    insult_service = Pyro4.Proxy("PYRONAME:pyro.service")  # Connect to the insult service
    subscriber = InsultSubscriber()
    daemon = Pyro4.Daemon()
    uri = daemon.register(subscriber)

    insult_service.subscribe(uri)
    print("Subscribed to insult broadcasts.")

    daemon.requestLoop()

if __name__ == "__main__":
    main()