import Pyro4

def main():
    insult_service = Pyro4.Proxy("PYRONAME:example.insults")

    print("Escoltant insults del servidor...")
    try:
        while True:
            insult = insult_service.insult_me()
            print(f"Insult rebut: {insult}")
    except KeyboardInterrupt:
        print("Interromput per l'usuari.")


if __name__ == "__main__":
    main()