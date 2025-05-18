import redis
import argparse
from multiprocessing import Process
import time

class InsultFilter:
    def __init__(self, redis_host, redis_port):
        self.insultSet = "INSULTS"
        self.censoredTextsSet = "RESULTS"
        self.workQueue = "Work_queue"
        self.counter_key = "COUNTER"
        self.client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

    def add_insult(self, insult):
        self.client.incr(self.counter_key)
        self.client.sadd(self.insultSet, insult)
        print(f"InsultFilter: Insult added (internal): {insult} (Counter: {self.counter.value})")
        return f"Insult added (internal): {insult}"

    def filter_text(self, text):
        # print(f"InsultFilter: Received text to filter: {text}")
        censored_text = ""
        if text is not None:
            insults = self.client.smembers(self.insultSet)
            for word in text.split():
                if word.lower() in insults:
                    censored_text += "CENSORED "
                else:
                    censored_text += word + " "
        return censored_text.strip() # Remove trailing space

    def get_censored_texts(self):
        results = self.client.smembers(self.censoredTextsSet)
        return f"Censored texts:{results}"

    def filter_service(self):
        print("InsultFilter Service: Starting filter_service...")
        try:
            while True:
                item = self.client.blpop(self.workQueue)     # Blocking pop from the work queue
                if item:
                    queue_name, text = item
                    # print(f"InsultFilter Worker: Processing text from {queue_name}: Text: {text}")
                    self.client.incr(self.counter_key)
                    filtered_text = self.filter_text(text)
                    # print(f"InsultFilter Worker: Filtered text: {filtered_text} (Counter: {self.counter.value})")
                    self.client.sadd(self.censoredTextsSet, filtered_text)
        except KeyboardInterrupt:
            print("\nInsultFilter Service: Stopping filter_service...")
            exit(1)

    def get_status_daemon(self):
        print("InsultFilter Worker: Starting get_status_daemon...")
        try:
            while True:
                print("\n--- InsultFilter Status ---")
                print(self.get_censored_texts())
                print(f"InsultFilter processed count: {self.get_processed_count()}")
                print("------------------------------\n")
                time.sleep(10)
        except KeyboardInterrupt:
            print("\nInsultFilter Worker: Stopping get_status_daemon...")

    def get_processed_count(self):
        count = self.client.get(self.counter_key)
        return int(count) if count else 0

# --- Main execution block for InsultFilter ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--redis-host", default="localhost", help="Redis host")
    parser.add_argument("--redis-port", type=int, default=6379, help="Redis port")
    parser.add_argument("-id", "--instance-id", type=int, default=1, help="Service instance ID", required=True)
    args = parser.parse_args()
    print("Starting InsultFilter...")

    insult_filter = InsultFilter(args.redis_host, args.redis_port)     # Create the InsultFilter instance

    print("InsultFilter: Clearing initial Redis keys (INSULTS, RESULTS, Work_queue)...")
    insult_filter.client.delete(insult_filter.insultSet)
    insult_filter.client.delete(insult_filter.censoredTextsSet)
    insult_filter.client.delete(insult_filter.workQueue)
    insult_filter.client.delete(insult_filter.counter_key)
    print("Redis keys cleared.")

    # --- Start background processes for InsultFilter ---
    print("InsultFilter: Starting worker processes...")
    process_filter_service = Process(target=insult_filter.filter_service)

    process_filter_service.start()
    try:
        insult_filter.get_status_daemon()
    except KeyboardInterrupt:
        print("\nShutting down InsultFilter...")
        print("Terminating worker processes...")
        # Terminate and join worker processes
        process_filter_service.terminate()
        process_filter_service.join()
        insult_filter.client.close()
        print("InsultFilter worker processes finished.")
        print("Exiting InsultFilter main program.")