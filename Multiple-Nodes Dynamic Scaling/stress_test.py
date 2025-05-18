import pika
import time
import random
import argparse
import Pyro4
import config
import math
from multiprocessing import Process, Queue as MPQueue
import sys # Importem sys per sortir si falta el NS

# --- Dades de Prova ---
INSULTS_TO_PUBLISH = ["tonto", "lleig", "boig", "idiota", "estúpid", "inútil", "desastre", "fracassat", "covard",
                      "mentider",
                      "beneit", "capsigrany", "ganàpia", "nyicris", "gamarús", "bocamoll", "murri", "dropo", "bleda",
                      "xitxarel·lo"]
TEXTS_TO_SEND_FOR_FILTERING = [
    "ets tonto i estas boig", "ets molt inútil", "ets una mica desastre", "ets massa fracassat",
    "ets un poc covard", "ets molt molt mentider", "ets super estúpid", "ets bastant idiota",
    "Ets un beneit de cap a peus.", "No siguis capsigrany i pensa abans de parlar.",
    "Aquest ganàpia no sap el que fa.", "Sempre estàs tan nyicris.", "Quin gamarús !",
    "No siguis bocamoll.", "És un murri.", "No siguis dropo.", "Ets una mica bleda.",
    "Aquest xitxarel·lo es pensa que ho sap tot.", "Un text normal sense res lleig."
]

FIXED_CONCURRENCY_LEVEL = 5 # Nombre fix de processos concurrents

def create_rabbitmq_connection(host_url):
    """Helper function to create a RabbitMQ connection."""
    try:
        # Use a shorter blocked_connection_timeout for faster detection
        connection = pika.BlockingConnection(pika.URLParameters(f"{host_url}?blocked_connection_timeout=10"))
        return connection
    except pika.exceptions.AMQPConnectionError:
        return None

def text_sender_worker(host_url, queue_name, results_mp_queue, num_messages_to_send):
    """Envia un nombre fix de textos a la cua de filtratge."""
    sent_count = 0
    error_count = 0
    connection = None
    channel = None

    while connection is None:
         connection = create_rabbitmq_connection(host_url)
         if connection is None:
             time.sleep(1)

    try:
        channel = connection.channel()
        channel.queue_declare(queue=queue_name, durable=True)

        for _ in range(num_messages_to_send):
            text = random.choice(TEXTS_TO_SEND_FOR_FILTERING)
            try:
                channel.basic_publish(exchange='', routing_key=queue_name, body=text)
                sent_count += 1
            except pika.exceptions.AMQPError:
                error_count += 1
                if connection and connection.is_open:
                    try: connection.close()
                    except Exception: pass
                connection = None
                channel = None
                reconnect_attempts = 0
                while connection is None and reconnect_attempts < 5:
                     connection = create_rabbitmq_connection(host_url)
                     if connection:
                          channel = connection.channel()
                          channel.queue_declare(queue=queue_name, durable=True)
                     else:
                          reconnect_attempts += 1
                          time.sleep(1)
                if connection is None:
                    print("StressTest Text Worker: Persistent connection failure. Exiting worker.")
                    break

            except Exception:
                error_count += 1


    except Exception as e:
        print(f"StressTest Text Worker Major Error: {e}")
        error_count += (num_messages_to_send - sent_count)

    finally:
        if connection and connection.is_open:
            connection.close()
        results_mp_queue.put({'type': 'filter', 'sent': sent_count, 'errors': error_count})


def insult_sender_worker(host_url, queue_name, results_mp_queue, num_messages_to_send):
    """Envia un nombre fix d'insults a la cua de processament d'insults."""
    sent_count = 0
    error_count = 0
    connection = None
    channel = None

    while connection is None:
         connection = create_rabbitmq_connection(host_url)
         if connection is None:
             time.sleep(1)

    try:
        channel = connection.channel()
        channel.queue_declare(queue=queue_name, durable=True)

        for _ in range(num_messages_to_send):
            insult = random.choice(INSULTS_TO_PUBLISH) + "_" + str(random.randint(1000, 9999))
            try:
                channel.basic_publish(exchange='', routing_key=queue_name, body=insult)
                sent_count += 1
            except pika.exceptions.AMQPError:
                error_count += 1
                if connection and connection.is_open:
                    try: connection.close()
                    except Exception: pass
                connection = None
                channel = None
                reconnect_attempts = 0
                while connection is None and reconnect_attempts < 5:
                     connection = create_rabbitmq_connection(host_url)
                     if connection:
                         channel = connection.channel()
                         channel.queue_declare(queue=queue_name, durable=True)
                     else:
                         reconnect_attempts += 1
                         time.sleep(1)
                if connection is None:
                    print("StressTest Insult Worker: Persistent connection failure. Exiting worker.")
                    break

            except Exception:
                error_count += 1

    except Exception as e:
        print(f"StressTest Insult Worker Major Error: {e}")
        error_count += (num_messages_to_send - sent_count)
    finally:
        if connection and connection.is_open:
            connection.close()
        results_mp_queue.put({'type': 'insult', 'sent': sent_count, 'errors': error_count})


def get_redis_processed_count(scaler_proxy, test_type):
    """Gets the current processed count from Redis via the ScalerManager proxy."""
    try:
        stats = scaler_proxy.get_scaler_stats()
        if test_type == 'filter_text':
            # Need to access the nested structure correctly
            count_str = stats.get('filter_workers_pool', {}).get('filter_processed_redis_counter', '0')
        elif test_type == 'add_insult':
            # Need to access the nested structure correctly
             count_str = stats.get('insult_processor_pool', {}).get('insults_processed_redis_counter', '0')
        else:
            return 0 # Should not happen with argparse choices

        # Redis counters are typically integers stored as strings
        return int(count_str)
    except Exception as e:
        print(f"Error getting Redis processed count from ScalerManager: {e}")
        return -1 # Indicate an error


def run_stress_test(num_messages, test_type):
    print(f"Starting Stress Test for {test_type}...")
    print(f"Total messages to send: {num_messages}")
    print(f"Concurrency (senders): {FIXED_CONCURRENCY_LEVEL}")
    print(f"Target RabbitMQ: {config.RABBITMQ_URL}")
    print(f"Pyro NS for stats: {config.PYRO_NS_HOST}:{config.PYRO_NS_PORT}")
    print("-" * 30)

    # --- Connect to ScalerManager via Pyro to get initial count ---
    scaler_proxy = None
    try:
        ns = Pyro4.locateNS(host=config.PYRO_NS_HOST, port=config.PYRO_NS_PORT)
        scaler_uri = ns.lookup(config.PYRO_SCALER_MANAGER_NAME)
        scaler_proxy = Pyro4.Proxy(scaler_uri)
        print(f"Connected to ScalerManager: {scaler_uri}")
    except Exception as e:
        print(f"Could not connect to ScalerManager via Pyro: {e}")
        print("Please ensure the Pyro Name Server and ScalerManager are running.")
        sys.exit(1) # Exit if we can't connect to get initial stats

    # Reset Counter in Redis
    scaler_proxy.reset_counter()

    initial_processed_count = get_redis_processed_count(scaler_proxy, test_type)
    if initial_processed_count == -1:
         print("Failed to get initial processed count from Redis. Exiting.")
         sys.exit(1)
    print(f"Initial processed count in Redis ({test_type}): {initial_processed_count}")
    print("-" * 30)


    results_mp_queue = MPQueue()
    sender_processes = []


    # --- Fase 1: Generar càrrega (enviar missatges) ---
    print(f"Starting {test_type} sender processes...")

    worker_target = None
    queue_name = None
    if test_type == 'filter_text':
        worker_target = text_sender_worker
        queue_name = config.TEXT_QUEUE_NAME
    elif test_type == 'add_insult':
        worker_target = insult_sender_worker
        queue_name = config.INSULTS_PROCESSING_QUEUE_NAME
    else:
        print(f"Error: Unknown test type '{test_type}'. Exiting.")
        sys.exit(1)

    # Calculate messages per worker
    messages_per_worker = num_messages // FIXED_CONCURRENCY_LEVEL
    remainder = num_messages % FIXED_CONCURRENCY_LEVEL

    print(f"Distributing {num_messages} messages among {FIXED_CONCURRENCY_LEVEL} workers:")
    print(f"  {messages_per_worker} messages per worker.")
    if remainder > 0:
        print(f"  The last worker will send {messages_per_worker + remainder} messages.")

    start_time = time.time()  # Start time of the overall test

    # Start sender processes
    for i in range(FIXED_CONCURRENCY_LEVEL):
        messages_this_worker = messages_per_worker + (remainder if i == FIXED_CONCURRENCY_LEVEL - 1 else 0)
        p = Process(target=worker_target,
                    args=(config.RABBITMQ_URL, queue_name, results_mp_queue, messages_this_worker),
                    daemon=True)
        sender_processes.append(p)
        p.start()

    # Wait for all sender processes to complete sending
    for p in sender_processes:
        p.join()

    end_sending_time = time.time() # Time when all sender processes have finished
    print(f"{test_type} sender processes finished sending.")

    total_sent_by_stress_test = 0
    total_send_errors_by_stress_test = 0
    while not results_mp_queue.empty():
        try:
            res = results_mp_queue.get_nowait()
            total_sent_by_stress_test += res.get('sent', 0)
            total_send_errors_by_stress_test += res.get('errors', 0)
        except Exception:
            pass # Ignore if queue is empty unexpectedly


    print(f"Stress test client attempted to send {total_sent_by_stress_test + total_send_errors_by_stress_test} messages ({test_type}). Sent {total_sent_by_stress_test}, failed {total_send_errors_by_stress_test}.")

    if total_sent_by_stress_test == 0:
        print("No messages were successfully sent by the stress test client. Cannot measure worker throughput.")
        print("-" * 30)
        print(f"Stress Test ({test_type}) Finished.")
        sys.exit(0) # Exit gracefully if nothing was sent

    # --- Fase 2: Esperar que els treballadors processin els missatges enviats ---
    print(f"Waiting for workers to process {total_sent_by_stress_test} messages...")
    # Calculate the target processed count we expect
    target_processed_count = initial_processed_count + total_sent_by_stress_test

    current_processed_count = get_redis_processed_count(scaler_proxy, test_type)

    # Wait until the target processed count is reached
    while current_processed_count < target_processed_count:
        # Add a timeout to prevent infinite waiting if something goes wrong
        if time.time() - start_time > 600: # 10 minutes timeout
            print("\nWarning: Timeout waiting for messages to be processed.")
            print(f"Current processed count: {current_processed_count}, Target: {target_processed_count}")
            break # Exit the waiting loop

        time.sleep(0.01) # Poll frequently

        current_processed_count = get_redis_processed_count(scaler_proxy, test_type)
        if current_processed_count == -1:
            print("\nError: Lost connection to ScalerManager while waiting for processing. Exiting.")
            sys.exit(1)
        # Optional: print progress
        print(f"Processed: {current_processed_count}/{target_processed_count}...", end='\r')

    end_processing_wait_time = time.time()
    print(f"\nTarget processed count ({target_processed_count}) reached or timeout occurred.")
    print(f"Final processed count in Redis ({test_type}): {current_processed_count}")

    # --- Fase 3: Calcular el Throughput dels Treballadors ---
    processed_during_test = current_processed_count - initial_processed_count
    processing_duration = end_processing_wait_time - start_time

    print("-" * 30)
    print("--- Throughput Statistics ---")
    print(f"Messages processed during test ({test_type}): {processed_during_test}")
    print(f"Time taken to process messages: {processing_duration:.3f} seconds")
    print(f"Time taken to send messages: {end_sending_time - start_time:.3f} seconds")

    worker_throughput = 0
    if processing_duration > 0:
        worker_throughput = processed_during_test / processing_duration
        print(f"Worker Processing Throughput ({test_type}): {worker_throughput:.3f} messages/second.")
    else:
        print("Processing duration was zero or negative, cannot calculate worker throughput.")


    # --- Fase 4: Obtenir estadístiques finals del ScalerManager ---
    # We already have the scaler_proxy connection
    if scaler_proxy:
         # Wait a tiny bit more just in case final stats need a moment to update after counter
         time.sleep(1)
         try:
            final_stats = scaler_proxy.get_scaler_stats()
            print("\n--- ScalerManager Final Statistics ---")

            if test_type == 'filter_text':
                print("Relevant Pool Stats: filter_workers_pool")
                filter_stats = final_stats.get('filter_workers_pool', {})
                for key, value in filter_stats.items():
                     print(f"  {key}: {value}")
            elif test_type == 'add_insult':
                 print("Relevant Pool Stats: insult_processor_pool")
                 insult_stats = final_stats.get('insult_processor_pool', {})
                 for key, value in insult_stats.items():
                     print(f"  {key}: {value}")

            print("\nOverall Stats Summary:")
            for key, value in final_stats.items():
                if key not in ['filter_workers_pool', 'insult_processor_pool']:
                    print(f"  {key}: {value}")

         except Exception as e:
            print(f"Error getting final stats from ScalerManager: {e}")


    print("-" * 30)
    print(f"Stress Test ({test_type}) Finished.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stress Test for Dynamic Insult Filter System")
    parser.add_argument(
        "-m", "--messages",
        type=int,
        required=True, # Make this argument mandatory
        help="Total number of messages to send during the test."
    )
    parser.add_argument("mode", # Changed from --type to positional 'mode'
                        choices=['add_insult', 'filter_text'],
                        help="The functionality to test ('add_insult' or 'filter_text')")
    args = parser.parse_args()

    if args.messages <= 0:
        print("Error: --messages must be a positive integer.")
        sys.exit(1)



    run_stress_test(args.messages, args.mode)