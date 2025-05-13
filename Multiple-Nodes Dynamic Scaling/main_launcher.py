# main_launcher.py
import time
import Pyro4
import threading
import config
from multiprocessing import Process

# Importa les classes dels teus serveis
from scaler_manager import ScalerManagerPyro
from insult_service import InsultServicePyro, start_insult_service_components


def run_pyro_service(service_class, service_name_in_ns, pyro_daemon_host):
    """Funció genèrica per executar un servei Pyro."""
    daemon = None
    ns = None
    uri = None
    service_instance = service_class()  # Crea la instància del servei

    try:
        ns = Pyro4.locateNS(host=config.PYRO_NS_HOST, port=config.PYRO_NS_PORT)
        daemon = Pyro4.Daemon(host=pyro_daemon_host)
        uri = daemon.register(service_instance)  # Registra la instància creada
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

    # 1. Iniciar el Pyro Name Server (manualment o amb python -m Pyro4.naming)
    #    Assegura't que el Name Server està funcionant abans de llançar els serveis.
    #    Comanda: python -m Pyro4.naming -n localhost -p 9090

    # 2. Iniciar InsultService (amb els seus processos interns i el seu propi servei Pyro)
    # L'InsultService necessita els seus processos de fons (notifier, listener)
    # i el seu propi objecte Pyro exposat.

    # L'InsultService en sí mateix no és un procés, sinó que llança processos fills.
    # El seu objecte Pyro s'exposarà en un procés/fil separat.

    insult_service_pyro_process = Process(target=run_pyro_service,
                                          args=(InsultServicePyro, config.PYRO_INSULT_SERVICE_NAME,
                                                config.PYRO_DAEMON_HOST),
                                          daemon=True)  # daemon=True perquè acabi si el principal acaba
    insult_service_pyro_process.start()
    print("InsultService Pyro endpoint process starting...")

    # Iniciar els processos de fons de InsultService (notifier, listener de l'exchange)
    # Aquests són gestionats internament per start_insult_service_components
    # i ja són processos daemon.
    insult_service_background_procs = start_insult_service_components()
    print(f"InsultService background processes ({len(insult_service_background_procs)}) started.")

    time.sleep(2)  # Dóna temps perquè es registri InsultService

    # 3. Iniciar ScalerManager (que inclou el seu propi servei Pyro i gestiona workers)
    # El ScalerManager té el seu propi bucle principal i el seu propi fil per al daemon Pyro.
    # El farem córrer en el procés principal d'aquest launcher per simplicitat,
    # o el podem posar en un altre Process si volem més aïllament.

    print("Starting ScalerManager...")
    scaler_manager_instance = ScalerManagerPyro()
    # El mètode run() del scaler manager és bloquejant (conté el main_loop i el pyro_daemon_thread.start())
    # Si volem que aquest script acabi amb Ctrl+C i tanqui tot, el run() ha de ser l'últim.

    try:
        scaler_manager_instance.run()  # Aquest és bloquejant per main_loop dins de run()
    except KeyboardInterrupt:
        print("Launcher: KeyboardInterrupt received. Shutting down all services.")
    finally:
        print("Launcher: Initiating shutdown sequence...")

        # Aturar ScalerManager (ja ho fa el seu propi finally dins de run())
        # Si scaler_manager.run() s'executa en el fil principal, el seu finally s'encarregarà.
        # Si s'executés en un procés separat, hauríem de senyalitzar-lo.

        # Aturar InsultService Pyro endpoint
        if insult_service_pyro_process.is_alive():
            print("Launcher: Terminating InsultService Pyro process...")
            insult_service_pyro_process.terminate()  # Forcem la terminació
            insult_service_pyro_process.join(timeout=5)

        # Els processos de fons de InsultService (notifier, listener) són daemon,
        # així que s'aturaran quan el seu procés pare (aquest launcher) acabi,
        # o quan insult_service_pyro_process acabi si fos el seu pare directe.
        # Com que són daemon=True en la seva creació, no cal join explícit aquí si el pare acaba.

        print("Launcher: Shutdown complete.")