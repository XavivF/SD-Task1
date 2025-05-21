import xmlrpc.client
import time
from multiprocessing import Process, Queue
import random
import argparse
import sys
import os
import redis
# Default URL for the Load Balancer
LOAD_BALANCER_URL = "http://localhost:9000/RPC2"
REDIS_COUNTER = 'COUNTER'

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


# --- Worker Functions ---
# The worker connects to the Load Balancer (LB) and uses a single proxy to it.
def worker_add_insult(urls, results_queue, n_msg):
    local_request_count = 0
    local_error_count = 0
    pid = os.getpid()
    lb_proxy = None
    try:
        servers = []
        for url in urls:
            servers.append(url)

        services = []

        for server in servers:
            services.append(xmlrpc.client.ServerProxy(f"http://{server}/RPC2", allow_none=True, verbose=False))

        while local_request_count < n_msg:
            try:
                insult = random.choice(INSULTS_TO_ADD) + str(random.randint(1, 100000))
                actual = services[local_request_count % len(servers)]

                for idx, srv in enumerate(servers):
                    if actual._ServerProxy__host == srv:
                        services[idx].add_insult(insult)
                        break

                local_request_count += 1
            except Exception as e:
                print(f"Error: {e}")
                local_request_count += 1
            except Exception as e:
                print(f"[Process {pid}] Error adding insult (XML-RPC via LB): {e}", file=sys.stderr)
                local_error_count += 1
                if isinstance(e, (OSError, xmlrpc.client.Fault)):
                     print(f"[Process {pid}] Connection or XML-RPC error via LB detected. Exiting worker for add_insult: {e}", file=sys.stderr)
                     break

    except Exception as e:
        print(f"[Process {pid}] Serious error creating XML-RPC proxy to LB for add_insult: {e}", file=sys.stderr)
        local_error_count += 1
    finally:
        results_queue.put((local_request_count, local_error_count))

def worker_filter_text(urls, results_queue, n_msg):
    local_request_count = 0
    local_error_count = 0
    pid = os.getpid()
    try:
        servers = []
        for url in urls:
            servers.append(url)

        services = []

        for server in servers:
            services.append(xmlrpc.client.ServerProxy(f"http://{server}/RPC2", allow_none=True, verbose=False))


        while local_request_count < n_msg:
            try:
                text = random.choice(TEXTS_TO_FILTER)
                actual = services[local_request_count % len(servers)]

                for idx, srv in enumerate(servers):
                    if actual._ServerProxy__host == srv:
                        services[idx].filter(text)
                        break

                local_request_count += 1
            except Exception as e:
                # print(f"[Process {pid}] Error filtering text (XML-RPC via LB): {e}", file=sys.stderr)
                local_error_count += 1
                if isinstance(e, (OSError, xmlrpc.client.Fault)):
                     print(f"[Process {pid}] Connection or XML-RPC error via LB detected. Exiting worker for filter_text: {e}", file=sys.stderr)
                     break

    except Exception as e:
        print(f"[Process {pid}] Serious error creating XML-RPC proxy to LB for filter_text: {e}", file=sys.stderr)
        local_error_count += 1
    finally:
        results_queue.put((local_request_count, local_error_count))

# --- Main Test Function ---
def run_stress_test(mode, lb_url, messages, service_url, filter_url):
    print(f"Starting XML-RPC stress test in mode '{mode}' via Load Balancer...")
    print("-" * 30)

    num_service_instances = 0
    url = []


    worker_function = None
    get_count_method_name = "get_processed_count"  # To store the name of the method to get counts from LB

    if mode == 'add_insult':
        worker_function = worker_add_insult
        num_service_instances = len(service_url)
        url = service_url
    elif mode == 'filter_text':
        worker_function = worker_filter_text
        num_service_instances = len(filter_url)
        url = filter_url
    else:
        print(f"Error: Mode '{mode}' not recognized. Valid modes are 'add_insult' or 'filter_text'.", file=sys.stderr)
        return

    lb_main_proxy = None
    try:
        lb_main_proxy = xmlrpc.client.ServerProxy(lb_url, allow_none=True, verbose=False)
        lb_main_proxy.system.listMethods()
        print("Successfully connected to Load Balancer.")
    except Exception as e:
        print(f"Error: Could not connect to or communicate with Load Balancer at {lb_url}: {e}", file=sys.stderr)
        print("Please ensure the Load Balancer is running and accessible.")
        return

    try:
        redis_client = redis.Redis(db=0, decode_responses=True,
                                   socket_connect_timeout=5, socket_timeout=5)
    except redis.exceptions.ConnectionError as e:
        print(f"Severe error connecting to Redis in run_stress_test: {e}", file=sys.stderr)
        exit(1)

    redis_client.set(REDIS_COUNTER, 0)

    n_messages = messages // DEFAULT_CONCURRENCY
    results_queue = Queue()
    processes = []
    start_time = time.time()

    # Create and start worker processes
    print(f"Launching {DEFAULT_CONCURRENCY} worker processes for mode '{mode}'...")
    for _ in range(DEFAULT_CONCURRENCY):
        process = Process(target=worker_function, args=(url, results_queue, n_messages))
        processes.append(process)
        process.start()

    # Wait for all processes to finish
    print("Waiting for processes to finish...")
    for process in processes:
        process.join()

    actual_duration_client = time.time() - start_time

    # Collect local results from workers
    total_client_requests_sent = 0
    total_client_errors = 0
    while not results_queue.empty():
        local_req, local_err = results_queue.get_nowait()  # Use get_nowait as processes should be done
        total_client_requests_sent += local_req
        total_client_errors += local_err

    total_messages = n_messages * DEFAULT_CONCURRENCY
    # We wait for the instances of the service to finish processing all the messages.
    while int(redis_client.get(REDIS_COUNTER)) < total_messages:
        time.sleep(0.001)

    actual_duration_server = time.time() - start_time

    # Get the total number of requests processed by the servers via the LB
    total_server_processed_count = -1  # Default to an error value
    if lb_main_proxy and get_count_method_name:
        try:
            # Dynamically get the correct count method from the LB proxy
            get_total_processed_count_func = getattr(lb_main_proxy, get_count_method_name)
            total_server_processed_count = get_total_processed_count_func()
            print(f"Successfully retrieved total processed count ({total_server_processed_count}) from LB using '{get_count_method_name}'.")
        except xmlrpc.client.Fault as f:
            print(f"XML-RPC Fault when calling '{get_count_method_name}' on Load Balancer: {f.faultString} (Code: {f.faultCode})",
                file=sys.stderr)
        except AttributeError:
            print(f"Error: The method '{get_count_method_name}' was not found on the Load Balancer proxy.",
                  file=sys.stderr)
            print("Please ensure the Load Balancer exposes this method.", file=sys.stderr)
        except Exception as e:
            print(f"Error getting total processed count from Load Balancer using '{get_count_method_name}': {e}",
                  file=sys.stderr)
    else:
        print("Load Balancer proxy not available or method name for counts not set; cannot get server counts.",
              file=sys.stderr)


    print("-" * 30)
    print(f"Stress Test (XML-RPC via Load Balancer) - Results\n")
    print(f"Test Mode: {mode}")
    print(f"Target URL (Load Balancer): {lb_url}")
    print(f"Total time sending requests: {actual_duration_client:.3f} seconds")
    print(f"Total time processing requests: {actual_duration_server:.3f} seconds")
    print("-" * 30)
    print(f"Total Client Requests Sent (by workers): {total_client_requests_sent}")
    print(f"Total Client Errors (encountered by workers): {total_client_errors}")

    if total_server_processed_count != -1:
        print(f"Total Server Processed Requests (summed via LB from backends): {total_server_processed_count}")
    else:
        print("Could not reliably get total server processed count from Load Balancer.")

    print("-" * 30)
    if actual_duration_client > 0:
        client_throughput = total_client_requests_sent / actual_duration_client
        print(f"Client-side Throughput (requests/second): {client_throughput:.3f}")

        if total_server_processed_count >= 0:  # Only calculate if count is valid
            server_throughput = total_server_processed_count / actual_duration_server
            print(f"Server-side Throughput (processed requests/second via LB): {server_throughput:.3f}")
    else:
        print("Throughput: N/A (actual duration was zero or too short)")
    print("\n--- Statistics (Per server throughput) ---")
    if total_server_processed_count != 0:
        if actual_duration_server > 0:
            service_throughput = total_server_processed_count / actual_duration_server
            print(f"Per server processing throughput (requests/second): {service_throughput / num_service_instances:.3f}")

    print("-" * 30)
    if redis_client:
        redis_client.close()
    return None


# --- Argument Handling and Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stress Test Script (Multiprocessing) for XML-RPC via a Load Balancer",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("mode", choices=['add_insult', 'filter_text'],
        help="The XML-RPC functionality to test ('add_insult' for InsultService, 'filter_text' for InsultFilter).")
    parser.add_argument("-m", "--messages", type=int, required=True,
                        help=f"Number of messages to send")
    parser.add_argument("-u", "--lb_url", type=str, default=LOAD_BALANCER_URL,
        help="URL of the XML-RPC Load Balancer (e.g., http://localhost:9000/RPC2).")
    parser.add_argument("--service_urls", nargs='+', default=[],
                        help="List of URLs of instances of InsultService (e.g., localhost:8000 localhost:8001)")
    parser.add_argument("--filter_urls", nargs='+', default=[],
                        help="List of URLs of instances of InsultFilter (e.g., localhost:8010 localhost:8011)")

    args = parser.parse_args()

    run_stress_test(args.mode, args.lb_url, args.messages, args.service_urls, args.filter_urls)