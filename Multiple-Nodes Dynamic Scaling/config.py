# RabbitMQ Configuration
RABBITMQ_HOST = 'localhost'
RABBITMQ_PORT = 5672
RABBITMQ_USER = 'guest'
RABBITMQ_PASS = 'guest'
RABBITMQ_VHOST = '/'
RABBITMQ_URL = f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASS}@{RABBITMQ_HOST}:{RABBITMQ_PORT}{RABBITMQ_VHOST}"

TEXT_QUEUE_NAME = 'text_queue'
INSULTS_PROCESSING_QUEUE_NAME = 'add_insult_queue'
INSULTS_EXCHANGE_NAME = 'insults_exchange'
INSULTS_BROADCAST_EXCHANGE_NAME = 'Insults_broadcast'

# Redis Configuration
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_INSULTS_SET_KEY = 'insults_set'
REDIS_CENSORED_TEXTS_LIST_KEY = 'censored_texts_list'
REDIS_PROCESSED_COUNTER_KEY = 'processed'

# Pyro Configuration
PYRO_NS_HOST = 'localhost'
PYRO_NS_PORT = 9090
PYRO_INSULT_SERVICE_NAME = 'pyro.insultservice'
PYRO_SCALER_MANAGER_NAME = 'pyro.scalermanager'
PYRO_DAEMON_HOST = "localhost"

# Dynamic Scaling Parameters for InsultFilterWorker pool (text_queue)
FILTER_MIN_WORKERS = 1
FILTER_MAX_WORKERS = 150
FILTER_WORKER_CAPACITY_C = 1159.75 # msg/s
FILTER_AVERAGE_RESPONSE_TIME = 0.00086225479 # s
FILTER_ARRIVAL_RATE = 50000 # msg/s
FILTER_SCALING_INTERVAL = 2  # s

# Dynamic Scaling Parameters for InsultProcessorWorker pool (insults_processing_queue) - NOU
INSULT_PROCESSOR_MIN_WORKERS = 1
INSULT_PROCESSOR_MAX_WORKERS = 20
INSULT_PROCESSOR_WORKER_CAPACITY_C = 1179.38 # insults/s (afegir a Redis és ràpid)
INSULT_PROCESSOR_AVERAGE_RESPONSE_TIME = 0.00084790313 # s
INSULT_ARRIVAL_RATE = 45000 # insults/s
INSULT_PROCESSOR_SCALING_INTERVAL = 2 # s (it can be changed)


# Insult Service (Broadcaster) Configuration
NUM_INSULT_NOTIFIERS = 1  # Number of processes that notify subscribers