import pika
import time
from multiprocessing import Process, Queue
import random
import argparse
import sys
import os

import redis

# --- Configuration  ---
DEFAULT_RABBIT_HOST = 'localhost'
DEFAULT_INSULT_EXCHANGE = 'insults_exchange'    # Default RabbitMQ queue for adding insults
DEFAULT_TEXT_QUEUE = 'text_queue'           # Default RabbitMQ queue for filtering work
DEFAULT_CONCURRENCY = 5                    # Default number of concurrent processes/clients
REDIS_COUNTER = "COUNTER"                  # Redis key for counting processed messages

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
def worker_add_insult(host, exchange_name, results_queue, n_msg):
    local_request_count = 0
    local_error_count = 0
    connection = None
    pid = os.getpid()
    try:
        connection_params = pika.ConnectionParameters(host)
        connection = pika.BlockingConnection(connection_params)
        channel = connection.channel()
        channel.exchange_declare(exchange=exchange_name, exchange_type='fanout')
        while local_request_count < n_msg:
            try:
                insult = random.choice(INSULTS_TO_ADD) + str(random.randint(1, 10000))
                channel.basic_publish(exchange=exchange_name, routing_key='', body=insult.encode('utf-8'))
                local_request_count += 1
            except pika.exceptions.AMQPConnectionError as e:
                 print(f"[Process {pid}] Connection error sending insult: {e}", file=sys.stderr)
                 local_error_count += 1
                 break
    except Exception as e:
        print(f"[Process {pid}] Serious error establishing connection/channel (add_insult): {e}", file=sys.stderr)
        local_error_count += 1
    finally:
        # Send results back to the main process via the queue
        results_queue.put((local_request_count, local_error_count))
        if connection and connection.is_open:
            connection.close()


def worker_filter_text(host, queue_name, results_queue, n_msg):
    local_request_count = 0
    local_error_count = 0
    connection = None
    pid = os.getpid()
    try:
        connection_params = pika.ConnectionParameters(host)
        connection = pika.BlockingConnection(connection_params)
        channel = connection.channel()
        channel.queue_declare(queue=queue_name)
        while local_request_count < n_msg:
            try:
                text = random.choice(TEXTS_TO_FILTER)
                channel.basic_publish(exchange='', routing_key=queue_name, body=text.encode('utf-8'))
                local_request_count += 1
            except pika.exceptions.AMQPConnectionError as e:
                 print(f"[Process {pid}] Connection error sending text: {e}", file=sys.stderr)
                 local_error_count += 1
                 break
    except Exception as e:
        print(f"[Process {pid}] Serious error establishing connection/channel (filter_text): {e}", file=sys.stderr)
        local_error_count += 1
    finally:
        # Send results back
        results_queue.put((local_request_count, local_error_count))
        if connection and connection.is_open:
            connection.close()

# --- Main Test Function ---
def run_stress_test(mode, host, insult_exchange, work_queue, messages, num_service_instances):
    print(f"Starting stress test (RabbitMQ) in mode '{mode}'...")
    print(f"RabbitMQ Host: {host}")
    print(f"Insults Exchange: {insult_exchange}")
    print(f"Filter Queue: {work_queue}")
    print(f"Number of messages to send: {messages}")
    print("-" * 30)

    # Worker selection (for RabbitMQ message sending)
    if mode == 'add_insult':
        worker_function = worker_add_insult
        target_queue_name = insult_exchange
    elif mode == 'filter_text':  # Use 'filter_text' to match service logic intent
        worker_function = worker_filter_text  # This worker sends text to the work_queue
        target_queue_name = work_queue
    else:
        print(f"Error: Mode '{mode}' unrecognized. Options: 'add_insult', 'filter_text'.", file=sys.stderr)
        exit(1)

    try:
        redis_client = redis.Redis(db=0, decode_responses=True,
                                   socket_connect_timeout=5, socket_timeout=5)
    except redis.exceptions.ConnectionError as e:
        print(f"Severe error connecting to Redis in run_stress_test: {e}", file=sys.stderr)
        exit(1)

    n_messages = messages // DEFAULT_CONCURRENCY
    results_queue = Queue()
    processes = []
    start_time = time.time()

    # --- Phase 1: Generate load with RabbitMQ ---
    print("Starting processes to send load to RabbitMQ...")
    for _ in range(DEFAULT_CONCURRENCY):
        process = Process(target=worker_function, args=(host, target_queue_name, results_queue, n_messages))
        processes.append(process)
        process.start()

    print("Waiting for load processes to finish...")
    for process in processes:
        process.join()  # Wait for each process to complete

    actual_duration_client = time.time() - start_time

    # Collect local results (messages sent by this test)
    total_sent_count = 0
    total_client_errors = 0
    while not results_queue.empty():
        req, err = results_queue.get()
        total_sent_count += req
        total_client_errors += err

    # We wait for the instances of the service to finish processing all the messages.
    total_messages = n_messages * DEFAULT_CONCURRENCY
    while int(redis_client.get(REDIS_COUNTER)) < total_messages:
        time.sleep(0.001)

    actual_duration_server = time.time() - start_time
    print("-" * 30)

    # --- Phase 2: Get statistics from the service ---
    total_processed_count = int(redis_client.get(REDIS_COUNTER))

    # --- Phase 3: Display results ---
    print("-" * 30)
    print("Stress Test (Redis with Multiprocessing) Finished")
    print(f"Total time sending requests: {actual_duration_client:.3f} seconds")
    print(f"Total time processing requests: {actual_duration_server:.3f} seconds")


    print("--- Client Results (Requests Sent by Stress Test Processes) ---")
    print(f"Total commands sent (client success): {total_sent_count}")
    print(f"Total errors (on client during sending): {total_client_errors}")

    if actual_duration_server > 0:
        client_throughput = total_sent_count / actual_duration_client
        print(f"Client sending throughput (messages/second): {client_throughput:.3f}")
    else:
        print("Client throughput: N/A (duration too short)")

    print("\n--- Statistics (Processed Counts) ---")
    if total_processed_count != 0:
        print(f"Server processed count: {total_processed_count}")
        if actual_duration_server > 0:
            server_throughput = total_processed_count / actual_duration_server
            print(f"Server throughput (requests/second): {server_throughput:.3f}")
    else:
        print("Could not retrieve service statistics.")

    print("\n--- Statistics (Per service instance throughput) ---")
    if total_processed_count != 0:
        if actual_duration_server > 0:
            service_throughput = total_processed_count / actual_duration_server
            print(f"Per server processing throughput (requests/second): {service_throughput/num_service_instances:.3f}")

    print("-" * 30)

# --- Argument Parsing and Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stress Test Script for Insult Services via RabbitMQ ")
    parser.add_argument("mode", choices=['add_insult', 'filter_text'],
                        help="The functionality to test ('add_insult' or 'filter_text')")
    parser.add_argument("--host", default=DEFAULT_RABBIT_HOST,
                        help=f"RabbitMQ server host (default: {DEFAULT_RABBIT_HOST})")
    parser.add_argument("--insult-exchange", default=DEFAULT_INSULT_EXCHANGE,
                        help=f"RabbitMQ exchange name for adding insults (default: {DEFAULT_INSULT_EXCHANGE})")
    parser.add_argument("--work-queue", default=DEFAULT_TEXT_QUEUE,
                        help=f"RabbitMQ queue name for filtering texts (default: {DEFAULT_TEXT_QUEUE})")
    parser.add_argument("-m", "--messages", type=int, required=True,
                        help=f"Number of messages to send")
    parser.add_argument("-n", "--num-instances", type=int, default=1, required=True,
                        help="Number of service instances to query for statistics (required)")

    args = parser.parse_args()

    # Call the main function with the parsed arguments
    run_stress_test(args.mode, args.host, args.insult_exchange, args.work_queue, args.messages, args.num_instances)