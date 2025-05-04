import redis
import time
import multiprocessing
from multiprocessing import Process, Queue
import random
import argparse
import sys
import os
import Pyro4

# --- Configuration ---
DEFAULT_REDIS_HOST = 'localhost'
DEFAULT_REDIS_PORT = 6379
DEFAULT_INSULT_CHANNEL = 'Insults_channel' # Channel where new insults are published
DEFAULT_WORK_QUEUE = 'Work_queue'         # List (queue) where texts to filter are sent
DEFAULT_PYRO_NAME = 'redis.counter'        # Default Pyro name for statistics
DEFAULT_DURATION = 10  # Seconds
DEFAULT_CONCURRENCY = 10 # Number of concurrent processes/clients

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
def worker_add_insult(host, port, channel_name, results_queue, end_time):
    """Function executed by each process to publish insults via Redis Pub/Sub."""
    local_request_count = 0
    local_error_count = 0
    redis_client = None
    pid = os.getpid()

    try:
        # Create a Redis client for each process
        redis_client = redis.Redis(host=host, port=port, db=0, decode_responses=True,
                                   socket_connect_timeout=5, socket_timeout=5)
        redis_client.ping() # Check initial connection

        while time.time() < end_time:
            try:
                insult = random.choice(INSULTS_TO_ADD) + str(random.randint(1, 10000))
                redis_client.publish(channel_name, insult)
                local_request_count += 1
            except redis.exceptions.ConnectionError as e:
                print(f"[Process {pid}] Redis connection error publishing insult: {e}", file=sys.stderr)
                local_error_count += 1
                # Attempt to reconnect or exit? Exiting for simplicity.
                break
            except Exception as e:
                # print(f"[Procés {pid}] Error publicant insult (Redis): {e}", file=sys.stderr) # Original comment left as code
                local_error_count += 1
            # time.sleep(0.001) # Probably not necessary

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
            # print(f"[Procés {pid}] Connexió Redis tancada.") # Original comment left as code


def worker_filter_text(host, port, queue_name, results_queue, end_time):
    """Function executed by each process to send texts to the Redis queue."""
    local_request_count = 0
    local_error_count = 0
    redis_client = None
    pid = os.getpid()

    try:
        redis_client = redis.Redis(host=host, port=port, db=0, decode_responses=True,
                                   socket_connect_timeout=5, socket_timeout=5)
        redis_client.ping()

        while time.time() < end_time:
            try:
                text = random.choice(TEXTS_TO_FILTER)
                redis_client.rpush(queue_name, text) # RPUSH adds to the end of the list
                local_request_count += 1
            except redis.exceptions.ConnectionError as e:
                print(f"[Process {pid}] Redis connection error sending to queue: {e}", file=sys.stderr)
                local_error_count += 1
                break
            except Exception as e:
                # print(f"[Procés {pid}] Error enviant text a cua (Redis): {e}", file=sys.stderr) # Original comment left as code
                local_error_count += 1
            # time.sleep(0.001)

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
            # print(f"[Procés {pid}] Connexió Redis tancada.") # Original comment left as code

# --- Main Test Function ---
def run_stress_test(mode, host, port, insult_channel, work_queue, pyro_name, duration, concurrency):
    """Runs the stress test for Redis using multiprocessing."""
    print(f"Starting stress test (Redis with Multiprocessing) in mode '{mode}'...")
    print(f"Redis Host: {host}:{port}")
    print(f"Insult Channel: {insult_channel}")
    print(f"Filter Queue: {work_queue}")
    print(f"Duration: {duration} seconds")
    print(f"Concurrency: {concurrency} processes")
    print("-" * 30)

    if mode == 'add_insult':
        worker_function = worker_add_insult
        target = insult_channel
    elif mode == 'filter_text':
        worker_function = worker_filter_text
        target = work_queue
    else:
        print(f"Error: Mode '{mode}' not recognized.", file=sys.stderr)
        return

    results_queue = Queue()
    processes = []
    start_time = time.time()
    end_time = start_time + duration

    # Create and start processes
    for _ in range(concurrency):
        # Pass host and port to the worker to create the client inside the process
        process = Process(target=worker_function, args=(host, port, target, results_queue, end_time))
        processes.append(process)
        process.start()

    # Wait for all processes to finish
    print("Waiting for processes to finish...")
    for process in processes:
        process.join()

    # Collect results from the queue
    total_request_count = 0
    total_error_count = 0
    while not results_queue.empty():
        req, err = results_queue.get()
        total_request_count += req
        total_error_count += err

    actual_duration = time.time() - start_time

    print("-" * 30)

    # --- Phase 2: Get statistics from the service via Pyro ---
    processed_count_service = -1  # Default value if Pyro call fails
    print(f"Connecting to Pyro ('{pyro_name}') to get service statistics...")
    try:
        # Connect to the service exposed by Pyro
        server_proxy = Pyro4.Proxy(f"PYRONAME:{pyro_name}")
        server_proxy._pyroTimeout = 10  # Set a timeout for Pyro connection/calls

        # Call the method to get the counter
        processed_count_service = server_proxy.get_processed_count()
        print(f"Statistics received from the service via Pyro.")

    except Pyro4.errors.NamingError:
        print(
            f"Error: Pyro service named '{pyro_name}' not found. Ensure the Name Server is running and the service is registered.",
            file=sys.stderr)
    except AttributeError:
        print(f"Error: The remote Pyro object ('{pyro_name}') does not have the exposed method 'get_processed_count'.",
              file=sys.stderr)
        print("Ensure the method is correctly defined with @Pyro4.expose in InsultService.py.", file=sys.stderr)
    except Exception as e:
        print(f"Error connecting or calling the Pyro service ('{pyro_name}'): {e}", file=sys.stderr)
        print("Ensure the InsultService.py service is running and has registered '{pyro_name}'.", file=sys.stderr)


    print("Stress Test (Redis with Multiprocessing) Finished")
    print(f"Total time: {actual_duration:.2f} seconds")
    print("--- Client Results (Stress Test) ---")
    print(f"Commands sent (client success): {total_request_count}")
    print(f"Errors (on client): {total_error_count}")

    if actual_duration > 0:
        throughput = total_request_count / actual_duration
        print(f"Sending throughput (commands/second): {throughput:.2f}")
    else:
        print("Throughput: N/A (duration too short)")

    print("--- Service Statistics (via Pyro) ---")
    if processed_count_service != -1:
        print(f"Requests processed by the service: {processed_count_service}")
        if actual_duration > 0:
            server_throughput = processed_count_service / actual_duration
            print(f"Server throughput (requests/second): {server_throughput:.2f}")
    else:
        print("Could not retrieve service statistics via Pyro.")
    print("-" * 30)


# --- Argument Handling and Execution ---
if __name__ == "__main__":
    multiprocessing.freeze_support()

    parser = argparse.ArgumentParser(description="Stress Test Script (Multiprocessing) for InsultService Redis")
    parser.add_argument("mode", choices=['add_insult', 'filter_text'],
                        help="The functionality to test ('add_insult' or 'filter_text')")
    parser.add_argument("--host", default=DEFAULT_REDIS_HOST,
                        help=f"Redis server host (default: {DEFAULT_REDIS_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_REDIS_PORT,
                        help=f"Redis server port (default: {DEFAULT_REDIS_PORT})")
    parser.add_argument("--insult-channel", default=DEFAULT_INSULT_CHANNEL,
                        help=f"Name of the Redis channel for publishing insults (default: {DEFAULT_INSULT_CHANNEL})")
    parser.add_argument("--work-queue", default=DEFAULT_WORK_QUEUE,
                        help=f"Name of the Redis list/queue for filtering texts (default: {DEFAULT_WORK_QUEUE})")
    parser.add_argument("--pyro-name", default=DEFAULT_PYRO_NAME,
                        help=f"Pyro object name for getting statistics (default: {DEFAULT_PYRO_NAME})")
    parser.add_argument("-d", "--duration", type=int, default=DEFAULT_DURATION,
                        help=f"Test duration in seconds (default: {DEFAULT_DURATION})")
    parser.add_argument("-c", "--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                        help=f"Number of concurrent processes (default: {DEFAULT_CONCURRENCY})")

    args = parser.parse_args()

    run_stress_test(args.mode, args.host, args.port, args.insult_channel, args.work_queue, args.pyro_name, args.duration, args.concurrency)