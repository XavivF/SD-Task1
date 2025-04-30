import random
import Pyro4

@Pyro4.expose
@Pyro4.behavior(instance_mode="single")
class InsultService:
    def __init__(self):
        self.insults_List = []
        self.censored_texts = []

    def add_insult(self, insult):
        if insult not in self.insults_List:
            self.insults_List.append(insult)
            print(f"Insult added: {insult}")
        else:
            print(f"Insult already exists: {insult}")

    def get_insults(self):
        print(f"Insults: {self.insults_List}")
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
        self.censored_texts.append(censored_text)
        print(f"Censored text: {censored_text}")
        return censored_text

    def filter_service(self, text):
        filtered_text = self.filter_text(text)
        print(f"Filtered text: {filtered_text}")
        return filtered_text

    def get_censored_texts(self):
        print(f"Censored texts: {self.censored_texts}")
        return self.censored_texts


def main():
    print("Starting Pyro Insult Service...")
    Pyro4.Daemon.serveSimple(
        {
            InsultService: "example.insults"
        },
        ns=True
    )


if __name__ == "__main__":
    main()