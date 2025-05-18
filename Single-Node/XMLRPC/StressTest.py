import xmlrpc.client
import time
from multiprocessing import Process, Queue
import random
import argparse
import sys
import os

# --- Configuration ---
SERVICE_URL = "http://localhost:8000"
FILTER_URL = "http://localhost:8010/RPC2"
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
def worker_add_insult(server_url, results_queue, end_time):
    local_request_count = 0
    local_error_count = 0
    server_request_count = 0
    server_proxy = None
    pid = os.getpid()

    try:
        # Create a proxy for each process
        server_proxy = xmlrpc.client.ServerProxy(server_url, allow_none=True, verbose=False)
        # We could make an initial non-functional call to verify connection if needed,
        # but XML-RPC normally doesn't have a standard 'ping'. The error will be detected on the first real call.

        while time.time() < end_time:
            try:
                insult = random.choice(INSULTS_TO_ADD)
                # Add a number to ensure they are "new"
                server_proxy.add_insult(insult + str(random.randint(1, 10000)))
                local_request_count += 1

            except Exception as e:
                # print(f"[Process {pid}] Error adding insult (XML-RPC): {e}", file=sys.stderr)
                local_error_count += 1
                # If there's a connection error (e.g., socket error), it might be useful to exit the loop
                if isinstance(e, OSError): # Check if it's a connection/network error
                     print(f"[Process {pid}] Connection error detected. Exiting worker.", file=sys.stderr)
                     break

        # Obtain server request counter
        server_request_count = server_proxy.get_processed_count()

    except Exception as e:
        print(f"[Process {pid}] Serious error creating XML-RPC proxy or initial error: {e}", file=sys.stderr)
        local_error_count += 1 # Error in initial configuration
    finally:
        # Send local results to the queue
        results_queue.put((local_request_count, local_error_count, server_request_count))
        # There is no explicit 'close' method for ServerProxy

def worker_filter_text(server_url, results_queue, end_time):
    local_request_count = 0
    local_error_count = 0
    server_request_count = 0
    server_proxy = None
    pid = os.getpid()

    try:
        server_proxy = xmlrpc.client.ServerProxy(server_url, allow_none=True, verbose=False)

        while time.time() < end_time:
            try:
                text = random.choice(TEXTS_TO_FILTER)
                server_proxy.filter(text)
                local_request_count += 1
            except Exception as e:
                # print(f"[Process {pid}] Error filtering text (XML-RPC): {e}", file=sys.stderr)
                local_error_count += 1
                if isinstance(e, OSError):
                     print(f"[Process {pid}] Connection error detected. Exiting worker.", file=sys.stderr)
                     break

        # Obtain server request counter
        server_request_count = server_proxy.get_processed_count()

    except Exception as e:
        print(f"[Process {pid}] Serious error creating XML-RPC proxy or initial error: {e}", file=sys.stderr)
        local_error_count += 1
    finally:
        results_queue.put((local_request_count, local_error_count, server_request_count))


# --- Main Test Function ---
def run_stress_test(mode, duration, concurrency):
    server_url = ""
    if mode == "filter_text":
        server_url = FILTER_URL
    elif mode == "add_insult":
        server_url = SERVICE_URL

    print(f"Starting XML-RPC stress test in mode '{mode}'...")
    print(f"Server URL: {server_url}")
    print(f"Duration: {duration} seconds")
    print(f"Concurrency: {concurrency} processes")
    print("-" * 30)

    # Select the worker function based on the mode
    if mode == 'add_insult':
        worker_function = worker_add_insult
    elif mode == 'filter_text':
        worker_function = worker_filter_text
    else:
        print(f"Error: Mode '{mode}' not recognized.", file=sys.stderr)
        return

    results_queue = Queue()
    processes = []
    start_time = time.time()
    end_time = start_time + duration

    # Create and start the processes
    for _ in range(concurrency):
        process = Process(target=worker_function, args=(server_url, results_queue, end_time))
        processes.append(process)
        process.start()

    # Wait for all processes to finish
    print("Waiting for processes to finish...")
    for process in processes:
        process.join()

    # Collect results from the queue
    total_request_count = 0
    total_error_count = 0
    server_processed_count = 0
    while not results_queue.empty():
        local_req, local_err, server_req = results_queue.get()
        total_request_count += local_req
        total_error_count += local_err
        server_processed_count = server_req

    actual_duration = time.time() - start_time

    print("-" * 30)
    print("Stress Test XML-RPC Finished")
    print(f"Total time: {actual_duration:.2f} seconds")
    print(f"Total local requests: {total_request_count}")
    print(f"Total server processed requests: {server_processed_count}")
    print(f"Total errors: {total_error_count}")

    if actual_duration > 0:
        throughput = total_request_count / actual_duration
        print(f"Client Throughput (petitions/second): {throughput:.2f}")

        if server_processed_count >= 0:
             server_throughput = server_processed_count / actual_duration
             print(f"Server Throughput (petitions/second): {server_throughput:.2f}")
    else:
        print("Throughput: N/A (duration too short)")

    print("-" * 30)
    return None

# --- Argument Handling and Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stress Test Script (Multiprocessing) for InsultService XML-RPC")
    parser.add_argument("mode", choices=['add_insult', 'filter_text'],
                        help="The functionality to test ('add_insult' or 'filter_text')")
    parser.add_argument("-d", "--duration", type=int, default=DEFAULT_DURATION,
                        help=f"Test duration in seconds (default: {DEFAULT_DURATION})")
    parser.add_argument("-c", "--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                        help=f"Number of concurrent processes (default: {DEFAULT_CONCURRENCY})")

    args = parser.parse_args()

    run_stress_test(args.mode, args.duration, args.concurrency)