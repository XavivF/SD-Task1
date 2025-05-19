import Pyro4
import time
import multiprocessing
from multiprocessing import Process, Queue
import random
import argparse
import sys

DEFAULT_PYRO_SERVICE = "pyro.service"
DEFAULT_PYRO_FILTER = "pyro.filter"
DEFAULT_DURATION = 10  # Seconds
DEFAULT_CONCURRENCY = 10 # Number of concurrent processes

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

# --- Worker Functions (performed in different processes) ---
def worker_add_insult(pyro_name, results_queue, end_time):
    local_request_count = 0
    local_error_count = 0
    server_proxy = None
    try:
        # We create a proxy for each process
        server_proxy = Pyro4.Proxy(f"PYRONAME:{pyro_name}")
        server_proxy._pyroTimeout = 5 # Timeout for the connection
    except Exception as e:
        print(f"[Process {multiprocessing.current_process().pid}] Error connecting to the server: {e}", file=sys.stderr)
        local_error_count += 1
        results_queue.put((local_request_count, local_error_count))
        return

    while time.time() < end_time:
        try:
            insult = random.choice(INSULTS_TO_ADD) + str(random.randint(1, 10000))
            server_proxy.add_insult(insult)
            local_request_count += 1
        except Exception:
            local_error_count += 1

    # Send local results to the main process
    results_queue.put((local_request_count, local_error_count))

def worker_filter_text(pyro_name, results_queue, end_time):
    local_request_count = 0
    local_error_count = 0
    server_proxy = None
    try:
        server_proxy = Pyro4.Proxy(f"PYRONAME:{pyro_name}")
        server_proxy._pyroTimeout = 5
    except Exception as e:
        print(f"[Process {multiprocessing.current_process().pid}] Error connecting to the server: {e}", file=sys.stderr)
        local_error_count += 1
        results_queue.put((local_request_count, local_error_count))
        return

    while time.time() < end_time:
        try:
            text = random.choice(TEXTS_TO_FILTER)
            server_proxy.filter_service(text)
            local_request_count += 1
        except Exception:
            local_error_count += 1

    results_queue.put((local_request_count, local_error_count))

# --- Main function ---
def run_stress_test(mode, duration, concurrency):
    pyro_name = ""
    if mode == "filter_text": pyro_name = DEFAULT_PYRO_FILTER
    if mode == "add_insult": pyro_name = DEFAULT_PYRO_SERVICE
    print(f"Starting Pyro stress test with mode '{mode}'...")
    print(f"Pyro name: {pyro_name}")
    print(f"Duration: {duration} seconds")
    print(f"Concurrency: {concurrency} processes")
    print("-" * 30)

    if mode == 'add_insult':
        worker_function = worker_add_insult
    elif mode == 'filter_text':
        worker_function = worker_filter_text
    else:
        print(f"Error: Mode unrecognized '{mode}' .", file=sys.stderr)
        return

    results_queue = Queue()
    processes = []
    start_time = time.time()
    end_time = start_time + duration

    # Create and start the processes
    for _ in range(concurrency):
        process = Process(target=worker_function, args=(pyro_name, results_queue, end_time))
        processes.append(process)
        process.start()

    print("Waiting for processes to end...")
    for process in processes:
        process.join()

    total_client_requests_sent = 0
    total_client_errors = 0
    while not results_queue.empty():
        req, err = results_queue.get()
        total_client_requests_sent += req
        total_client_errors += err

    actual_duration = time.time() - start_time

    print("-" * 30)
    print("Pyro Stress Test finalized")
    print(f"Total duration: {actual_duration:.2f} seconds")
    print(f"Intended petitions by the client: {total_client_requests_sent}")
    print(f"Total client errors: {total_client_errors}")

    server_processed_count = -1
    try:
        # Create a proxy to obtain the processed count from the server
        server_proxy_metrics = Pyro4.Proxy(f"PYRONAME:{pyro_name}")
        server_proxy_metrics._pyroTimeout = 5
        server_processed_count = server_proxy_metrics.get_processed_count()
        print(f"Server processed petitions: {server_processed_count}")
    except Exception as e:
        print(f"ERROR: It isn't possible to obtain the processed petitions: {e}", file=sys.stderr)


    if actual_duration > 0:
        client_throughput = total_client_requests_sent / actual_duration
        print(f"Client Throughput (petitions/second): {client_throughput:.2f}")

        if server_processed_count >= 0:
             server_throughput = server_processed_count / actual_duration
             print(f"Server Throughput (petitions/second): {server_throughput:.2f}")
    else:
        print("Throughput: N/A (too short duration)")

    print("-" * 30)
    return None

# --- Arguments Management ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stress Test Script for Pyro Insult Service")
    parser.add_argument("mode", choices=['add_insult', 'filter_text'],
                        help="The function to test ('add_insult' o 'filter_text')")
    parser.add_argument("-d", "--duration", type=int, default=DEFAULT_DURATION,
                        help=f"Duration in seconds (default: {DEFAULT_DURATION})")
    parser.add_argument("-c", "--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                        help=f"Number of concurrent processes (default: {DEFAULT_CONCURRENCY})")

    args = parser.parse_args()
    # It may be necessary to start the name server manually first: python3 -m Pyro4.naming
    run_stress_test(args.mode, args.duration, args.concurrency)