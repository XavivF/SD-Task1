import Pyro4
import time
import math
import requests
from requests.auth import HTTPBasicAuth
from multiprocessing import Process, Event, Manager as ProcManager
import threading
import config

from insult_filter_worker import InsultFilterWorker
from insult_processor_worker import InsultProcessorWorker
from redis_manager import redis_cli


@Pyro4.expose
@Pyro4.behavior(instance_mode="single")
class ScalerManagerPyro:
    def __init__(self):
        self.proc_manager = ProcManager()  # Gestor de Processos per a llistes compartides

        # Pool per InsultFilterWorkers
        # Aquesta llista compartida guardarà NOMÉS ID i type
        self.filter_worker_processes_info = self.proc_manager.list()
        # Aquest diccionari local guardarà els objectes Process i Event
        # Es gestiona només dins del procés del ScalerManager
        # Format: {worker_id: {'process': Process, 'stop_event': Event, 'type': str}}
        self.filter_worker_processes_local = {}

        self.last_filter_queue_check_time = time.time()
        self.last_filter_message_count = 0
        self.estimated_filter_arrival_rate_lambda = 0.0

        # Pool per InsultProcessorWorkers
        # Aquesta llista compartida guardarà NOMÉS ID i type
        self.insult_processor_worker_processes_info = self.proc_manager.list()
        # Aquest diccionari local guardarà els objectes Process i Event
        self.insult_processor_worker_processes_local = {}


        self.last_insult_queue_check_time = time.time()
        self.last_insult_message_count = 0
        self.estimated_insult_arrival_rate_lambda = 0.0

        self.ns = None
        try:
            self.ns = Pyro4.locateNS(host=config.PYRO_NS_HOST, port=config.PYRO_NS_PORT)
        except Pyro4.errors.NamingError:
            print(f"ScalerManager: Pyro Name Server not found at {config.PYRO_NS_HOST}:{config.PYRO_NS_PORT}.")

        self.pyro_daemon_thread = None
        # Aquest event deté el bucle principal del ScalerManager
        self.stop_main_loop_event = Event()


        print("ScalerManager initialized (manages FilterWorkers and InsultProcessorWorkers).")

    def get_queue_length_http(self, queue_name: str, vhost: str = '%2F') -> int:
        # Aquest mètode es manté igual
        api_url = f"http://{config.RABBITMQ_HOST}:15672/api/queues/{vhost}/{queue_name}"
        try:
            # Utilitzem l'usuari i contrasenya de config per autenticar la crida HTTP
            response = requests.get(api_url, auth=HTTPBasicAuth(config.RABBITMQ_USER, config.RABBITMQ_PASS))
            response.raise_for_status()
            data = response.json()
            return data.get('messages', 0)
        except requests.exceptions.RequestException as e:
            print(f"[ScalerManager] Error getting queue length for '{queue_name}' via HTTP API: {e}")
            return -1
        except Exception as e:
            print(f"[ScalerManager] Unexpected error parsing queue length for '{queue_name}': {e}")
            return -1

    def start_worker(self, worker_type: str):
        """Inicia un worker del tipus especificat i gestiona les llistes locals i compartides."""
        worker_id = f"{worker_type}_{time.time_ns()}"
        # L'Event es crea aquí (en el procés pare) i es passarà per argument al procés fill.
        # La referència a l'Event també es guarda LOCALMENT.
        stop_event = Event()

        # Wrapper per asegurar que la instància del Worker es crea dins el nou procés fill
        def worker_runner(worker_class, wid, sevent):
            instance = worker_class(wid, sevent)
            instance.run()

        worker_process = None
        worker_pool_list_shared = None # Llista compartida del Manager (només ID i type)
        worker_pool_local_dict = None # Diccionari local amb objectes Process i Event

        if worker_type == "FilterWorker":
            worker_process = Process(target=worker_runner, args=(InsultFilterWorker, worker_id, stop_event),
                                     daemon=True)
            worker_pool_list_shared = self.filter_worker_processes_info
            worker_pool_local_dict = self.filter_worker_processes_local
        elif worker_type == "InsultProcessorWorker":
            worker_process = Process(target=worker_runner, args=(InsultProcessorWorker, worker_id, stop_event),
                                     daemon=True)
            worker_pool_list_shared = self.insult_processor_worker_processes_info
            worker_pool_local_dict = self.insult_processor_worker_processes_local
        else:
            print(f"[ScalerManager] Unknown worker type: {worker_type}")
            return


        # Guarda la informació COMPLERTA (incloent Process i Event) al diccionari LOCAL del ScalerManager
        # Aquesta referència NO es serialitza per la llista compartida
        worker_pool_local_dict[worker_id] = {
            'process': worker_process,
            'stop_event': stop_event, # L'Event es guarda localment
            'type': worker_type
        }

        # Afegeix NOMÉS la informació mínima i pickleable a la llista COMPARTIDA (Manager)
        # Això és el que altres processos (si n'hi hagués, o parts del ScalerManager
        # que accedeixin a la llista compartida) poden veure de forma segura.
        worker_pool_list_shared.append(
            {'id': worker_id, 'type': worker_type}) # IMPORTANT: NO incloem 'process' ni 'stop_event' aquí.

        worker_process.start()
        print(f"[ScalerManager] Started {worker_type}: {worker_id}")


    def stop_worker(self, worker_type: str):
        """Atura un worker del pool especificat (senyalitzant l'event local)."""

        worker_pool_list_shared = None # Llista compartida del Manager (ID, type)
        worker_pool_local_dict = None # Diccionari local (ID -> Process, Event, type)

        if worker_type == "FilterWorker":
            worker_pool_list_shared = self.filter_worker_processes_info
            worker_pool_local_dict = self.filter_worker_processes_local
        elif worker_type == "InsultProcessorWorker":
            worker_pool_list_shared = self.insult_processor_worker_processes_info
            worker_pool_local_dict = self.insult_processor_worker_processes_local
        else:
            print(f"[ScalerManager] Unknown worker type: {worker_type}")
            return False # O el maneig d'error que correspongui


        if worker_pool_list_shared:
            # Agafem la informació (ID, type) del worker de la llista compartida (FIFO)
            worker_info_shared = worker_pool_list_shared.pop(0) # Això elimina de la llista del Manager
            worker_id_to_stop = worker_info_shared['id']
            worker_type_to_stop = worker_info_shared['type'] # Obtenim el tipus correcte

            # Busquem la informació complerta (amb l'Event) al diccionari LOCAL
            worker_info_local = worker_pool_local_dict.get(worker_id_to_stop)

            if worker_info_local and 'stop_event' in worker_info_local:
                 # Senyalitzem l'esdeveniment de stop LOCAL
                 stop_event_to_set = worker_info_local['stop_event']
                 stop_event_to_set.set()
                 print(f"[ScalerManager] Signaled {worker_type_to_stop} {worker_id_to_stop} to stop.")
                 # No eliminem del diccionari local aquí. La neteja es fa més tard.
                 return True
            else:
                 print(f"[ScalerManager] Warning: Could not find local info for worker {worker_id_to_stop} to signal stop.")
                 # Tot i no poder senyalitzar, ja l'hem eliminat de la llista shared.
                 # La neteja final s'encarregarà si el procés encara existeix.
                 return False # O gestionar com a error


        return False # No hi havia workers per aturar


    def adjust_worker_pool(self, queue_name: str,
                           min_workers: int, max_workers: int,
                           worker_capacity_c: float, average_response_time: float,
                           last_msg_count_attr_name: str, last_check_time_attr_name: str,
                           lambda_attr_name: str, worker_type_name: str):
        """Lògica genèrica per ajustar un pool de treballadors."""

        worker_pool_list_shared = None # Llista compartida del Manager (ID, type)
        worker_pool_local_dict = None # Diccionari local (ID -> Process, Event, type)

        lambda_rate = 0.0
        if queue_name == config.TEXT_QUEUE_NAME:
            lambda_rate = config.FILTER_ARRIVAL_RATE
        elif queue_name == config.INSULTS_PROCESSING_QUEUE_NAME:
            lambda_rate = config.INSULT_ARRIVAL_RATE

        if worker_type_name == "FilterWorker":
            worker_pool_list_shared = self.filter_worker_processes_info
            worker_pool_local_dict = self.filter_worker_processes_local
        elif worker_type_name == "InsultProcessorWorker":
            worker_pool_list_shared = self.insult_processor_worker_processes_info
            worker_pool_local_dict = self.insult_processor_worker_processes_local
        else:
             print(f"[ScalerManager] Error: Unknown worker type during adjustment for {queue_name}.")
             return

        backlog_B = self.get_queue_length_http(queue_name)
        if backlog_B == -1:
            print(f"[ScalerManager] Cannot adjust {worker_type_name} pool, failed to get queue length for '{queue_name}'.")
            return

        current_workers_count = len(worker_pool_list_shared) # Utilitzem la mida de la llista compartida (registrats)

        print(f"[ScalerManager-{worker_type_name}] State: Backlog (B)={backlog_B}, Est. Lambda (λ)={lambda_rate:.2f} msg/s")

        # Fórmula N = ceil((lambda * Tr + B) / C )
        numerator = (lambda_rate * average_response_time) + backlog_B
        denominator = worker_capacity_c

        num_required_N = math.ceil(numerator / denominator)


        # Assegurar que N_required està dins dels límits min/max
        num_required_N = max(min_workers, min(num_required_N, max_workers))

        print(f"[ScalerManager-{worker_type_name}] Calculated N_required = {num_required_N}, Current workers = {current_workers_count}")

        if num_required_N > current_workers_count:
            num_to_add = num_required_N - current_workers_count
            print(f"[ScalerManager-{worker_type_name}] Scaling up: Adding {num_to_add} worker(s).")
            for _ in range(num_to_add):
                if len(worker_pool_list_shared) < max_workers: # Comprovem la mida de la llista compartida (registrats)
                    self.start_worker(worker_type_name) # Inicia i gestiona llistes internes
                else:
                    print(f"[ScalerManager-{worker_type_name}] Max workers ({max_workers}) reached, cannot add more.")
                    break # Aturem si hem arribat al màxim
        elif num_required_N < current_workers_count:
            num_to_remove = current_workers_count - num_required_N
            print(f"[ScalerManager-{worker_type_name}] Scaling down: Removing {num_to_remove} worker(s).")
            for _ in range(num_to_remove):
                # Eliminar workers de la llista compartida (que senyalitza stop localment)
                if len(worker_pool_list_shared) > min_workers: # Comprovem la mida de la llista compartida
                    self.stop_worker(worker_type_name) # Elimina de llista shared i senyalitza stop local
                else:
                    print(f"[ScalerManager-{worker_type_name}] Min workers ({min_workers}) reached, cannot remove more.")
                    break # Aturem si hem arribat al mínim


        # --- Neteja de processos treballador que hagin acabat inesperadament ---
        # Iterem sobre la llista compartida (amb una còpia) per trobar workers que *haurien* d'estar registrats
        # Però que, en comprovar amb l'objecte Process local, no estan vius.
        worker_ids_to_remove_from_shared_list = [] # Guardarem els IDs dels workers a eliminar de la llista shared
        worker_ids_to_remove_from_local_dict = [] # Guardarem els IDs dels processos morts trobats al dict local

        # Iterem sobre una còpia de la llista compartida per seguretat mentre la modifiquem
        for worker_info_shared in list(worker_pool_list_shared):
            worker_id = worker_info_shared['id']
            # Intentem obtenir la informació local complerta (amb Process)
            worker_info_local = worker_pool_local_dict.get(worker_id)

            if worker_info_local is None:
                # Aquest cas no hauria de passar si la lògica add/remove/cleanup és consistent.
                # La info és a la llista compartida, però s'ha perdut l'entrada local.
                print(f"[ScalerManager-{worker_type_name}] Warning: Worker {worker_id} info found in shared list, but local info (Process/Event) not found. Removing from shared list.")
                worker_ids_to_remove_from_shared_list.append(worker_id) # Marcar per eliminar de shared
            elif not worker_info_local['process'].is_alive():
                # El procés NO està viu (segons l'objecte Process local), cal netejar les dues llistes
                print(
                    f"[ScalerManager-{worker_type_name}] Worker {worker_id} is no longer alive. Removing from lists.")
                worker_ids_to_remove_from_shared_list.append(worker_id) # Marcar per eliminar de shared
                worker_ids_to_remove_from_local_dict.append(worker_id) # Marcar per eliminar de local


        # Eliminem les entrades de la llista compartida (Manager) basant-nos en els IDs marcats
        # Cal fer-ho element a element per valor o index, no per ID directament en Manager.list
        # Un mètode segur amb Manager.list és reconstruir-la o eliminar per index en ordre invers.
        # Iterem sobre una còpia i eliminem de l'original si l'ID està a la llista to_remove
        indices_to_remove_from_shared_list_final = []
        for i, worker_info_shared in enumerate(list(worker_pool_list_shared)):
             if worker_info_shared['id'] in worker_ids_to_remove_from_shared_list:
                  indices_to_remove_from_shared_list_final.append(i)

        # Eliminem en ordre invers per no afectar índexs
        for i in sorted(indices_to_remove_from_shared_list_final, reverse=True):
             try:
                 del worker_pool_list_shared[i] # Eliminem per índex de la llista compartida
             except IndexError:
                  pass # Potser ja ha estat eliminat per una altra lògica concurrent (poc probable amb 1 fil de main_loop, però segur)


        # Eliminem els objectes Process i Event corresponents del diccionari LOCAL basant-nos en els IDs marcats
        for worker_id in worker_ids_to_remove_from_local_dict:
             if worker_id in worker_pool_local_dict:
                 del worker_pool_local_dict[worker_id]


        # NOTA: Quan cridem _stop_worker, només senyalitzem l'event LOCAL i eliminem de la llista shared.
        # El procés worker s'aturarà al seu ritme.
        # La neteja COMPLERTA (eliminació de l'entrada al diccionari local amb l'objecte Process)
        # es fa en la propera execució d'aquest bloc de neteja si el procés ja no està viu,
        # o a la neteja final del main_loop.


    def main_loop(self):
        print("[ScalerManager] Starting main loop for all worker pools...")
        filter_last_scale_time = time.time()
        insult_processor_last_scale_time = time.time()

        # Bucle principal on es monitoritza i escala
        while not self.stop_main_loop_event.is_set():
            current_time = time.time()

            # Ajustar FilterWorkers
            if current_time - filter_last_scale_time >= config.FILTER_SCALING_INTERVAL:
                print("\n--- Adjusting InsultFilterWorker Pool ---")
                # Cridem _adjust_worker_pool que gestiona les llistes internes
                self.adjust_worker_pool(
                    queue_name=config.TEXT_QUEUE_NAME,
                    min_workers=config.FILTER_MIN_WORKERS,
                    max_workers=config.FILTER_MAX_WORKERS,
                    worker_capacity_c=config.FILTER_WORKER_CAPACITY_C,
                    average_response_time=config.FILTER_AVERAGE_RESPONSE_TIME,
                    last_msg_count_attr_name='last_filter_message_count',
                    last_check_time_attr_name='last_filter_queue_check_time',
                    lambda_attr_name='estimated_filter_arrival_rate_lambda',
                    worker_type_name="FilterWorker"
                )
                filter_last_scale_time = current_time

            # Ajustar InsultProcessorWorkers (NOU)
            if current_time - insult_processor_last_scale_time >= config.INSULT_PROCESSOR_SCALING_INTERVAL:
                print("\n--- Adjusting InsultProcessorWorker Pool ---")
                # Cridem _adjust_worker_pool que gestiona les llistes internes
                self.adjust_worker_pool(
                    queue_name=config.INSULTS_PROCESSING_QUEUE_NAME,
                    min_workers=config.INSULT_PROCESSOR_MIN_WORKERS,
                    max_workers=config.INSULT_PROCESSOR_MAX_WORKERS,
                    worker_capacity_c=config.INSULT_PROCESSOR_WORKER_CAPACITY_C,
                    average_response_time=config.INSULT_PROCESSOR_AVERAGE_RESPONSE_TIME,
                    last_msg_count_attr_name='last_insult_message_count',
                    last_check_time_attr_name='last_insult_queue_check_time',
                    lambda_attr_name='estimated_insult_arrival_rate_lambda',
                    worker_type_name="InsultProcessorWorker"
                )
                insult_processor_last_scale_time = current_time


            time.sleep(1)  # Comprova cada segon si toca escalar algun pool

        # --- CODI DE NETEJA FINAL (EXECUTAT DESPRÉS DEL WHILE LOOP) ---
        # Aquest bloc s'executa quan self.stop_main_loop_event.is_set() és True
        print("[ScalerManager] Main loop stopped. Initiating cleanup of all workers...")

        all_local_pools = {
            "FilterWorker": self.filter_worker_processes_local,
            "InsultProcessorWorker": self.insult_processor_worker_processes_local
        }

        print("[ScalerManager] Signaling all workers to stop...")
        # Iterem sobre una còpia dels items del diccionari local per poder modificar l'original
        for worker_type, local_pool in list(all_local_pools.items()): # Itera sobre els pools
            for worker_id, worker_info_local in list(local_pool.items()): # Itera sobre els workers locals
                try:
                    # Obtenim l'event de stop del diccionari local
                    if 'stop_event' in worker_info_local and worker_info_local['stop_event']:
                       stop_event_to_set = worker_info_local['stop_event']
                       stop_event_to_set.set()
                       print(f"[ScalerManager] Signaled {worker_type} {worker_id} to stop (final cleanup).")
                    else:
                       print(f"[ScalerManager] Warning: Stop event not found in local info for {worker_type} {worker_id} during final cleanup.")

                except Exception as e:
                    print(f"[ScalerManager] Error signaling stop to {worker_type} {worker_id}: {e}")


        # Esperar que els processos acabin i netejar els diccionaris locals i llistes compartides
        print("[ScalerManager] Waiting for workers to finish and performing final list cleanup...")
        # Iterem sobre una còpia dels items del diccionari local
        for worker_type, local_pool in list(all_local_pools.items()): # Itera sobre els pools
             for worker_id, worker_info_local in list(local_pool.items()): # Itera sobre els workers locals
                # Intentem unir-nos/terminar el procés si encara existeix a la info local
                if 'process' in worker_info_local and worker_info_local['process'] and worker_info_local['process'].is_alive():
                    worker_process = worker_info_local['process']
                    try:
                        print(f"[ScalerManager] Joining {worker_type} {worker_id}...")
                        worker_process.join(timeout=5)
                        if worker_process.is_alive():
                            print(f"[ScalerManager] Forcing termination of {worker_type} {worker_id}")
                            worker_process.terminate()
                    except Exception as e:
                        print(f"[ScalerManager] Error joining/terminating {worker_type} {worker_id}: {e}")

                # Un cop hem intentat aturar/unir el procés, el podem eliminar de les llistes.
                # Eliminem del diccionari local
                if worker_id in local_pool:
                     del local_pool[worker_id]

                # Eliminem de la llista compartida (Manager) si encara hi és.
                # Cal trobar l'entrada per ID i eliminar-la.
                shared_list = None
                if worker_type == "FilterWorker":
                    shared_list = self.filter_worker_processes_info
                elif worker_type == "InsultProcessorWorker":
                    shared_list = self.insult_processor_worker_processes_info

                if shared_list:
                    indices_to_remove_from_shared_list_final = []
                    # Iterem sobre una còpia per trobar l'índex
                    for i, worker_info_shared in enumerate(list(shared_list)):
                         if worker_info_shared['id'] == worker_id:
                              indices_to_remove_from_shared_list_final.append(i)

                    # Eliminem en ordre invers de la llista compartida real
                    for i in sorted(indices_to_remove_from_shared_list_final, reverse=True):
                         try:
                             del shared_list[i]
                         except IndexError:
                              pass # Ja s'ha eliminat


        print("[ScalerManager] All workers stopped and lists cleaned.")


    @Pyro4.expose
    def get_scaler_stats(self):
        filter_queue_len = self.get_queue_length_http(config.TEXT_QUEUE_NAME)
        insult_proc_queue_len = self.get_queue_length_http(config.INSULTS_PROCESSING_QUEUE_NAME)

        # Cal utilitzar la mida de les llistes compartides per al nombre de workers actius
        # que el ScalerManager *creu* que estan vius/registrats.
        active_filter_workers = len(self.filter_worker_processes_info)
        active_insult_processors = len(self.insult_processor_worker_processes_info)

        return {
            "filter_workers_pool": {
                "active_workers": active_filter_workers,
                "text_queue_length": filter_queue_len if filter_queue_len != -1 else "Error",
                # La lambda estimada es guarda com a atribut de l'objecte ScalerManager
                "total_texts_censored_redis": redis_cli.get_censored_texts_count(),
                "filter_processed_redis_counter": redis_cli.r.get(config.REDIS_PROCESSED_COUNTER_KEY) or 0,
            },
            "insult_processor_pool": {  # NOU
                "active_workers": active_insult_processors,
                "insults_processing_queue_length": insult_proc_queue_len if insult_proc_queue_len != -1 else "Error",
                 # La lambda estimada es guarda com a atribut de l'objecte ScalerManager
                "insults_processed_redis_counter": redis_cli.r.get(config.REDIS_PROCESSED_COUNTER_KEY) or 0,
            },
            "config_summary": {
                "filter_min_max_workers": f"{config.FILTER_MIN_WORKERS}-{config.FILTER_MAX_WORKERS}",
                "filter_C_Tr": f"C={config.FILTER_WORKER_CAPACITY_C}, Tr={config.FILTER_AVERAGE_RESPONSE_TIME}",
                "insult_proc_min_max_workers": f"{config.INSULT_PROCESSOR_MIN_WORKERS}-{config.INSULT_PROCESSOR_MAX_WORKERS}",
                "insult_proc_C_Tr": f"C={config.INSULT_PROCESSOR_WORKER_CAPACITY_C}, Tr={config.INSULT_PROCESSOR_AVERAGE_RESPONSE_TIME}",
            }
        }

    # get_censored_texts_sample es manté igual. Assumeix que redis_cli ja està connectat.
    @Pyro4.expose
    def get_censored_texts_sample(self, count=10):
         """Returns a sample of censored texts from Redis."""
         return redis_cli.get_censored_texts(0, count - 1)

    @Pyro4.expose
    def reset_counter(self):
        """Resets the processed texts counter in Redis."""
        redis_cli.reset_processed_count()
        print("[ScalerManager] Processed texts counter reset in Redis.")
        return True


    def start_pyro_daemon(self):
        # Aquest mètode es manté pràcticament igual
        try:
            # El daemon Pyro ha de córrer en un fil separat per no bloquejar el main_loop
            daemon = Pyro4.Daemon(host=config.PYRO_DAEMON_HOST)
            # Registrem la instància actual del ScalerManagerPyro
            uri = daemon.register(self, objectId=config.PYRO_SCALER_MANAGER_NAME)
            if self.ns:
                self.ns.register(config.PYRO_SCALER_MANAGER_NAME, uri)
                print(f"[ScalerManager] Pyro service registered as '{config.PYRO_SCALER_MANAGER_NAME}' with URI {uri}")
            else:
                print(
                    f"[ScalerManager] Pyro Name Server not found. Service '{config.PYRO_SCALER_MANAGER_NAME}' not registered. URI is {uri}")
            print("[ScalerManager] Pyro daemon starting...")
            # Entra al bucle principal del daemon Pyro, esperant peticions remotes
            daemon.requestLoop()
            print("[ScalerManager] Pyro daemon stopped.")
        except Exception as e:
            print(f"[ScalerManager] Error in Pyro setup or loop: {e}")
        finally:
            # Neteja al final (si el daemon s'atura per qualsevol raó)
            if self.ns and config.PYRO_SCALER_MANAGER_NAME in self.ns.list():  # type: ignore
                try:
                    self.ns.remove(config.PYRO_SCALER_MANAGER_NAME)
                    print(f"[ScalerManager] Pyro service '{config.PYRO_SCALER_MANAGER_NAME}' unregistered.")
                except Exception as e_unreg:
                    print(f"[ScalerManager] Error unregistering Pyro service: {e_unreg}")


    def run(self):
        # Aquest mètode inicia el fil del daemon Pyro i després entra al bucle principal d'escalat
        self.pyro_daemon_thread = threading.Thread(target=self.start_pyro_daemon, daemon=True)
        self.pyro_daemon_thread.start()
        print("[ScalerManager] Pyro daemon thread for ScalerManager started.")
        try:
            # El bucle principal de l'escalat s'executa en el fil principal (o el fil que cridi 'run')
            self.main_loop()
        except KeyboardInterrupt:
            # Captura Ctrl+C per iniciar el tancament controlat
            print("[ScalerManager] KeyboardInterrupt received by ScalerManager. Stopping...")
        finally:
            # Senyalitza al bucle principal que s'aturi
            self.stop_main_loop_event.set()
            # No cal unir-se al fil del daemon Pyro si és daemon=True, acabarà sol.
            # La neteja de workers la fa main_loop abans de sortir.
            print("[ScalerManager] ScalerManager exiting.")