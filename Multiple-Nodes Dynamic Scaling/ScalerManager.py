import Pyro4
import time
import math
import requests
from requests.auth import HTTPBasicAuth
from multiprocessing import Process, Event, Manager as ProcManager
import threading
import config

from Pyro4 import errors
from InsultFilterWorker import InsultFilterWorker
from InsultProcessorWorker import InsultProcessorWorker
from RedisManager import redis_cli


@Pyro4.expose
@Pyro4.behavior(instance_mode="single")
class ScalerManagerPyro:
    def __init__(self):
        self.proc_manager = ProcManager()  # Process Manager for shared lists

        # Pool for InsultFilterWorkers
        # This shared list will store ONLY ID and type
        self.filter_worker_processes_info = self.proc_manager.list()
        # This local dictionary will store the Process and Event objects
        # It is managed only within the ScalerManager process
        # Format: {worker_id: {'process': Process, 'stop_event': Event, 'type': str}}
        self.filter_worker_processes_local = {}

        self.last_filter_queue_check_time = time.time()
        self.last_filter_message_count = 0
        self.estimated_filter_arrival_rate_lambda = 0.0

        # Pool for InsultProcessorWorkers
        # This shared list will store ONLY ID and type
        self.insult_processor_worker_processes_info = self.proc_manager.list()
        # This local dictionary will store the Process and Event objects
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
        # This event stops the main loop of the ScalerManager
        self.stop_main_loop_event = Event()


        print("ScalerManager initialized (manages FilterWorkers and InsultProcessorWorkers).")

    def get_queue_length_http(self, queue_name: str, vhost: str = '%2F') -> int:
        # This method remains the same
        api_url = f"http://{config.RABBITMQ_HOST}:15672/api/queues/{vhost}/{queue_name}"
        try:
            # We use the user and password from config to authenticate the HTTP call
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
        """Starts a worker of the specified type and manages local and shared lists."""
        worker_id = f"{worker_type}_{time.time_ns()}"
        # The Event is created here (in the parent process) and will be passed as an argument to the child process.
        # The reference to the Event is also stored LOCALLY.
        stop_event = Event()

        # Wrapper to ensure the Worker instance is created inside the new child process
        def worker_runner(worker_class, wid, sevent):
            instance = worker_class(wid, sevent)
            instance.run()

        worker_process = None
        worker_pool_list_shared = None # Shared list from the Manager (only ID and type)
        worker_pool_local_dict = None # Local dictionary with Process and Event objects

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


        # Stores the COMPLETE information (including Process and Event) in the LOCAL dictionary of the ScalerManager
        # This reference is NOT serialized for the shared list
        worker_pool_local_dict[worker_id] = {
            'process': worker_process,
            'stop_event': stop_event, # The Event is stored locally
            'type': worker_type
        }

        # Adds ONLY the minimum and pickleable information to the SHARED list (Manager)
        # This is what other processes (if any, or parts of the ScalerManager
        # that access the shared list) can safely see.
        worker_pool_list_shared.append(
            {'id': worker_id, 'type': worker_type}) # IMPORTANT: We do NOT include 'process' or 'stop_event' here.

        worker_process.start()
        print(f"[ScalerManager] Started {worker_type}: {worker_id}")


    def stop_worker(self, worker_type: str):
        """Stops a worker from the specified pool (by signaling the local event)."""

        worker_pool_list_shared = None # Shared list from the Manager (ID, type)
        worker_pool_local_dict = None # Local dictionary (ID -> Process, Event, type)

        if worker_type == "FilterWorker":
            worker_pool_list_shared = self.filter_worker_processes_info
            worker_pool_local_dict = self.filter_worker_processes_local
        elif worker_type == "InsultProcessorWorker":
            worker_pool_list_shared = self.insult_processor_worker_processes_info
            worker_pool_local_dict = self.insult_processor_worker_processes_local
        else:
            print(f"[ScalerManager] Unknown worker type: {worker_type}")
            return False # Or appropriate error handling

        if worker_pool_list_shared:
            # Get the worker info (ID, type) from the shared list (FIFO)
            worker_info_shared = worker_pool_list_shared.pop(0) # This removes from the Manager's list
            worker_id_to_stop = worker_info_shared['id']
            worker_type_to_stop = worker_info_shared['type'] # Get the correct type

            # Look for the complete info (with the Event) in the LOCAL dictionary
            worker_info_local = worker_pool_local_dict.get(worker_id_to_stop)

            if worker_info_local and 'stop_event' in worker_info_local:
                 # Signal the LOCAL stop event
                 stop_event_to_set = worker_info_local['stop_event']
                 stop_event_to_set.set()
                 print(f"[ScalerManager] Signaled {worker_type_to_stop} {worker_id_to_stop} to stop.")
                 # We don't remove from the local dictionary here. Cleanup is done later.
                 return True
            else:
                 print(f"[ScalerManager] Warning: Could not find local info for worker {worker_id_to_stop} to signal stop.")
                 # Even if we can't signal, we have removed it from the shared list.
                 # Final cleanup will handle it if the process still exists.
                 return False # Or handle as an error


        return False # No workers to stop


    def adjust_worker_pool(self, queue_name: str,
                           min_workers: int, max_workers: int,
                           worker_capacity_c: float, average_response_time: float,
                           last_msg_count_attr_name: str, last_check_time_attr_name: str,
                           lambda_attr_name: str, worker_type_name: str):
        """Generic logic to adjust a worker pool."""

        worker_pool_list_shared = None # Shared list from the Manager (ID, type)
        worker_pool_local_dict = None # Local dictionary (ID -> Process, Event, type)

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

        backlog_b = self.get_queue_length_http(queue_name)
        if backlog_b == -1:
            print(f"[ScalerManager] Cannot adjust {worker_type_name} pool, failed to get queue length for '{queue_name}'.")
            return

        current_workers_count = len(worker_pool_list_shared) # Use the size of the shared list (registered)

        print(f"[ScalerManager-{worker_type_name}] State: Backlog (B)={backlog_b}, Est. Lambda (λ)={lambda_rate:.2f} msg/s")

        # Formula N = ceil((lambda * Tr + B) / C )
        numerator = (lambda_rate * average_response_time) + backlog_b
        denominator = worker_capacity_c

        num_required_N = math.ceil(numerator / denominator)


        # Ensure N_required is within min/max limits
        num_required_N = max(min_workers, min(num_required_N, max_workers))

        print(f"[ScalerManager-{worker_type_name}] Calculated N_required = {num_required_N}, Current workers = {current_workers_count}")

        if num_required_N > current_workers_count:
            num_to_add = num_required_N - current_workers_count
            print(f"[ScalerManager-{worker_type_name}] Scaling up: Adding {num_to_add} worker(s).")
            for _ in range(num_to_add):
                if len(worker_pool_list_shared) < max_workers: # Check the size of the shared list (registered)
                    self.start_worker(worker_type_name) # Start and manage internal lists
                else:
                    print(f"[ScalerManager-{worker_type_name}] Max workers ({max_workers}) reached, cannot add more.")
                    break # Stop if we reached the maximum
        elif num_required_N < current_workers_count:
            num_to_remove = current_workers_count - num_required_N
            print(f"[ScalerManager-{worker_type_name}] Scaling down: Removing {num_to_remove} worker(s).")
            for _ in range(num_to_remove):
                # Remove workers from the shared list (which signals stop locally)
                if len(worker_pool_list_shared) > min_workers: # Check the size of the shared list
                    self.stop_worker(worker_type_name) # Removes from shared list and signals stop locally
                else:
                    print(f"[ScalerManager-{worker_type_name}] Min workers ({min_workers}) reached, cannot remove more.")
                    break # Stop if we reached the minimum


        # --- Cleanup of worker processes that may have finished unexpectedly ---
        # Iterate over the shared list (with a copy) to find workers that *should* be registered
        # But which, when checked with the local Process object, are not alive.
        worker_ids_to_remove_from_shared_list = [] # Will store the IDs of workers to remove from the shared list
        worker_ids_to_remove_from_local_dict = [] # Will store the IDs of dead processes found in the local dict

        # Iterate over a copy of the shared list for safety while modifying the original
        for worker_info_shared in list(worker_pool_list_shared):
            worker_id = worker_info_shared['id']
            # Try to get the complete local information (with Process)
            worker_info_local = worker_pool_local_dict.get(worker_id)

            if worker_info_local is None:
                # This case should not happen if the add/remove/cleanup logic is consistent.
                # The info is in the shared list, but the local entry is lost.
                print(f"[ScalerManager-{worker_type_name}] Warning: Worker {worker_id} info found in shared list, but local info (Process/Event) not found. Removing from shared list.")
                worker_ids_to_remove_from_shared_list.append(worker_id) # Mark for removal from shared
            elif not worker_info_local['process'].is_alive():
                # The process is NOT alive (according to the local Process object), need to clean up both lists
                print(f"[ScalerManager-{worker_type_name}] Worker {worker_id} is no longer alive. Removing from lists.")
                worker_ids_to_remove_from_shared_list.append(worker_id) # Mark for removal from shared
                worker_ids_to_remove_from_local_dict.append(worker_id) # Mark for removal from local


        # Remove the entries from the shared list (Manager) based on the marked IDs
        # Need to do it element by element by value or index, not by ID directly in Manager.list
        # A safe method with Manager.list is to rebuild it or remove by index in reverse order.
        # Iterate over a copy and remove from the original if the ID is in the to_remove list
        indices_to_remove_from_shared_list_final = []
        for i, worker_info_shared in enumerate(list(worker_pool_list_shared)):
             if worker_info_shared['id'] in worker_ids_to_remove_from_shared_list:
                  indices_to_remove_from_shared_list_final.append(i)

        # Remove in reverse order to avoid affecting indices
        for i in sorted(indices_to_remove_from_shared_list_final, reverse=True):
             try:
                 del worker_pool_list_shared[i] # Remove by index from the shared list
             except IndexError:
                  pass # Maybe it has already been removed by other concurrent logic (unlikely with 1 main_loop thread, but safe)


        # Remove the corresponding Process and Event objects from the LOCAL dictionary based on the marked IDs
        for worker_id in worker_ids_to_remove_from_local_dict:
             if worker_id in worker_pool_local_dict:
                 del worker_pool_local_dict[worker_id]


        # NOTE: When we call _stop_worker, we only signal the LOCAL event and remove from the shared list.
        # The worker process will stop at its own pace.
        # The COMPLETE cleanup (removal of the entry from the local dictionary with the Process object)
        # is done in the next execution of this cleanup block if the process is no longer alive,
        # or during the final cleanup of the main_loop.


    def main_loop(self):
        print("[ScalerManager] Starting main loop for all worker pools...")
        filter_last_scale_time = time.time()
        insult_processor_last_scale_time = time.time()

        # Main loop where monitoring and scaling happens
        while not self.stop_main_loop_event.is_set():
            current_time = time.time()


            # Adjust FilterWorkers
            if current_time - filter_last_scale_time >= config.FILTER_SCALING_INTERVAL:
                print("\n\n--- Adjusting InsultFilterWorker Pool ---")
                # Call _adjust_worker_pool which manages internal lists
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
            # Adjust InsultProcessorWorkers (NEW)
            if current_time - insult_processor_last_scale_time >= config.INSULT_PROCESSOR_SCALING_INTERVAL:
                print("\n\n--- Adjusting InsultProcessorWorker Pool ---")
                # Call _adjust_worker_pool which manages internal lists
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

            time.sleep(0.1)  # Check every tenth of a second if it's time to scale any pool

        # --- FINAL CLEANUP CODE (EXECUTED AFTER THE WHILE LOOP) ---
        # This block is executed when self.stop_main_loop_event.is_set() is True
        print("[ScalerManager] Main loop stopped. Initiating cleanup of all workers...")

        all_local_pools = {
            "FilterWorker": self.filter_worker_processes_local,
            "InsultProcessorWorker": self.insult_processor_worker_processes_local
        }

        print("[ScalerManager] Signaling all workers to stop...")
        # Iterate over a copy of the items in the local dictionary to be able to modify the original
        for worker_type, local_pool in list(all_local_pools.items()): # Iterate over the pools
            for worker_id, worker_info_local in list(local_pool.items()): # Iterate over local workers
                try:
                    # Get the stop event from the local dictionary
                    if 'stop_event' in worker_info_local and worker_info_local['stop_event']:
                       stop_event_to_set = worker_info_local['stop_event']
                       stop_event_to_set.set()
                       # print(f"[ScalerManager] Signaled {worker_type} {worker_id} to stop (final cleanup).")
                    else:
                       print(f"[ScalerManager] Warning: Stop event not found in local info for {worker_type} {worker_id} during final cleanup.")

                except Exception as e:
                    print(f"[ScalerManager] Error signaling stop to {worker_type} {worker_id}: {e}")


        # Wait for processes to finish and clean up local dictionaries and shared lists
        print("[ScalerManager] Waiting for workers to finish and performing final list cleanup...")
        # Iterate over a copy of the items in the local dictionary
        for worker_type, local_pool in list(all_local_pools.items()): # Iterate over the pools
             for worker_id, worker_info_local in list(local_pool.items()): # Iterate over local workers
                # Try to join/terminate the process if it still exists in the local info
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

                # Once we have attempted to stop/join the process, we can remove it from the lists.
                # Remove from the local dictionary
                if worker_id in local_pool:
                     del local_pool[worker_id]

                # Remove from the shared list (Manager) if it is still there.
                # Need to find the entry by ID and remove it.
                shared_list = None
                if worker_type == "FilterWorker":
                    shared_list = self.filter_worker_processes_info
                elif worker_type == "InsultProcessorWorker":
                    shared_list = self.insult_processor_worker_processes_info

                if shared_list:
                    indices_to_remove_from_shared_list_final = []
                    # Iterate over a copy to find the index
                    for i, worker_info_shared in enumerate(list(shared_list)):
                         if worker_info_shared['id'] == worker_id:
                              indices_to_remove_from_shared_list_final.append(i)

                    # Remove in reverse order from the actual shared list
                    for i in sorted(indices_to_remove_from_shared_list_final, reverse=True):
                         try:
                             del shared_list[i]
                         except IndexError:
                              pass # Already removed


        print("[ScalerManager] All workers stopped and lists cleaned.")


    @Pyro4.expose
    def get_scaler_stats(self):
        filter_queue_len = self.get_queue_length_http(config.TEXT_QUEUE_NAME)
        insult_proc_queue_len = self.get_queue_length_http(config.INSULTS_PROCESSING_QUEUE_NAME)

        # Need to use the size of the shared lists for the number of active workers
        # that the ScalerManager *believes* are alive/registered.
        active_filter_workers = len(self.filter_worker_processes_info)
        active_insult_processors = len(self.insult_processor_worker_processes_info)

        return {
            "filter_workers_pool": {
                "active_workers": active_filter_workers,
                "text_queue_length": filter_queue_len if filter_queue_len != -1 else "Error",
                # The estimated lambda is stored as an attribute of the ScalerManager object
                "total_texts_censored_redis": redis_cli.get_censored_texts_count(),
                "filter_processed_redis_counter": redis_cli.r.get(config.REDIS_PROCESSED_COUNTER_KEY) or 0,
            },
            "insult_processor_pool": {  # NEW
                "active_workers": active_insult_processors,
                "insults_processing_queue_length": insult_proc_queue_len if insult_proc_queue_len != -1 else "Error",
                 # The estimated lambda is stored as an attribute of the ScalerManager object
                "insults_processed_redis_counter": redis_cli.r.get(config.REDIS_PROCESSED_COUNTER_KEY) or 0,
            },
            "config_summary": {
                "filter_min_max_workers": f"{config.FILTER_MIN_WORKERS}-{config.FILTER_MAX_WORKERS}",
                "filter_C_Tr": f"C={config.FILTER_WORKER_CAPACITY_C}, Tr={config.FILTER_AVERAGE_RESPONSE_TIME}",
                "insult_proc_min_max_workers": f"{config.INSULT_PROCESSOR_MIN_WORKERS}-{config.INSULT_PROCESSOR_MAX_WORKERS}",
                "insult_proc_C_Tr": f"C={config.INSULT_PROCESSOR_WORKER_CAPACITY_C}, Tr={config.INSULT_PROCESSOR_AVERAGE_RESPONSE_TIME}",
            }
        }

    @Pyro4.expose
    def get_censored_texts(self):
         return redis_cli.get_censored_texts(0, -1)

    @Pyro4.expose
    def reset_counter(self):
        """Resets the processed texts counter in Redis."""
        redis_cli.reset_processed_count()
        print("[ScalerManager] Processed texts counter reset in Redis.")
        return True


    def start_pyro_daemon(self):
        # This method remains practically the same
        try:
            # The Pyro daemon must run in a separate thread to not block the main_loop
            daemon = Pyro4.Daemon(host=config.PYRO_DAEMON_HOST)
            # Register the current instance of ScalerManagerPyro
            uri = daemon.register(self, objectId=config.PYRO_SCALER_MANAGER_NAME)
            if self.ns:
                self.ns.register(config.PYRO_SCALER_MANAGER_NAME, uri)
                print(f"[ScalerManager] Pyro service registered as '{config.PYRO_SCALER_MANAGER_NAME}' with URI {uri}")
            else:
                print(f"[ScalerManager] Pyro Name Server not found. Service '{config.PYRO_SCALER_MANAGER_NAME}' not registered. URI is {uri}")
            print("[ScalerManager] Pyro daemon starting...")
            # Enter the main loop of the Pyro daemon, waiting for remote requests
            daemon.requestLoop()
            print("[ScalerManager] Pyro daemon stopped.")
        except Exception as e:
            print(f"[ScalerManager] Error in Pyro setup or loop: {e}")
        finally:
            # Cleanup at the end (if the daemon stops for any reason)
            if self.ns and config.PYRO_SCALER_MANAGER_NAME in self.ns.list():  # type: ignore
                try:
                    self.ns.remove(config.PYRO_SCALER_MANAGER_NAME)
                    print(f"[ScalerManager] Pyro service '{config.PYRO_SCALER_MANAGER_NAME}' unregistered.")
                except Exception as e_unreg:
                    print(f"[ScalerManager] Error unregistering Pyro service: {e_unreg}")


    def run(self):
        # This method starts the Pyro daemon thread and then enters the main scaling loop
        self.pyro_daemon_thread = threading.Thread(target=self.start_pyro_daemon, daemon=True)
        self.pyro_daemon_thread.start()
        print("[ScalerManager] Pyro daemon thread for ScalerManager started.")
        try:
            # The main scaling loop runs in the main thread (or the thread that calls 'run')
            self.main_loop()
        except KeyboardInterrupt:
            # Capture Ctrl+C to initiate controlled shutdown
            print("[ScalerManager] KeyboardInterrupt received by ScalerManager. Stopping...")
        finally:
            # Signal the main loop to stop
            self.stop_main_loop_event.set()
            # No need to join the Pyro daemon thread if daemon=True, it will exit on its own.
            # Worker cleanup is done by main_loop before exiting.
            print("[ScalerManager] ScalerManager exiting.")