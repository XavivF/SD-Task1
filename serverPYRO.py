import random
import Pyro4


@Pyro4.expose
@Pyro4.behavior(instance_mode="single")
class Insults:
    def __init__(self):
        self.insults = []

    def add_insult(self, insult):
        self.insults.append(insult)
        print(f"Insult added: {insult}")

    def get_insults(self):
        print(self.insults)

    def insult_me(self):
        if len(self.insults) == 0:
            print("No insults available")
        i = random.randint(0, len(self.insults) - 1)
        print(self.insults[i])


def main():
    print("Servidor encès!!!!")
    Pyro4.Daemon.serveSimple(
        {
            Insults: "example.insults"
        },
        ns=True)


if __name__ == "__main__":
    main()
