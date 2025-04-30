import Pyro4
import random
import time

class InsultClient:
    def __init__(self):
        self.insult_service = Pyro4.Proxy("PYRONAME:example.insults")
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
        censored_text = self.insult_service.filter_text(text)
        print(f"Text sent: {text}")
        print(f"Censored text: {censored_text}")


    def send_insult(self):
        insult = random.choice(self.insults)
        self.insult_service.add_insult(insult)
        print("Insult sent to server:", insult)

def main():
    client = InsultClient()

    client.send_insult()
    try:
        while True:
            client.send_text()
            time.sleep(5)
    except KeyboardInterrupt:
        print("Interrupted by user, stopping...")

if __name__ == "__main__":
    main()