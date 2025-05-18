import redis
import time
from multiprocessing import Process, Queue
import random
import argparse
import sys
import os

# --- Configuration ---
DEFAULT_REDIS_HOST = 'localhost'
DEFAULT_REDIS_PORT = 6379
DEFAULT_INSULT_QUEUE = 'Insults_queue'
DEFAULT_WORK_QUEUE = 'Work_queue'         # List (queue) where texts to filter are sent
REDIS_COUNTER = 'COUNTER'


DEFAULT_CONCURRENCY = 5 # Number of concurrent processes/clients

# --- Data for tests ---
INSULTS_TO_ADD = ["tonto", "lleig", "boig", "idiota", "estúpid", "inútil", "desastre", "fracassat", "covard", "mentider",
                  "beneit", "capsigrany", "ganàpia", "nyicris", "gamarús", "bocamoll", "murri", "dropo", "bleda", "xitxarel·lo"]
TEXTS_TO_FILTER = [
    "ets tonto i estas boig", "ets molt inútil", "ets una mica desastre", "ets massa fracassat",
    "ets un poc covard", "ets molt molt mentider", "ets super estúpid", "ets bastant idiota",
    "Ets un beneit de cap a peus.", "No siguis capsigrany i pensa abans de parlar.",
    "Aquest ganàpia no sap el que fa.", "Sempre estàs tan nyicris.", "Quin gamarús !",
    "No siguis bocamoll.", "És un murri.", "No siguis dropo.", "Ets una mica bleda.",
    "Aquest xitxarel·lo es pensa que ho sap tot."
]


# --- Worker Functions (executed in separate processes) ---
def worker_add_insult(host, port, queue_name, results_queue, n_msg):
    local_request_count = 0
    local_error_count = 0
    redis_client = None
    pid = os.getpid()

    try:
        # Create a Redis client for each process
        redis_client = redis.Redis(host=host, port=port, db=0, decode_responses=True,
                                   socket_connect_timeout=5, socket_timeout=5)
        redis_client.ping() # Check initial connection

        while local_request_count < n_msg:
            try:
                insult = random.choice(INSULTS_TO_ADD) + str(random.randint(1, 10000))
                redis_client.rpush(queue_name, insult)
                local_request_count += 1
            except redis.exceptions.ConnectionError as e:
                print(f"[Process {pid}] Redis connection error publishing insult: {e}", file=sys.stderr)
                local_error_count += 1
                break
            except Exception as e:
                print(f"[Process {pid}] Unexpected error publishing insult to Redis: {e}", file=sys.stderr)
                local_error_count += 1

    except redis.exceptions.ConnectionError as e:
         print(f"[Process {pid}] Severe error connecting to Redis in worker_add_insult: {e}", file=sys.stderr)
         local_error_count += 1 # Error in initial connection
    except Exception as e:
        print(f"[Process {pid}] Unexpected error in worker_add_insult: {e}", file=sys.stderr)
        local_error_count += 1
    finally:
        # Send local results to the queue
        results_queue.put((local_request_count, local_error_count))
        if redis_client:
            redis_client.close()
            # print(f"[Procés {pid}] Connexió Redis tancada.")

def worker_filter_text(host, port, queue_name, results_queue, n_msg):
    local_request_count = 0
    local_error_count = 0
    redis_client = None
    pid = os.getpid()

    try:
        redis_client = redis.Redis(host=host, port=port, db=0, decode_responses=True,
                                   socket_connect_timeout=5, socket_timeout=5)
        redis_client.ping()

        while local_request_count < n_msg:
            try:
                text = random.choice(TEXTS_TO_FILTER)
                redis_client.rpush(queue_name, text) # RPUSH adds to the end of the list
                local_request_count += 1
            except redis.exceptions.ConnectionError as e:
                print(f"[Process {pid}] Redis connection error sending to queue: {e}", file=sys.stderr)
                local_error_count += 1
                break
    except redis.exceptions.ConnectionError as e:
         print(f"[Process {pid}] Severe error connecting to Redis in worker_filter_text: {e}", file=sys.stderr)
         local_error_count += 1
    except Exception as e:
        print(f"[Process {pid}] Unexpected error in worker_filter_text: {e}", file=sys.stderr)
        local_error_count += 1
    finally:
        results_queue.put((local_request_count, local_error_count))
        if redis_client:
            redis_client.close()
            # print(f"[Procés {pid}] Connexió Redis tancada.")  # TODO: Uncomment this line to see the Redis connection close message

# --- Main Test Function ---
def run_stress_test(mode, host, port, insult_queue, work_queue, messages, num_service_instances):
    print(f"Starting stress test (Redis) in mode '{mode}'...")
    print(f"Redis Host: {host}:{port}")
    print(f"Insult Queue (for add_insult mode): {insult_queue}")
    print(f"Filter Queue (for filter_text mode): {work_queue}")
    print(f"Number of messages to send: {messages}")
    print("-" * 30)

    if mode == 'add_insult':
        worker_function = worker_add_insult
        target = insult_queue
    elif mode == 'filter_text':
        worker_function = worker_filter_text
        target = work_queue
    else:
        print(f"Error: Mode '{mode}' not recognized.\nOptions: 'add_insult', 'filter_service'.", file=sys.stderr)
        return

    try:
        redis_client = redis.Redis(host=host, port=port, db=0, decode_responses=True,
                                   socket_connect_timeout=5, socket_timeout=5)
    except redis.exceptions.ConnectionError as e:
        print(f"Severe error connecting to Redis in run_stress_test: {e}", file=sys.stderr)
        exit(1)

    n_messages = messages // DEFAULT_CONCURRENCY
    results_queue = Queue()
    processes = []
    start_time = time.time()

    # Create and start processes
    for _ in range(DEFAULT_CONCURRENCY):
        # Pass host and port to the worker to create the client inside the process
        process = Process(target=worker_function, args=(host, port, target, results_queue, n_messages))
        processes.append(process)
        process.start()

    # Wait for all processes to finish
    print("Waiting for processes to finish...")
    for process in processes:
        process.join()

    actual_duration_client = time.time() - start_time

    # Collect results from the queue
    total_client_sent_count = 0
    total_client_error_count = 0
    while not results_queue.empty():
        try:
            req, err = results_queue.get(timeout=1)
            total_client_sent_count += req
            total_client_error_count += err
        except Exception as e:
            print(f"Error collecting results from queue: {e}", file=sys.stderr)

    # We wait for the instances of the service to finish processing all the messages.
    total_messages = n_messages * DEFAULT_CONCURRENCY
    while int(redis_client.get(REDIS_COUNTER)) < total_messages:
        time.sleep(0.001)

    actual_duration_server = time.time() - start_time

    print("-" * 30)

    # --- Phase 2: Get statistics from the service ---
    total_processed_count = int(redis_client.get(REDIS_COUNTER))

    # --- Phase 3: Display results ---
    print("Stress Test (Redis with Multiprocessing) Finished")
    print(f"Total time sending requests: {actual_duration_client:.3f} seconds")
    print(f"Total time processing requests: {actual_duration_server:.3f} seconds")


    print("--- Client Results (Requests Sent by Stress Test Processes) ---")
    print(f"Total commands sent (client success): {total_client_sent_count}")
    print(f"Total errors (on client during sending): {total_client_error_count}")

    if actual_duration_server > 0:
        client_sending_throughput = total_client_sent_count / actual_duration_client
        print(f"Client sending throughput (commands/second): {client_sending_throughput:.3f}")
    else:
        print("Client sending throughput: N/A (duration too short)")

    print("\n--- Statistics (Processed Counts) ---")
    if total_processed_count != 0:
        # The service count reflects insults added via its listener
        print(f"Server processed count: {total_processed_count}")
        if actual_duration_server > 0:
            service_throughput = total_processed_count / actual_duration_server
            print(f"Server processing throughput (requests/second): {service_throughput:.3f}")
    else:
        print("Could not retrieve service statistics")
    print("\n--- Statistics (Per service instance throughput) ---")
    if total_processed_count != 0:
        if actual_duration_server > 0:
            service_throughput = total_processed_count / actual_duration_server
            print(f"Per server processing throughput (requests/second): {service_throughput/num_service_instances:.3f}")

    print("-" * 30)


# --- Argument Handling and Execution ---
if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Stress Test Script (Multiprocessing) for Insult Services via Redis")
    parser.add_argument("mode", choices=['add_insult', 'filter_text'],
                        help="The functionality to test ('add_insult' pushes to Redis queue; 'filter_text' pushes to Redis queue)")
    parser.add_argument("--host", default=DEFAULT_REDIS_HOST,
                        help=f"Redis server host (default: {DEFAULT_REDIS_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_REDIS_PORT,
                        help=f"Redis server port (default: {DEFAULT_REDIS_PORT})")
    parser.add_argument("--insult-queue", default=DEFAULT_INSULT_QUEUE,
                        help=f"Name of the Redis queue for publishing insults (default: {DEFAULT_INSULT_QUEUE})")
    parser.add_argument("--work-queue", default=DEFAULT_WORK_QUEUE,
                        help=f"Name of the Redis list/queue for filtering texts (default: {DEFAULT_WORK_QUEUE})")
    parser.add_argument("-m", "--messages", type=int, required=True,
                        help=f"Number of messages to send")
    parser.add_argument("-n", "--num-instances", type=int, default=1,
                        help=f"Number of service instances to retrieve stats from (default: 1)", required=True)

    args = parser.parse_args()

    run_stress_test(args.mode, args.host, args.port, args.insult_queue, args.work_queue,
                                args.messages, args.num_instances)