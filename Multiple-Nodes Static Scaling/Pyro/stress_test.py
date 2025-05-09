import Pyro4
import time
from multiprocessing import Process, Queue
import random
import argparse
import sys
import os
import Pyro4.errors
import itertools # For Round Robin strategy

# --- Configuration ---
# Prefixes for the sequential Pyro names of the services
DEFAULT_PYRO_SERVICE_PREFIX = "pyro.service"
DEFAULT_PYRO_FILTER_PREFIX = "pyro.filter"
DEFAULT_DURATION = 10  # Seconds
DEFAULT_CONCURRENCY = 10 # Number of concurrent processes

# --- Test Data ---
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
# These functions implement client-side load balancing using the list of specific Pyro names
def worker_request(pyro_names_list, request_type, results_queue, end_time, ns_host, ns_port):
    local_request_count = 0
    local_error_count = 0
    pid = os.getpid()

    # List of proxies for the backends. Each worker has its own list of proxies.
    backend_proxies = []
    try:
        # Locate the Name Server first
        ns = Pyro4.locateNS(host=ns_host, port=ns_port)
        # Create a proxy for each specific name provided
        for name in pyro_names_list:
            try:
                # Lookup the URI for the specific name
                uri = ns.lookup(name)
                # Create a proxy using the specific URI
                proxy = Pyro4.Proxy(uri)
                proxy._pyroTimeout = 5 # Timeout for connection and calls
                backend_proxies.append(proxy)
                # print(f"[Process {pid}] Successfully created proxy for {name} ({uri})")
            except Pyro4.errors.NamingError:
                 print(f"[Process {pid}] WARNING: Pyro name '{name}' not found in Name Server. Skipping proxy creation.", file=sys.stderr)
            except Exception as e:
                print(f"[Process {pid}] ERROR creating proxy for name {name} using NS lookup: {e}", file=sys.stderr)
                local_error_count += 1 # Count as error if we can't create the initial proxy

    except Pyro4.errors.NamingError:
         print(f"[Process {pid}] ERROR locating Name Server at start. Cannot create proxies.", file=sys.stderr)
         local_error_count += 1
         results_queue.put((local_request_count, local_error_count))
         return
    except Exception as e:
         print(f"[Process {pid}] ERROR during initial proxy setup: {e}", file=sys.stderr)
         local_error_count += 1
         results_queue.put((local_request_count, local_error_count))
         return

    if not backend_proxies:
        print(f"[Process {pid}] ERROR: No valid backend proxies created from names: {pyro_names_list}. Exiting worker.", file=sys.stderr)
        results_queue.put((local_request_count, local_error_count))
        return

    # Round Robin iterator to pick the next proxy
    proxy_iterator = itertools.cycle(backend_proxies)

    while time.time() < end_time:
        try:
            # 1. Select the next proxy using Round Robin
            server_proxy = next(proxy_iterator)

            # 2. Make the RPC call through the selected proxy
            if request_type == 'add_insult':
                data = random.choice(INSULTS_TO_ADD) + str(random.randint(1, 10000))
                server_proxy.add_insult(data)
            elif request_type == 'filter_service':
                data = random.choice(TEXTS_TO_FILTER)
                server_proxy.filter_service(data)
            local_request_count += 1
        except Exception as e:
            # print(f"[Process {pid}] Error during {request_type} call to {server_proxy._pyroUri}: {e}", file=sys.stderr) # Too verbose
            local_error_count += 1
            if isinstance(e, (Pyro4.errors.CommunicationError, Pyro4.errors.NamingError)):
                 print(f"[Process {pid}] Pyro error detected during call to {server_proxy._pyroUri}. It might be down.", file=sys.stderr)
                 # Do not break the loop, the RR iterator will move to the next proxy.

    # Send local results to the queue
    results_queue.put((local_request_count, local_error_count))


# --- Main Test Function ---
def run_stress_test(mode, duration, concurrency, num_instances, ns_host=None, ns_port=None):

    if mode == "filter_text":
        pyro_name_prefix = DEFAULT_PYRO_FILTER_PREFIX
    elif mode == "add_insult":
        pyro_name_prefix = DEFAULT_PYRO_SERVICE_PREFIX
    else:
        print(f"Error: Mode unrecognized '{mode}'.", file=sys.stderr)
        return

    # Generate the list of expected Pyro names based on the prefix and number of instances
    pyro_names_to_test = [f"{pyro_name_prefix}.{i}" for i in range(1, num_instances + 1)]

    print(f"Starting Pyro stress test with mode '{mode}'...")
    print(f"Target Pyro names (expecting {num_instances} instances): {pyro_names_to_test}")
    print(f"Duration: {duration} seconds")
    print(f"Concurrency: {concurrency} processes")
    if ns_host:
         print(f"Name Server: {ns_host}:{ns_port}")
    else:
         print("Name Server: Auto-locating")
    print("-" * 30)

    # Select the request type based on the mode
    request_type = None
    if mode == 'add_insult':
        request_type = 'add_insult'
    elif mode == 'filter_text':
        request_type = 'filter_service' # Correct method on the filter

    results_queue = Queue()
    processes = []
    start_time = time.time()
    end_time = start_time + duration

    # Create and start the worker processes
    # Pass the complete list of expected Pyro names to EACH worker
    for _ in range(concurrency):
        process = Process(target=worker_request, args=(pyro_names_to_test, request_type, results_queue, end_time, ns_host, ns_port))
        processes.append(process)
        process.start()

    # Wait for all processes to finish
    print("Waiting for processes to finish...")
    for process in processes:
        process.join()

    # Collect local results from the workers
    total_client_requests_sent = 0
    total_client_errors = 0
    while not results_queue.empty():
        local_req, local_err = results_queue.get()
        total_client_requests_sent += local_req
        total_client_errors += local_err

    actual_duration = time.time() - start_time

    print("-" * 30)
    print("Pyro Stress Test finalized")
    print(f"Total time: {actual_duration:.2f} seconds")
    print(f"Total client requests sent: {total_client_requests_sent}")
    print(f"Total client errors: {total_client_errors}")

    # --- Code to get the total processed count from ALL backend instances ---
    total_server_processed_count = 0
    successful_backend_count = 0

    print(f"Summing processed counts from {num_instances} expected backend names...")
    try:
        # Locate the Name Server for metric collection
        ns = Pyro4.locateNS(host=ns_host, port=ns_port)
        # Iterate through the list of expected names
        for name in pyro_names_to_test:
            try:
                # Lookup the URI for the specific name and create a proxy to get the counter
                uri = ns.lookup(name)
                backend_proxy = Pyro4.Proxy(uri)
                backend_proxy._pyroTimeout = 5 # Timeout for the call
                count = backend_proxy.get_processed_count()
                total_server_processed_count += count
                successful_backend_count += 1
                # print(f"  Count from {name} ({uri}): {count}")
            except Pyro4.errors.NamingError:
                print(f"  WARNING: Backend instance '{name}' not found in Name Server for metric collection. Skipping count.", file=sys.stderr)
            except Exception as e:
                print(f"  ERROR obtaining processed count from '{name}': {e}", file=sys.stderr)
                # If a backend fails to get the counter, we don't include its count.
                pass # Continue trying with others

    except Pyro4.errors.NamingError:
        print("ERROR: Could not locate Pyro Name Server for final metric collection. Make sure it's running.", file=sys.stderr)
        total_server_processed_count = -1
    except Exception as e:
        print(f"ERROR during final metric collection: {e}", file=sys.stderr)
        total_server_processed_count = -1


    if successful_backend_count > 0:
         print(f"Total server processed petitions (summed from {successful_backend_count}/{num_instances} instances): {total_server_processed_count}")
    elif num_instances > 0: # If we expected instances but didn't find any
         print(f"ERROR: Could not connect to any of the {num_instances} expected backend instances to get processed count.", file=sys.stderr)
         total_server_processed_count = -1


    # --- End of code to get the total ---

    print("-" * 30)

    if actual_duration > 0:
        client_throughput = total_client_requests_sent / actual_duration
        print(f"Client Throughput (petitions/second): {client_throughput:.2f}")

        if total_server_processed_count >= 0: # Only calculate if total was successfully obtained
             server_throughput = total_server_processed_count / actual_duration
             print(f"Server Throughput (petitions/second): {server_throughput:.2f}")
        else:
            print("Server Throughput: N/A (could not get total processed count)")
    else:
        print("Throughput: N/A (duration too short)")

    print("-" * 30)
    return None

# --- Argument Handling and Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stress Test Script (Multiprocessing) for Pyro Services with Client-Side LB by Name")
    parser.add_argument("mode", choices=['add_insult', 'filter_text'],
                        help="The functionality to test ('add_insult' or 'filter_text')")
    parser.add_argument("-d", "--duration", type=int, default=DEFAULT_DURATION,
                        help=f"Test duration in seconds (default: {DEFAULT_DURATION})")
    parser.add_argument("-c", "--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                        help=f"Number of concurrent processes (default: {DEFAULT_CONCURRENCY})")
    parser.add_argument("-n", "--num-instances", type=int, required=True, choices=[1, 2, 3],
                        help="Number of backend service instances being tested (1, 2, or 3)")
    parser.add_argument("--ns-host", type=str, default=None, help="Name Server host (default: locate via broadcast)")
    parser.add_argument("--ns-port", type=int, default=None, help="Name Server port (default: locate via broadcast)")


    args = parser.parse_args()

    run_stress_test(args.mode, args.duration, args.concurrency, args.num_instances, args.ns_host, args.ns_port)