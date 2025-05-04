# rabbitmq_stress_test_mp_with_stats.py
import pika
import time
import multiprocessing
from multiprocessing import Process, Queue
import random
import argparse
import sys
import os
import Pyro4

# --- Configuration  ---
DEFAULT_RABBIT_HOST = 'localhost'
DEFAULT_INSULT_QUEUE = 'Insults_channel'    # Default RabbitMQ queue for adding insults
DEFAULT_WORK_QUEUE = 'Work_queue'           # Default RabbitMQ queue for filtering work
DEFAULT_PYRO_NAME = 'rabbit.counter'        # Default Pyro name for statistics
DEFAULT_DURATION = 10                       # Default test duration in seconds
DEFAULT_CONCURRENCY = 10                    # Default number of concurrent processes/clients

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


# --- Worker Functions (Send load to RabbitMQ) --
def worker_add_insult(host, queue_name, results_queue, end_time):
    local_request_count = 0
    local_error_count = 0
    connection = None
    pid = os.getpid()
    try:
        connection_params = pika.ConnectionParameters(host)
        connection = pika.BlockingConnection(connection_params)
        channel = connection.channel()
        channel.queue_declare(queue=queue_name)
        while time.time() < end_time:
            try:
                insult = random.choice(INSULTS_TO_ADD) + str(random.randint(1, 10000))
                channel.basic_publish(exchange='', routing_key=queue_name, body=insult.encode('utf-8'))
                local_request_count += 1
            except pika.exceptions.AMQPConnectionError as e:
                 print(f"[Process {pid}] Connection error sending insult: {e}", file=sys.stderr)
                 local_error_count += 1
                 break
            except Exception as e:
                local_error_count += 1
    except Exception as e:
        print(f"[Process {pid}] Serious error establishing connection/channel (add_insult): {e}", file=sys.stderr)
        local_error_count += 1
    finally:
        # Send results back to the main process via the queue
        results_queue.put((local_request_count, local_error_count))
        if connection and connection.is_open:
            connection.close()


def worker_filter_text(host, queue_name, results_queue, end_time):
    local_request_count = 0
    local_error_count = 0
    connection = None
    pid = os.getpid()
    try:
        connection_params = pika.ConnectionParameters(host)
        connection = pika.BlockingConnection(connection_params)
        channel = connection.channel()
        channel.queue_declare(queue=queue_name)
        while time.time() < end_time:
            try:
                text = random.choice(TEXTS_TO_FILTER)
                channel.basic_publish(exchange='', routing_key=queue_name, body=text.encode('utf-8'))
                local_request_count += 1
            except pika.exceptions.AMQPConnectionError as e:
                 print(f"[Process {pid}] Connection error sending text: {e}", file=sys.stderr)

                 local_error_count += 1
                 break
            except Exception as e:
                local_error_count += 1
    except Exception as e:
        print(f"[Process {pid}] Serious error establishing connection/channel (filter_text): {e}", file=sys.stderr)
        local_error_count += 1
    finally:
        # Send results back
        results_queue.put((local_request_count, local_error_count))
        if connection and connection.is_open:
            connection.close()

# --- Main Test Function ---
def run_stress_test(mode, host, insult_queue, work_queue, pyro_name, duration, concurrency):
    """Runs the stress test (RabbitMQ load generation) and gets statistics via Pyro."""
    print(f"Starting stress test (RabbitMQ+Pyro with Multiprocessing) in mode '{mode}'...")
    print(f"RabbitMQ Host: {host}")
    print(f"Insults Queue: {insult_queue}")
    print(f"Filter Queue: {work_queue}")
    print(f"Pyro Name (Statistics): {pyro_name}") # New
    print(f"Duration: {duration} seconds")
    print(f"Concurrency: {concurrency} processes")
    print("-" * 30)

    # Worker selection (for RabbitMQ message sending)
    if mode == 'add_insult':
        worker_function = worker_add_insult
        target_queue_name = insult_queue
    elif mode == 'filter_service':  # Use 'filter_service' to match service logic intent
        worker_function = worker_filter_text  # This worker sends text to the work_queue
        target_queue_name = work_queue
    else:
        print(f"Error: Mode '{mode}' unrecognized. Options: 'add_insult', 'filter_service'.", file=sys.stderr)
        exit(1)

    results_queue = Queue()
    processes = []
    start_time = time.time()
    end_time = start_time + duration

    # --- Phase 1: Generate load with RabbitMQ ---
    print("Starting processes to send load to RabbitMQ...")
    for _ in range(concurrency):
        process = Process(target=worker_function, args=(host, target_queue_name, results_queue, end_time))
        processes.append(process)
        process.start()

    print("Waiting for load processes to finish...")
    for process in processes:
        process.join()  # Wait for each process to complete

    # Collect local results (messages sent by this test)
    total_sent_count = 0
    total_client_errors = 0
    while not results_queue.empty():
        req, err = results_queue.get()
        total_sent_count += req
        total_client_errors += err

    actual_duration = time.time() - start_time
    print("Load processes finished.")
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
        print(f"Error: Pyro service named '{pyro_name}' not found. Ensure the Name Server is running and the service is registered.", file=sys.stderr)
    except AttributeError:
         print(f"Error: The remote Pyro object ('{pyro_name}') does not have the exposed method 'get_processed_count'.", file=sys.stderr)
         print("Ensure the method is correctly defined with @Pyro4.expose in InsultService.py.", file=sys.stderr)
    except Exception as e:
        print(f"Error connecting or calling the Pyro service ('{pyro_name}'): {e}", file=sys.stderr)
        print("Ensure the InsultService.py service is running and has registered '{pyro_name}'.", file=sys.stderr)

        # --- Phase 3: Display results ---
    print("-" * 30)
    print(f"Stress Test (RabbitMQ+Pyro, Mode: {mode}) Finished")
    print(f"Total time: {actual_duration:.2f} seconds")
    print("--- Client Results (Stress Test) ---")
    print(f"Messages sent attempt (client success): {total_sent_count}")
    print(f"Errors (on client side): {total_client_errors}")

    if actual_duration > 0:
        client_throughput = total_sent_count / actual_duration
        print(f"Client sending throughput (messages/second): {client_throughput:.2f}")
    else:
        print("Client throughput: N/A (duration too short)")

    print("--- Service Statistics (via Pyro) ---")
    if processed_count_service != -1:
        print(f"Requests processed by the service: {processed_count_service}")
        if actual_duration > 0:
            server_throughput = processed_count_service / actual_duration
            print(f"Server throughput (requests/second): {server_throughput:.2f}")
    else:
        print("Could not retrieve service statistics via Pyro.")
    print("-" * 30)

# --- Argument Parsing and Execution ---
if __name__ == "__main__":
    # TODO is necessary?
    multiprocessing.freeze_support()

    parser = argparse.ArgumentParser(description="Stress Test Script (RabbitMQ+Pyro) for InsultService")
    parser.add_argument("mode", choices=['add_insult', 'filter_service'],
                        help="The functionality to test ('add_insult' or 'filter_service')")
    parser.add_argument("--host", default=DEFAULT_RABBIT_HOST,
                        help=f"RabbitMQ server host (default: {DEFAULT_RABBIT_HOST})")
    parser.add_argument("--insult-queue", default=DEFAULT_INSULT_QUEUE,
                        help=f"RabbitMQ queue name for adding insults (default: {DEFAULT_INSULT_QUEUE})")
    parser.add_argument("--work-queue", default=DEFAULT_WORK_QUEUE,
                        help=f"RabbitMQ queue name for filtering texts (default: {DEFAULT_WORK_QUEUE})")
    parser.add_argument("--pyro-name", default=DEFAULT_PYRO_NAME,
                        help=f"Pyro object name for getting statistics (default: {DEFAULT_PYRO_NAME})")
    parser.add_argument("-d", "--duration", type=int, default=DEFAULT_DURATION,
                        help=f"Test duration in seconds (default: {DEFAULT_DURATION})")
    parser.add_argument("-c", "--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                        help=f"Number of concurrent processes (default: {DEFAULT_CONCURRENCY})")

    args = parser.parse_args()

    # Call the main function with the parsed arguments
    run_stress_test(args.mode, args.host, args.insult_queue, args.work_queue, args.pyro_name, args.duration,args.concurrency)