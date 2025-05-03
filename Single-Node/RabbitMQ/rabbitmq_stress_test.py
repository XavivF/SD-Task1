# rabbitmq_stress_test_mp_with_stats.py
import pika
import time
import multiprocessing
from multiprocessing import Process, Queue
import random
import argparse
import sys
import os
import Pyro4 # Importació afegida

# --- Configuració ---
DEFAULT_RABBIT_HOST = 'localhost'
DEFAULT_INSULT_QUEUE = 'Insults_channel'
DEFAULT_WORK_QUEUE = 'Work_queue'
DEFAULT_PYRO_NAME = 'rabbit.counter' # Nom Pyro per defecte per a les estadístiques
DEFAULT_DURATION = 10  # Segons
DEFAULT_CONCURRENCY = 10 # Nombre de processos/clients concurrents

# --- Dades per a les proves ---
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


# --- Funcions Worker (No canvien, envien càrrega a RabbitMQ) ---
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
                 print(f"[Procés {pid}] Error de connexió enviant insult: {e}", file=sys.stderr)
                 local_error_count += 1
                 break
            except Exception as e:
                local_error_count += 1
    except Exception as e:
        print(f"[Procés {pid}] Error greu establint connexió/canal (add_insult): {e}", file=sys.stderr)
        local_error_count += 1
    finally:
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
                 print(f"[Procés {pid}] Error de connexió enviant text: {e}", file=sys.stderr)
                 local_error_count += 1
                 break
            except Exception as e:
                local_error_count += 1
    except Exception as e:
         print(f"[Procés {pid}] Error greu establint connexió/canal (filter_text): {e}", file=sys.stderr)
         local_error_count += 1
    finally:
        results_queue.put((local_request_count, local_error_count))
        if connection and connection.is_open:
            connection.close()

# --- Funció Principal del Test ---
# Afegim pyro_name com a argument
def run_stress_test(mode, host, insult_queue, work_queue, pyro_name, duration, concurrency):
    """Executa el stress test (RabbitMQ) i obté estadístiques via Pyro."""
    print(f"Iniciant stress test (RabbitMQ+Pyro amb Multiprocessing) en mode '{mode}'...")
    print(f"Host RabbitMQ: {host}")
    print(f"Cua Insults: {insult_queue}")
    print(f"Cua Filtre: {work_queue}")
    print(f"Nom Pyro (Estadístiques): {pyro_name}") # Nou
    print(f"Durada: {duration} segons")
    print(f"Concurrència: {concurrency} processos")
    print("-" * 30)

    # Selecció del worker (RabbitMQ)
    if mode == 'add_insult':
        worker_function = worker_add_insult
        target_queue_name = insult_queue
    elif mode == 'filter_service': # Canviat nom del mode per coherència
        worker_function = worker_filter_text # El worker envia text a la cua work_queue
        target_queue_name = work_queue
    else:
        print(f"Error: Mode '{mode}' no reconegut. Opcions: 'add_insult', 'filter_service'.", file=sys.stderr)
        return

    results_queue = Queue()
    processes = []
    start_time = time.time()
    end_time = start_time + duration

    # --- Fase 1: Generar càrrega amb RabbitMQ ---
    print("Iniciant processos per enviar càrrega a RabbitMQ...")
    for _ in range(concurrency):
        process = Process(target=worker_function, args=(host, target_queue_name, results_queue, end_time))
        processes.append(process)
        process.start()

    print("Esperant que els processos de càrrega acabin...")
    for process in processes:
        process.join()

    # Recollir resultats locals (missatges enviats pel test)
    total_sent_count = 0
    total_client_errors = 0
    while not results_queue.empty():
        req, err = results_queue.get()
        total_sent_count += req
        total_client_errors += err

    actual_duration = time.time() - start_time
    print("Processos de càrrega finalitzats.")
    print("-" * 30)

    # --- Fase 2: Obtenir estadístiques del servei via Pyro ---
    processed_count_service = -1 # Valor per defecte si falla la connexió Pyro
    print(f"Connectant a Pyro ({pyro_name}) per obtenir estadístiques del servei...")
    try:
        # Connectar al servei exposat per Pyro
        server_proxy = Pyro4.Proxy(f"PYRONAME:{pyro_name}")
        server_proxy._pyroTimeout = 10 # Timeout per a la connexió/crida Pyro

        # Cridar el mètode per obtenir el comptador
        processed_count_service = server_proxy.get_processed_count()
        print(f"Estadística rebuda del servei via Pyro.")

    except Pyro4.errors.NamingError:
        print(f"Error: No s'ha trobat el servei Pyro amb nom '{pyro_name}'. Assegura't que el Name Server funciona i el servei està registrat.", file=sys.stderr)
    except Exception as e:
        print(f"Error connectant o cridant el servei Pyro ({pyro_name}): {e}", file=sys.stderr)
        print("    >> Assegura't que el servei InsultService.py està funcionant i ha registrat 'rabbit.counter'.", file=sys.stderr)
        print("    >> Assegura't que el mètode 'get_processed_count' està correctament definit i exposat a InsultService.py.", file=sys.stderr)


    # --- Fase 3: Mostrar resultats ---
    print("-" * 30)
    print(f"Stress Test (RabbitMQ+Pyro, Mode: {mode}) Finalitzat")
    print(f"Temps total: {actual_duration:.2f} segons")
    print("--- Resultats del Client (Stress Test) ---")
    print(f"Missatges enviats (èxit client): {total_sent_count}")
    print(f"Errors (en client): {total_client_errors}")
    if actual_duration > 0:
        client_throughput = total_sent_count / actual_duration
        print(f"Throughput d'enviament client (missatges/segon): {client_throughput:.2f}")
    else:
        print("Throughput client: N/A (durada massa curta)")
    print("--- Estadístiques del Servei (via Pyro) ---")
    if processed_count_service != -1:
        service_throughput = processed_count_service / actual_duration
        print(f"Peticions processades pel servei: {processed_count_service}")
        print(f"Throughput de processament servidor (missatges processats/segon): {service_throughput:.2f}")
    else:
        print("No s'han pogut obtenir les estadístiques del servei via Pyro.")
    print("-" * 30)

    # Podries retornar el throughput del client o una tupla amb més dades si cal
    return client_throughput if actual_duration > 0 else 0

# --- Gestió d'Arguments i Execució ---
if __name__ == "__main__":
    multiprocessing.freeze_support()

    parser = argparse.ArgumentParser(description="Script de Stress Test (RabbitMQ+Pyro) per a InsultService")
    parser.add_argument("mode", choices=['add_insult', 'filter_service'], # Canviat 'filter_text' a 'filter_service'
                        help="La funcionalitat a provar ('add_insult' o 'filter_service')")
    parser.add_argument("--host", default=DEFAULT_RABBIT_HOST,
                        help=f"Host del servidor RabbitMQ (defecte: {DEFAULT_RABBIT_HOST})")
    parser.add_argument("--insult-queue", default=DEFAULT_INSULT_QUEUE,
                        help=f"Nom de la cua RabbitMQ per afegir insults (defecte: {DEFAULT_INSULT_QUEUE})")
    parser.add_argument("--work-queue", default=DEFAULT_WORK_QUEUE,
                        help=f"Nom de la cua RabbitMQ per filtrar textos (defecte: {DEFAULT_WORK_QUEUE})")
    parser.add_argument("--pyro-name", default=DEFAULT_PYRO_NAME, # Nou argument
                        help=f"Nom de l'objecte Pyro per obtenir estadístiques (defecte: {DEFAULT_PYRO_NAME})")
    parser.add_argument("-d", "--duration", type=int, default=DEFAULT_DURATION,
                        help=f"Durada del test en segons (defecte: {DEFAULT_DURATION})")
    parser.add_argument("-c", "--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                        help=f"Nombre de processos concurrents (defecte: {DEFAULT_CONCURRENCY})")

    args = parser.parse_args()

    # Crida a la funció principal amb el nou argument pyro_name
    run_stress_test(args.mode, args.host, args.insult_queue, args.work_queue, args.pyro_name, args.duration, args.concurrency)