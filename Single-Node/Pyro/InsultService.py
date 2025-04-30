import random
import threading
import time
import Pyro4

@Pyro4.expose
@Pyro4.behavior(instance_mode="single")
class InsultService:
    def __init__(self):
        self.insults_List = []
        self.censored_texts = []
        self.subscribers = []

    def add_insult(self, insult):
        if insult not in self.insults_List:
            self.insults_List.append(insult)
            print(f"Insult added: {insult}")
        else:
            print(f"Insult already exists: {insult}")

    def get_insults(self):
        print(f"Insult list: {self.insults_List}")
        return self.insults_List

    def insult_me(self):
        if not self.insults_List:
            return "No insults available"
        insult = random.choice(self.insults_List)
        print(f"Selected insult: {insult}")
        return insult

    def filter_text(self, text):
        censored_text = ""
        for word in text.split():
            if word.lower() in self.insults_List:
                censored_text += "CENSORED "
            else:
                censored_text += word + " "
        return censored_text

    def filter_service(self, text):
        censored_text = self.filter_text(text)
        self.censored_texts.append(censored_text)
        print(f"Censored text: {censored_text}")
        return censored_text

    def get_censored_texts(self):
        print(f"Censored texts: {self.censored_texts}")
        return self.censored_texts

    def subscribe(self, client_proxy):
        self.subscribers.append(client_proxy)
        print("New subscriber added.")

    def notify_subscribers(self, insult):
            for subscriber in self.subscribers:
                try:
                    print(f"Notifying subscriber: {subscriber} with:" + insult)
                    subscriber.receive_insult(insult)
                except Pyro4.errors.CommunicationError:
                    print("Failed to contact a subscriber.")

def main():
    print("Starting Pyro Insult Service...")
    daemon = Pyro4.Daemon()  # Crear el daemon de Pyro
    ns = Pyro4.locateNS()  # Localitzar el servidor de noms
    uri = daemon.register(InsultService)  # Registrar el servei com a objecte Pyro
    ns.register("example.insults", uri)  # Registrar el servei al servidor de noms
    print("Insult Service is ready.")
    daemon.requestLoop()  # Iniciar el bucle d'espera


if __name__ == "__main__":
    main()