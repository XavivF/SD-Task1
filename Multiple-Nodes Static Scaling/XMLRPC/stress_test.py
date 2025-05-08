import xmlrpc.client
import time
from multiprocessing import Process, Queue
import random
import argparse
import sys
import os

LOAD_BALANCER_URL = "http://localhost:9000/RPC2"

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


# --- Worker Functions (molt simplificades) ---
# The worker now connects to the LB and only has 1 proxy
def worker_add_insult(lb_url, results_queue, end_time):
    local_request_count = 0
    local_error_count = 0
    pid = os.getpid()
    server_proxy = None

    try:
        server_proxy = xmlrpc.client.ServerProxy(lb_url, allow_none=True, verbose=False)

        while time.time() < end_time:
            try:
                insult = random.choice(INSULTS_TO_ADD)
                server_proxy.add_insult(insult + str(random.randint(1, 10000)))
                local_request_count += 1
            except Exception as e:
                # print(f"[Process {pid}] Error adding insult (XML-RPC via LB): {e}", file=sys.stderr)
                local_error_count += 1
                if isinstance(e, (OSError, xmlrpc.client.Fault)):
                     print(f"[Process {pid}] Connection or XML-RPC error via LB detected. Exiting worker: {e}", file=sys.stderr)
                     break

    except Exception as e:
        print(f"[Process {pid}] Serious error creating XML-RPC proxy to LB: {e}", file=sys.stderr)
        local_error_count += 1
    finally:
        results_queue.put((local_request_count, local_error_count))

def worker_filter_text(lb_url, results_queue, end_time):
    local_request_count = 0
    local_error_count = 0
    pid = os.getpid()
    server_proxy = None

    try:
        server_proxy = xmlrpc.client.ServerProxy(lb_url, allow_none=True, verbose=False)

        while time.time() < end_time:
            try:
                text = random.choice(TEXTS_TO_FILTER)
                server_proxy.filter(text)
                local_request_count += 1
            except Exception as e:
                # print(f"[Process {pid}] Error filtering text (XML-RPC via LB): {e}", file=sys.stderr)
                local_error_count += 1
                if isinstance(e, (OSError, xmlrpc.client.Fault)):
                     print(f"[Process {pid}] Connection or XML-RPC error via LB detected. Exiting worker: {e}", file=sys.stderr)
                     break

    except Exception as e:
        print(f"[Process {pid}] Serious error creating XML-RPC proxy to LB: {e}", file=sys.stderr)
        local_error_count += 1
    finally:
        results_queue.put((local_request_count, local_error_count))


# --- Main Test Function ---
def run_stress_test(mode, lb_url, duration, concurrency):
    print(f"Starting XML-RPC stress test in mode '{mode}' via Load Balancer...")
    print(f"Load Balancer URL: {lb_url}")
    print(f"Duration: {duration} seconds")
    print(f"Concurrency: {concurrency} processes")
    print("-" * 30)

    if mode == 'add_insult':
        worker_function = worker_add_insult
    elif mode == 'filter_text':
        worker_function = worker_filter_text
    else:
        print(f"Error: Mode '{mode}' not recognized.", file=sys.stderr)
        return

    lb_proxy = None
    try:
        lb_proxy = xmlrpc.client.ServerProxy(lb_url, allow_none=True, verbose=False)
    except Exception as e:
         print(f"Error creating proxy to Load Balancer {lb_url}: {e}", file=sys.stderr)
         return


    results_queue = Queue()
    processes = []
    start_time = time.time()
    end_time = start_time + duration

    # Create and start worker processes, passing the LB URL
    for _ in range(concurrency):
        process = Process(target=worker_function, args=(lb_url, results_queue, end_time))
        processes.append(process)
        process.start()

    # Wait for all processes to finish
    print("Waiting for processes to finish...")
    for process in processes:
        process.join()

    # Collect local results from workers
    total_local_request_count = 0
    total_local_error_count = 0
    while not results_queue.empty():
        local_req, local_err = results_queue.get()
        total_local_request_count += local_req
        total_local_error_count += local_err

    actual_duration = time.time() - start_time

    # Get the total number of requests processed by the servers via the LB
    total_server_processed_count = -1 # Initial value
    try:
        total_server_processed_count = lb_proxy.get_processed_count()
    except Exception as e:
        print(f"Error getting total processed count from Load Balancer: {e}", file=sys.stderr)


    print("-" * 30)
    print("Stress Test XML-RPC Finished (via Load Balancer)")
    print(f"Total time: {actual_duration:.2f} seconds")
    print(f"Total client requests sent: {total_local_request_count}")
    if total_server_processed_count != -1:
        print(f"Total server processed requests (summed via LB): {total_server_processed_count}")
    else:
         print("Could not get total server processed count from LB.")

    print(f"Total client errors: {total_local_error_count}")

    if actual_duration > 0:
        client_throughput = total_local_request_count / actual_duration
        print(f"Client Throughput (petitions/second): {client_throughput:.2f}")

        if total_server_processed_count >= 0:
             server_throughput = total_server_processed_count / actual_duration
             print(f"Server Throughput (petitions/second): {server_throughput:.2f}")
    else:
        print("Throughput: N/A (duration too short)")

    print("-" * 30)
    return None

# --- Argument Handling and Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stress Test Script (Multiprocessing) for XML-RPC Load Balancer")
    parser.add_argument("mode", choices=['add_insult', 'filter_text'],
                        help="The functionality to test ('add_insult' or 'filter_text')")
    parser.add_argument("-d", "--duration", type=int, default=DEFAULT_DURATION,
                        help=f"Test duration in seconds (default: {DEFAULT_DURATION})")
    parser.add_argument("-c", "--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                        help=f"Number of concurrent processes (default: {DEFAULT_CONCURRENCY})")
    parser.add_argument("-u", "--lb_url", type=str, default=LOAD_BALANCER_URL,
                        help=f"URL of the Load Balancer (default: {LOAD_BALANCER_URL})")

    args = parser.parse_args()

    run_stress_test(args.mode, args.lb_url, args.duration, args.concurrency)