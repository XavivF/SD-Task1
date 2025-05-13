# stress_test.py
import pika
import time
import random
import argparse
import Pyro4
import config
from multiprocessing import Process, Queue as MPQueue  # Per evitar conflicte amb pika.Queue

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


def text_sender_worker(host_url, queue_name, results_mp_queue, end_time):
    """Envia textos a la cua de filtratge."""
    sent_count = 0
    error_count = 0
    connection = None
    try:
        connection = pika.BlockingConnection(pika.URLParameters(host_url))
        channel = connection.channel()
        channel.queue_declare(queue=queue_name, durable=True)  # Assegura que existeix

        while time.time() < end_time:
            text = random.choice(TEXTS_TO_SEND_FOR_FILTERING)
            try:
                channel.basic_publish(exchange='', routing_key=queue_name, body=text,
                                      properties=pika.BasicProperties(delivery_mode=2))
                sent_count += 1
            except pika.exceptions.AMQPConnectionError:
                error_count += 1
                # Reconnect logic could be added here for longer tests
                print("StressTest Worker: Connection error, trying to reconnect...")
                try:
                    connection = pika.BlockingConnection(pika.URLParameters(host_url))
                    channel = connection.channel()
                    channel.queue_declare(queue=queue_name, durable=True)
                except Exception:
                    print("StressTest Worker: Reconnect failed. Exiting worker.")
                    break  # Surt del bucle while si la reconnexió falla
            except Exception:
                error_count += 1
            # No sleep, send as fast as possible

    except Exception as e:
        print(f"StressTest Worker Error: {e}")
        error_count += sent_count  # Assume all failed if major error
        sent_count = 0
    finally:
        if connection and connection.is_open:
            connection.close()
        results_mp_queue.put({'sent': sent_count, 'errors': error_count})


def run_stress_test(duration_seconds, concurrency_level):
    print(f"Starting Stress Test for InsultFilter system...")
    print(f"Duration: {duration_seconds}s, Concurrency (senders): {concurrency_level}")
    print(f"Target RabbitMQ: {config.RABBITMQ_URL}, Text Queue: {config.TEXT_QUEUE_NAME}")
    print(f"Pyro NS for stats: {config.PYRO_NS_HOST}:{config.PYRO_NS_PORT}")
    print("-" * 30)

    results_mp_queue = MPQueue()
    sender_processes = []
    start_time = time.time()
    end_time = start_time + duration_seconds

    # --- Fase 1: Generar càrrega (enviar textos) ---
    print("Starting text sender processes...")
    for _ in range(concurrency_level):
        p = Process(target=text_sender_worker,
                    args=(config.RABBITMQ_URL, config.TEXT_QUEUE_NAME, results_mp_queue, end_time),
                    daemon=True)
        sender_processes.append(p)
        p.start()

    # Esperar que els processos de càrrega acabin (o el temps s'esgoti)
    # Ells s'aturaran per end_time, però fem join per esperar la seva finalització neta.
    for p in sender_processes:
        p.join()

    actual_duration = time.time() - start_time
    print("Text sender processes finished.")

    total_texts_sent_by_stress_test = 0
    total_send_errors_by_stress_test = 0
    while not results_mp_queue.empty():
        res = results_mp_queue.get_nowait()
        total_texts_sent_by_stress_test += res.get('sent', 0)
        total_send_errors_by_stress_test += res.get('errors', 0)

    print(
        f"Stress test client sent {total_texts_sent_by_stress_test} texts with {total_send_errors_by_stress_test} errors.")
    if actual_duration > 0:
        client_throughput = total_texts_sent_by_stress_test / actual_duration
        print(f"Client sending throughput: {client_throughput:.2f} texts/second.")

    print("-" * 30)

    # --- Fase 2: Obtenir estadístiques del ScalerManager via Pyro ---
    scaler_proxy = None
    try:
        ns = Pyro4.locateNS(host=config.PYRO_NS_HOST, port=config.PYRO_NS_PORT)
        scaler_uri = ns.lookup(config.PYRO_SCALER_MANAGER_NAME)
        scaler_proxy = Pyro4.Proxy(scaler_uri)
        print(f"Connected to ScalerManager: {scaler_uri}")
    except Exception as e:
        print(f"Could not connect to ScalerManager via Pyro: {e}")

    if scaler_proxy:
        print("Waiting a bit for system to process remaining messages...")
        time.sleep(5 + config.SCALING_INTERVAL)  # Espera un interval d'escalat + marge

        try:
            final_stats = scaler_proxy.get_scaler_stats()
            print("\n--- ScalerManager Final Statistics ---")
            for key, value in final_stats.items():
                print(f"  {key}: {value}")

            # Podem calcular un throughput del servidor basat en el comptador de Redis
            total_processed_redis = final_stats.get("total_filter_processed_redis_counter", 0)
            if isinstance(total_processed_redis, str):  # Si és un missatge d'error
                total_processed_redis = 0

            # Idealment, agafaríem un comptador inicial i un final.
            # Per simplicitat, si el test és l'únic que envia, podem aproximar.
            # Però és millor si el test registra el comptador abans i després.
            # Per ara, mostrem el total acumulat.
            # Per a un throughput real del servidor durant el test,
            # necessitaríem `total_processed_redis_after - total_processed_redis_before`.

            if actual_duration > 0 and total_processed_redis > 0:  # Assumeix que el comptador era 0 abans
                # Això és el throughput global, no només del test si el sistema ja estava funcionant.
                # Per un throughput del test, necessitem comptador_abans i comptador_després.
                # print(f"  Approx Server throughput (based on Redis total): {total_processed_redis / actual_duration:.2f} reqs/second")
                pass


        except Exception as e:
            print(f"Error getting stats from ScalerManager: {e}")

    print("-" * 30)
    print("Stress Test Finished.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stress Test for Dynamic Insult Filter System")
    parser.add_argument("-d", "--duration", type=int, default=30, help="Test duration in seconds.")
    parser.add_argument("-c", "--concurrency", type=int, default=5, help="Number of concurrent text sender processes.")
    args = parser.parse_args()

    run_stress_test(args.duration, args.concurrency)