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
DEFAULT_INSULT_EXCHANGE = 'insults_exchange'    # Default RabbitMQ queue for adding insults
DEFAULT_TEXT_QUEUE = 'text_queue'           # Default RabbitMQ queue for filtering work
DEFAULT_PYRO_NAME_SERVICE = 'rabbit.service'        # Default Pyro name for statistics
DEFAULT_PYRO_NAME_FILTER = 'rabbit.filter'          # Default Pyro name for filter service
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
def worker_add_insult(host, exchange_name, results_queue, end_time):
    local_request_count = 0
    local_error_count = 0
    connection = None
    pid = os.getpid()
    try:
        connection_params = pika.ConnectionParameters(host)
        connection = pika.BlockingConnection(connection_params)
        channel = connection.channel()
        channel.exchange_declare(exchange=exchange_name, exchange_type='fanout')
        while time.time() < end_time:
            try:
                insult = random.choice(INSULTS_TO_ADD) + str(random.randint(1, 10000))
                channel.basic_publish(exchange=exchange_name, routing_key='', body=insult.encode('utf-8'))
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
def run_stress_test(mode, host, insult_queue, work_queue, duration, concurrency, num_service_instances):
    if mode == "filter_service": pyro_name = DEFAULT_PYRO_NAME_FILTER
    if mode == "add_insult": pyro_name = DEFAULT_PYRO_NAME_SERVICE

    print(f"Starting stress test (RabbitMQ+Pyro with Multiprocessing) in mode '{mode}'...")
    print(f"RabbitMQ Host: {host}")
    print(f"Insults Queue: {insult_queue}")
    print(f"Filter Queue: {work_queue}")
    print(f"Pyro Name (Statistics): {pyro_name}")
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
    total_processed_count = 0
    # Get stats from InsultService instances
    for i in range(1, num_service_instances + 1):
        service_instance_name = f"{pyro_name}.{i}"
        try:
            server_proxy = Pyro4.Proxy(f"PYRONAME:{service_instance_name}")
            server_proxy._pyroTimeout = 10
            total_processed_count += server_proxy.get_processed_count()
            print(f"Stats retrieved from {service_instance_name}.")
        except Pyro4.errors.NamingError:
            print(f"Warning: Instance '{service_instance_name}' not found.", file=sys.stderr)
        except Exception as e:
            print(f"Error retrieving stats from {service_instance_name}: {e}", file=sys.stderr)

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
    if total_processed_count != 0:
        print(f"Requests processed by the service: {total_processed_count}")
        if actual_duration > 0:
            server_throughput = total_processed_count / actual_duration
            print(f"Server throughput (requests/second): {server_throughput:.2f}")
    else:
        print("Could not retrieve service statistics via Pyro.")
    print("-" * 30)

# --- Argument Parsing and Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stress Test Script (RabbitMQ+Pyro) for InsultService")
    parser.add_argument("mode", choices=['add_insult', 'filter_service'],
                        help="The functionality to test ('add_insult' or 'filter_service')")
    parser.add_argument("--host", default=DEFAULT_RABBIT_HOST,
                        help=f"RabbitMQ server host (default: {DEFAULT_RABBIT_HOST})")
    parser.add_argument("--insult-queue", default=DEFAULT_INSULT_EXCHANGE,
                        help=f"RabbitMQ queue name for adding insults (default: {DEFAULT_INSULT_EXCHANGE})")
    parser.add_argument("--work-queue", default=DEFAULT_TEXT_QUEUE,
                        help=f"RabbitMQ queue name for filtering texts (default: {DEFAULT_TEXT_QUEUE})")
    parser.add_argument("-d", "--duration", type=int, default=DEFAULT_DURATION,
                        help=f"Test duration in seconds (default: {DEFAULT_DURATION})")
    parser.add_argument("-c", "--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                        help=f"Number of concurrent processes (default: {DEFAULT_CONCURRENCY})")
    parser.add_argument("-n", "--num-instances", type=int, default=1, required=True,
                        help="Number of service instances to query for statistics (required)")

    args = parser.parse_args()

    # Call the main function with the parsed arguments
    run_stress_test(args.mode, args.host, args.insult_queue, args.work_queue, args.duration, args.concurrency, args.num_instances)