# config.py

# RabbitMQ Configuration
RABBITMQ_HOST = 'localhost'
RABBITMQ_PORT = 5672
RABBITMQ_USER = 'guest'
RABBITMQ_PASS = 'guest'
RABBITMQ_VHOST = '/'
RABBITMQ_URL = f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASS}@{RABBITMQ_HOST}:{RABBITMQ_PORT}{RABBITMQ_VHOST}"

TEXT_QUEUE_NAME = 'text_queue'  # Per filtrar textos
INSULTS_PROCESSING_QUEUE_NAME = 'insults_processing_queue' # NOVA CUA per processar insults
# INSULTS_EXCHANGE_NAME ja no s'usarà per a la ingesta d'insults amb escalat dinàmic.
# Podem redefinir-lo o eliminar-lo si no té altres usos.
# Per ara, el comentem per evitar confusió amb l'ús anterior.
INSULTS_EXCHANGE_NAME = 'insults_exchange'
INSULTS_BROADCAST_EXCHANGE_NAME = 'Insults_broadcast' # Per a InsultService notifiqui als subscriptors

# Redis Configuration
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_INSULTS_SET_KEY = 'insults_set'
REDIS_CENSORED_TEXTS_LIST_KEY = 'censored_texts_list'
REDIS_FILTER_PROCESSED_COUNTER_KEY = 'filter_processed_total'
REDIS_INSULTS_PROCESSED_COUNTER_KEY = 'insults_processed_total' # NOU comptador
REDIS_PROCESSED_COUNTER_KEY = 'processed'

# Pyro Configuration
PYRO_NS_HOST = 'localhost'
PYRO_NS_PORT = 9090
PYRO_INSULT_SERVICE_NAME = 'example.insultservice'
PYRO_SCALER_MANAGER_NAME = 'example.scalermanager'
PYRO_DAEMON_HOST = "localhost"

# Dynamic Scaling Parameters for InsultFilterWorker pool (text_queue)
FILTER_MIN_WORKERS = 1
FILTER_MAX_WORKERS = 10
FILTER_WORKER_CAPACITY_C = 5.0 # msg/s
FILTER_TARGET_RESPONSE_TIME_TR = 5.0 # s
FILTER_SCALING_INTERVAL = 10  # s

# Dynamic Scaling Parameters for InsultProcessorWorker pool (insults_processing_queue) - NOU
INSULT_PROCESSOR_MIN_WORKERS = 1
INSULT_PROCESSOR_MAX_WORKERS = 5
INSULT_PROCESSOR_WORKER_CAPACITY_C = 10.0 # insults/s (afegir a Redis és ràpid)
INSULT_PROCESSOR_TARGET_RESPONSE_TIME_TR = 3.0 # s
INSULT_PROCESSOR_SCALING_INTERVAL = 15 # s (pot ser diferent)

# Insult Service (Broadcaster) Configuration
NUM_INSULT_NOTIFIERS = 1  # Nombre de processos que notifiquen als subscriptors