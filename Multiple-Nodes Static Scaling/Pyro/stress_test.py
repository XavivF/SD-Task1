import Pyro4
import time
from multiprocessing import Process, Queue
import random
import argparse
import sys
import Pyro4.errors

# --- Configuration ---
# Name for the LoadBalancer in the Name Server
DEFAULT_PYRO_LOADBALANCER = "pyro.loadbalancer"
DEFAULT_DURATION = 10  # Seconds
DEFAULT_CONCURRENCY = 10 # Number of concurrent processes

# --- Test Data ---
INSULTS_TO_ADD = [
    "tonto", "lleig", "boig", "idiota", "estúpid", "inútil", "desastre", "fracassat", "covard", "mentider",
    "beneit", "capsigrany", "ganàpia", "nyicris", "gamarús", "bocamoll", "murri", "dropo", "bleda", "xitxarel·lo"
]
TEXTS_TO_FILTER = [
    "ets tonto i estas boig", "ets molt inútil", "ets una mica desastre", "ets massa fracassat",
    "ets un poc covard", "ets molt molt mentider", "ets super estúpid", "ets bastant idiota",
    "Ets un beneit de cap a peus.", "No siguis capsigrany i pensa abans de parlar.",
    "Aquest ganàpia no sap el que fa.", "Sempre estàs tan nyicris.", "Quin gamarús !",
    "No siguis bocamoll.", "És un murri.", "No siguis dropo.", "Ets una mica bleda.",
    "Aquest xitxarel·lo es pensa que ho sap tot."
]

# --- Worker Function ---
def worker_request(duration, results_queue, ns_host, ns_port, mode):
    requests_sent = 0
    errors = 0
    load_balancer = None

    try:
        if ns_host and ns_port:
            ns = Pyro4.locateNS(host=ns_host, port=ns_port)
        else:
            ns = Pyro4.locateNS()
        load_balancer = Pyro4.Proxy(ns.lookup(DEFAULT_PYRO_LOADBALANCER))
        load_balancer._pyroTimeout = 10  # Timeout for proxy calls
    except Pyro4.errors.NamingError:
        print(f"Worker ERROR: LoadBalancer '{DEFAULT_PYRO_LOADBALANCER}' not found. Make sure it is running.", file=sys.stderr)
        results_queue.put((0, 1))
        return
    except Exception as e:
        print(f"Worker ERROR connecting to the LoadBalancer for testing: {e}", file=sys.stderr)
        results_queue.put((0, 1))
        return

    start_time = time.time()
    while time.time() - start_time < duration:
        try:
            if mode == 'add_insult':
                data = random.choice(INSULTS_TO_ADD) + str(random.randint(1, 10000))
                load_balancer.add_insult(data)
                requests_sent+=1
            elif mode == 'filter_text':
                data = random.choice(TEXTS_TO_FILTER)
                load_balancer.filter_service(data)
                requests_sent+=1
        except Pyro4.errors.CommunicationError as e:
            print(f"Worker ERROR: Communication error with the LoadBalancer: {e}", file=sys.stderr)
            errors += 1
        except Exception as e:
            print(f"Worker ERROR during the call: {e}", file=sys.stderr)
            errors += 1
    results_queue.put((requests_sent, errors))

def get_total_processed_count(mode, ns_host, ns_port):
    try:
        if ns_host and ns_port:
            ns = Pyro4.locateNS(host=ns_host, port=ns_port)
        else:
            ns = Pyro4.locateNS()
        load_balancer = Pyro4.Proxy(ns.lookup(DEFAULT_PYRO_LOADBALANCER))
        load_balancer._pyroTimeout = 5 # Timeout for statistic call
        if mode == 'add_insult':
            return load_balancer.get_processed_count_service()
        elif mode == 'filter_text':
            return load_balancer.get_processed_count_filter()
        else:
            return -1
    except Pyro4.errors.NamingError:
        print(f"ERROR: LoadBalancer '{DEFAULT_PYRO_LOADBALANCER}' not found. Make sure it is running.", file=sys.stderr)
        return -1
    except Exception as e:
        print(f"ERROR: Unable to get processed requests from the LoadBalancer: {e}", file=sys.stderr)
        return -1

def run_stress_test(mode, duration, concurrency, ns_host, ns_port):
    print(f"Starting Pyro stress test for '{mode}' with {concurrency} processes for {duration} seconds.")
    print(f"Load Balancer name: {DEFAULT_PYRO_LOADBALANCER}")
    print(f"Duration: {duration} seconds")
    print(f"Concurrency: {concurrency} processes")
    print("-" * 30)

    results_queue = Queue()
    processes = []

    start_test_time = time.time()
    # Start worker processes
    print("Starting worker processes...")
    for _ in range(concurrency):
        p = Process(target=worker_request, args=(duration, results_queue, ns_host, ns_port, mode))
        processes.append(p)
        p.start()

    # Wait for all processes to finish
    print("Waiting for processes to finish...")
    for p in processes:
        p.join()

    end_test_time = time.time()
    actual_duration = end_test_time - start_test_time

    total_client_requests_sent = 0
    total_error_count = 0
    while not results_queue.empty():
        requests_sent, errors = results_queue.get()
        total_client_requests_sent += requests_sent
        total_error_count += errors

    print("\n--- Test Results ---")
    print(f"Pyro Stress Test Finished")
    print(f"Actual test duration: {actual_duration:.2f} seconds")
    print(f"Total client requests sent: {total_client_requests_sent}")
    print(f"Total client errors: {total_error_count}")

    server_processed_count = get_total_processed_count(mode, ns_host, ns_port)
    if server_processed_count >= 0: # Validate the server processed count
        print(f"Total server processed requests: {server_processed_count}")
    else:
        print("Server performance: N/A (unable to retrieve total processed requests count)")

    if actual_duration > 0:
        client_throughput = total_client_requests_sent / actual_duration
        print(f"Client throughput (requests/second): {client_throughput:.2f}")

        if server_processed_count >= 0:
             server_throughput = server_processed_count / actual_duration
             print(f"Server throughput (requests/second): {server_throughput:.2f}")
    else:
        print("Performance: N/A (duration too short)")

    print("-" * 30)
    return None

# --- Argument Handling and Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Script de prova d'estrès (Multiprocessament) per a serveis Pyro amb LoadBalancer")
    parser.add_argument("mode", choices=['add_insult', 'filter_text'],
                        help="La funcionalitat a provar ('add_insult' o 'filter_text')")
    parser.add_argument("-d", "--duration", type=int, default=DEFAULT_DURATION,
                        help=f"Durada de la prova en segons (per defecte: {DEFAULT_DURATION})")
    parser.add_argument("-c", "--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                        help=f"Nombre de processos concurrents (per defecte: {DEFAULT_CONCURRENCY})")
    parser.add_argument("--ns-host", type=str, default=None, help="Host del Name Server (per defecte: localitzar via broadcast)")
    parser.add_argument("--ns-port", type=int, default=None, help="Port del Name Server (per defecte: localitzar via broadcast)")


    args = parser.parse_args()

    run_stress_test(args.mode, args.duration, args.concurrency, args.ns_host, args.ns_port)