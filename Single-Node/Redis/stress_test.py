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


# Pyro names for retrieving statistics
DEFAULT_PYRO_SERVICE_NAME = 'redis.insultservice'
DEFAULT_PYRO_FILTER_NAME = 'redis.insultfilter'

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
            # print(f"[Procés {pid}] Connexió Redis tancada.") # TODO: Uncomment this line to see the Redis connection close message

def worker_filter_text(host, port, queue_name, results_queue, end_time):
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
def run_stress_test(mode, host, port, insult_channel, work_queue, service_pyro_name, filter_pyro_name, duration, concurrency):
    if (mode == "filter_text") and (service_pyro_name == "pyro.service"):
        print(f"Error: The mode '{mode}' is not compatible with the Pyro name '{service_pyro_name}'.", file=sys.stderr)
        exit(1)
    print(f"Starting stress test (Redis direct interaction) in mode '{mode}'...")
    print(f"Redis Host: {host}:{port}")
    print(f"Insult Channel (for add_insult mode): {insult_channel}")
    print(f"Filter Queue (for filter_text mode): {work_queue}")
    print(f"InsultService Pyro Name (for stats): {service_pyro_name}")
    print(f"InsultFilter Pyro Name (for stats): {filter_pyro_name}")
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
    total_client_sent_count = 0
    total_client_error_count = 0
    while not results_queue.empty():
        try:
            req, err = results_queue.get(timeout=1)
            total_client_sent_count += req
            total_client_error_count += err
        except Exception as e:
            print(f"Error collecting results from queue: {e}", file=sys.stderr)

    actual_duration = time.time() - start_time

    print("-" * 30)

    # --- Phase 2: Get statistics from BOTH services via Pyro ---
    service_processed_count = -1    # Default value if Pyro call fails
    filter_processed_count = -1

    print(f"Connecting to Pyro ('{service_pyro_name}') to get service statistics...")
    # Get stats from InsultService
    try:
        # Connect to the service exposed by Pyro
        server_proxy = Pyro4.Proxy(f"PYRONAME:{service_pyro_name}")
        server_proxy._pyroTimeout = 10  # Set a timeout for Pyro connection/calls

        # Call the exposed get_processed_count method to get the counter
        service_processed_count = server_proxy.get_processed_count()
        print(f"Statistics received from InsultService via Pyro.")
    except Pyro4.errors.NamingError:
        print(f"Error: InsultService Pyro service '{service_pyro_name}' not found. Is it running and registered?",
          file=sys.stderr)
    except AttributeError:
        print(f"Error: InsultService '{service_pyro_name}' does not have the exposed method 'get_processed_count'.",
              file=sys.stderr)
    except Exception as e:
        print(f"Error retrieving stats from InsultService ('{service_pyro_name}'): {e}", file=sys.stderr)

    # Get stats from InsultFilter
    try:
        filter_proxy = Pyro4.Proxy(f"PYRONAME:{filter_pyro_name}")
        filter_proxy._pyroTimeout = 10  # Timeout for stats retrieval
        # Call the exposed get_processed_count method to get the counter
        filter_processed_count = filter_proxy.get_processed_count()
        print(f"Statistics retrieved from InsultFilter ('{filter_pyro_name}').")
    except Pyro4.errors.NamingError:
        print(f"Error: InsultFilter Pyro service '{filter_pyro_name}' not found. Is it running and registered?",
              file=sys.stderr)
    except AttributeError:
        print(f"Error: InsultFilter '{filter_pyro_name}' does not have the exposed method 'get_processed_count'.",
              file=sys.stderr)
    except Exception as e:
        print(f"Error retrieving stats from InsultFilter ('{filter_pyro_name}'): {e}", file=sys.stderr)


    print("Stress Test (Redis with Multiprocessing) Finished")
    print(f"Total time: {actual_duration:.2f} seconds")


    print("--- Client Results (Requests Sent by Stress Test Processes) ---")
    print(f"Total commands sent (client success): {total_client_sent_count}")
    print(f"Total errors (on client during sending): {total_client_error_count}")

    if actual_duration > 0:
        client_sending_throughput = total_client_sent_count / actual_duration
        print(f"Client sending throughput (commands/second): {client_sending_throughput:.2f}")
    else:
        print("Client sending throughput: N/A (duration too short)")

    print("\n--- Service Statistics (Processed Counts via Pyro) ---")
    if service_processed_count != -1:
        # The service count reflects insults added via its listener
        print(f"InsultService processed count: {service_processed_count}")
        if actual_duration > 0:
            service_throughput = service_processed_count / actual_duration
            print(f"InsultService processing throughput (requests/second): {service_throughput:.2f}")
    else:
        print("Could not retrieve InsultService statistics.")

    if filter_processed_count != -1:
        # The filter count reflects items processed from the queue by its worker process
        print(f"InsultFilter processed count: {filter_processed_count}")
        if actual_duration > 0:
            filter_throughput = filter_processed_count / actual_duration
            print(f"InsultFilter processing throughput (requests/second): {filter_throughput:.2f}")
    else:
        print("Could not retrieve InsultFilter statistics.")
    print("-" * 30)


# --- Argument Handling and Execution ---
if __name__ == "__main__":
    multiprocessing.freeze_support()

    parser = argparse.ArgumentParser(
        description="Stress Test Script (Multiprocessing) for Insult Services via Redis (Load) and Pyro (Stats)")
    parser.add_argument("mode", choices=['add_insult', 'filter_text'],
                        help="The functionality to test ('add_insult' publishes to Redis channel; 'filter_text' pushes to Redis queue)")
    parser.add_argument("--host", default=DEFAULT_REDIS_HOST,
                        help=f"Redis server host (default: {DEFAULT_REDIS_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_REDIS_PORT,
                        help=f"Redis server port (default: {DEFAULT_REDIS_PORT})")
    parser.add_argument("--insult-channel", default=DEFAULT_INSULT_CHANNEL,
                        help=f"Name of the Redis channel for publishing insults (default: {DEFAULT_INSULT_CHANNEL})")
    parser.add_argument("--work-queue", default=DEFAULT_WORK_QUEUE,
                        help=f"Name of the Redis list/queue for filtering texts (default: {DEFAULT_WORK_QUEUE})")
    parser.add_argument("--service-pyro-name", default=DEFAULT_PYRO_SERVICE_NAME,
                        help=f"Pyro object name for the InsultService (to get stats) (default: {DEFAULT_PYRO_SERVICE_NAME})")
    parser.add_argument("--filter-pyro-name", default=DEFAULT_PYRO_FILTER_NAME,
                        help=f"Pyro object name for the InsultFilter (to get stats) (default: {DEFAULT_PYRO_FILTER_NAME})")
    parser.add_argument("-d", "--duration", type=int, default=DEFAULT_DURATION,
                        help=f"Test duration in seconds (default: {DEFAULT_DURATION})")
    parser.add_argument("-c", "--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                        help=f"Number of concurrent client processes (default: {DEFAULT_CONCURRENCY})")

    args = parser.parse_args()

    run_stress_test(args.mode, args.host, args.port, args.insult_channel, args.work_queue,
                    args.service_pyro_name, args.filter_pyro_name, args.duration, args.concurrency)