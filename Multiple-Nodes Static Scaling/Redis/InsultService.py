import redis
import argparse
import time
from multiprocessing import Process


class InsultService:
    def __init__(self, redis_host, redis_port):
        self.queue_insults = "Insults_queue"
        self.channel_broadcast = "Insults_broadcast"
        self.insultSet = "INSULTS"
        self.counter_key = "COUNTER"  # Key for Redis counter
        self.client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

    def add_insult(self, insult):
        self.client.incr(self.counter_key)  # INCR Redis Counter
        self.client.sadd(self.insultSet, insult)
        # print(f"InsultService added: {insult} (Counter: {self.get_processed_count()})")
        return f"Insult added: {insult}"

    def get_insults(self):
        insults_list = self.client.smembers(self.insultSet)
        return f"Insult list: {insults_list}"

    def insult_me(self):
        if self.client.scard(self.insultSet) != 0:
            insult = self.client.srandmember(self.insultSet)
            print(f"InsultService Broadcast: chosen: {insult}")
            return insult
        return "Insult list is empty"

    # --- Background processes for this service ---
    def notify_subscribers(self):
        print("InsultService Worker: Starting notify_subscribers...")
        try:
            while True:
                insult = self.insult_me()
                if insult and insult != "Insult list is empty":
                    self.client.publish(self.channel_broadcast, insult)
                    # print(f"InsultService Worker: Notified subscribers with: {insult}")
                time.sleep(5)
        except KeyboardInterrupt:
            print("\nInsultService Worker: Stopping notify_subscribers...")

    def listen(self):
        print("InsultService Worker: Starting listen...")
        try:
            while True:
                item = self.client.blpop(self.queue_insults)
                if item:
                    queue_name, insult = item
                    # print(f"InsultService Worker: Processed insult: {insult} (Counter: {self.get_processed_count()})")
                    self.add_insult(insult)
        except KeyboardInterrupt:
            print("\nInsultService Worker: Stopping listen process...")

    def get_status_daemon(self):
        print("InsultService Worker: Starting get_status_daemon...")
        try:
            while True:
                print("\n--- InsultService Status ---")
                print(self.get_insults())
                print(f"InsultService processed count: {self.get_processed_count()}")
                print("------------------------------\n")
                time.sleep(10)
        except KeyboardInterrupt:
            print("\nInsultService Worker: Stopping get_status_daemon...")

    def get_processed_count(self):
        count = self.client.get(self.counter_key)
        return int(count) if count else 0

# --- Main execution block for InsultService ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--redis-host", default="localhost", help="Redis host")
    parser.add_argument("--redis-port", type=int, default=6379, help="Redis port")
    parser.add_argument("-id", "--instance-id", type=int, default=1, help="Service instance ID", required=True)
    args = parser.parse_args()

    print("Starting InsultService...")

    insults_service = InsultService(args.redis_host, args.redis_port)

    print("InsultService: Clearing initial Redis keys (INSULTS, INSULTS_COUNTER)...")
    insults_service.client.delete(insults_service.insultSet)
    insults_service.client.delete(insults_service.counter_key)
    print("Redis keys cleared.")

    # --- Start background processes for InsultService ---
    print("InsultService: Starting worker processes...")
    process_service_notify = Process(target=insults_service.notify_subscribers)
    process_service_listen = Process(target=insults_service.listen)

    process_service_notify.start()
    process_service_listen.start()

    try:
        insults_service.get_status_daemon()
    except KeyboardInterrupt:
        print("\nShutting down InsultService...")
        print("Terminating worker processes...")
        process_service_notify.terminate()
        process_service_listen.terminate()

        process_service_notify.join()
        process_service_listen.join()
        insults_service.client.close()
        print("InsultService worker processes finished.")
        print("Exiting InsultService main program.")
