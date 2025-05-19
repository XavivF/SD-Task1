import time
import Pyro4
import config
from multiprocessing import Process

from scaler_manager import ScalerManagerPyro
from insult_service import InsultServicePyro, start_insult_service_components


def run_pyro_service(service_class, service_name_in_ns, pyro_daemon_host):
    """Generic function to run a Pyro service."""
    daemon = None
    ns = None
    uri = None
    service_instance = service_class()  # Creates the service instance

    try:
        ns = Pyro4.locateNS(host=config.PYRO_NS_HOST, port=config.PYRO_NS_PORT)
        daemon = Pyro4.Daemon(host=pyro_daemon_host)
        uri = daemon.register(service_instance)  # Registers the created instance
        ns.register(service_name_in_ns, uri)

        print(f"Service '{service_name_in_ns}' registered with URI {uri}. Ready.")
        daemon.requestLoop()
    except Pyro4.errors.NamingError as e_ns:
        print(
            f"Pyro Naming Server error for '{service_name_in_ns}': {e_ns}. Is Name Server running at {config.PYRO_NS_HOST}:{config.PYRO_NS_PORT}?")
    except Exception as e:
        print(f"Error running Pyro service '{service_name_in_ns}': {e}")
    finally:
        print(f"Shutting down Pyro service '{service_name_in_ns}'.")
        if daemon:
            daemon.shutdown()
        if ns and uri and service_name_in_ns in ns.list():
            try:
                ns.remove(service_name_in_ns)
                print(f"Service '{service_name_in_ns}' unregistered.")
            except Exception as e_unreg:
                print(f"Error unregistering '{service_name_in_ns}': {e_unreg}")


if __name__ == "__main__":
    print("Starting services...")

    # 1. Start the Pyro Name Server (manually or with python -m Pyro4.naming)
    #    Ensure the Name Server is running before launching the services.
    #    Command: python -m Pyro4.naming -n localhost -p 9090

    # 2. Start InsultService (with its internal processes and its own Pyro service)
    # InsultService needs its background processes (notifier, exchange listener)
    # and its own exposed Pyro object.

    # InsultService itself is not a process, but it launches child processes.
    # Its Pyro object will be exposed in a separate process/thread.

    insult_service_pyro_process = Process(target=run_pyro_service,
                                          args=(InsultServicePyro, config.PYRO_INSULT_SERVICE_NAME,
                                                config.PYRO_DAEMON_HOST),
                                          daemon=True)  # daemon=True so it exits if the main process exits
    insult_service_pyro_process.start()
    print("InsultService Pyro endpoint process starting...")

    # Start InsultService background processes (notifier, exchange listener)
    # These are managed internally by start_insult_service_components
    # and are already daemon processes.
    insult_service_background_procs = start_insult_service_components()
    print(f"InsultService background processes ({len(insult_service_background_procs)}) started.")

    time.sleep(2)  # Give time for InsultService to register

    # 3. Start ScalerManager (which includes its own Pyro service and manages workers)
    # ScalerManager has its own main loop and its own thread for the Pyro daemon.
    # We will run it in the main process of this launcher for simplicity,
    # or we can put it in another Process if we want more isolation.

    print("Starting ScalerManager...")
    scaler_manager_instance = ScalerManagerPyro()
    # The ScalerManager's run() method is blocking (it contains the main_loop and pyro_daemon_thread.start())
    # If we want this script to exit with Ctrl+C and close everything, run() must be the last thing.

    try:
        scaler_manager_instance.run()  # This is blocking due to main_loop inside run()
    except KeyboardInterrupt:
        print("Launcher: KeyboardInterrupt received. Shutting down all services.")
    finally:
        print("Launcher: Initiating shutdown sequence...")

        # Stop ScalerManager (already done by its own finally inside run())
        # If scaler_manager.run() is executed in the main thread, its finally will handle it.
        # If it were executed in a separate process, we would need to signal it.

        # Stop InsultService Pyro endpoint
        if insult_service_pyro_process.is_alive():
            print("Launcher: Terminating InsultService Pyro process...")
            insult_service_pyro_process.terminate()  # Force termination
            insult_service_pyro_process.join(timeout=5)

        # The InsultService background processes (notifier, listener) are daemon,
        # so they will stop when their parent process (this launcher) exits,
        # or when insult_service_pyro_process exits if it were their direct parent.
        # Since they are daemon=True upon creation, explicit join is not needed here if the parent exits.

        print("Launcher: Shutdown complete.")