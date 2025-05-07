import Pyro4
import random
import time
import multiprocessing


class InsultClient:
    def __init__(self):
        self.insult_service = Pyro4.Proxy("PYRONAME:pyro.service")
        self.insult_filter = Pyro4.Proxy("PYRONAME:pyro.filter")
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
        while True:
            time.sleep(5)
            try:
                text = random.choice(self.llista_insults)
                censored_text = self.insult_filter.filter_service(text)
                print(f"Text sent: {text}")
                print(f"Censored text: {censored_text}")
            except Pyro4.errors.CommunicationError:
                pass
            except Exception:
                pass

    def send_insults(self):
        for insult in self.insults:
            self.insult_service.add_insult(insult)
            self.insult_filter.add_insult(insult)
            print("Insult sent to server:", insult)

    def broadcast(self):
        while True:
            time.sleep(5)
            try:
                insult = self.insult_service.insult_me()
                self.insult_service.notify_subscribers(insult)
                print(f"Sent insult {insult} to subscribers.")
            except Pyro4.errors.CommunicationError:
                pass
            except Exception:
                pass

def main():
    client = InsultClient()

    try:
        client.send_insults()
    except Pyro4.errors.CommunicationError as e:
        print(f"Communication error: {e}.")

    br_proc = multiprocessing.Process(target=client.broadcast)
    st_proc = multiprocessing.Process(target=client.send_text)
    br_proc.start()
    st_proc.start()

    try:
        print("Press K to stop the services, press I to read the current insult list or press T to read the texts received")
        while True:
            t = input()
            if t == "I":
                try:
                    print("Insult list:", client.insult_service.get_insults())
                except Pyro4.errors.CommunicationError as e:
                    print(f"Communication error: {e}.")
            elif t == "T":
                try:
                    print("Censored texts:", client.insult_filter.get_censored_texts())
                except Pyro4.errors.CommunicationError as e:
                    print(f"Communication error: {e}.")
            elif t == "K":
                print("Stopping services...")
                br_proc.terminate()
                st_proc.terminate()
                br_proc.join()
                st_proc.join()
                break
            else:
                print("Unknown command.")
    except KeyboardInterrupt:
        print("Interrupted by user, stopping...")
        br_proc.terminate()
        st_proc.terminate()
        br_proc.join()
        st_proc.join()

if __name__ == "__main__":
    main()