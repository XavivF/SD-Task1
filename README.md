# SD-Task1
Scaling distributed Systems using direct and indirect communication middleware

# How to Run the Different Tests

## Single-Node 
### XMLRPC Implementation

### Redis Implementation

### RabbitMQ Implementation

### Pyro Implementation

## Multiple-Nodes Static Scaling
### XMLRPC Implementation

#### 1. Start Insult Service Instances

You can run multiple instances of the `InsultService.py` on different ports to simulate
multiple nodes for scaling. Each instance needs a unique port.

```bash
python3 InsultService.py --port <port_service_1>
# Example:
# python3 InsultService.py --port 8001

python3 InsultService.py --port <port_service_2>
# Example:
# python3 InsultService.py --port 8002

# Add more instances as needed for scaling tests (e.g., for 3 nodes)
# python3 InsultService.py --port 8003
```

#### 2. Start the Insult Filter Instances

Similarly, start one or more instances of the InsultFilter.py on different ports.

```bash
python3 InsultFilter.py --port <port_filter_1>
# Example:
# python3 InsultFilter.py --port 8011

python3 InsultFilter.py --port <port_filter_2>
# Example:
# python3 InsultFilter.py --port 8012

# Add more instances as needed for scaling tests (e.g., for 3 nodes)
# python3 InsultFilter.py --port 8013
```

#### 3. Start the Load Balancer

The Load Balancer (LoadBalancer.py) needs to know the URLs of all running
Insult Service and Insult Filter instances. Specify them using the --service_urls
and --filter_urls arguments. The URLs should be in the format http://localhost:<port>/RPC2.

```bash
python3 LoadBalancer.py --port <load_balancer_port> --service_urls <service_url_1> <service_url_2> ... --filter_urls <filter_url_1> <filter_url_2> ...
```

**Example** (using the ports from the examples above with 2 service and 3 filter instances):

```bash
python3 LoadBalancer.py --port 9000 --service_urls http://localhost:8001/RPC2 http://localhost:8002/RPC2 --filter_urls http://localhost:8011/RPC2 http://localhost:8012/RPC2 http://localhost:8013/RPC2
```

#### 4. Start the Subscriber

The Subscriber (InsultSubscriber.py) listens for broadcasted insults from the Insult Service 
instances. It needs a specific port to run on. The InsultClient.py is configured to register
this subscriber with the Load Balancer upon startup, which in turn registers it with the backend
service instances.

```bash
python3 InsultSubscriber.py --subscriber-port <subscriber_port>
```

**Example:**

```bash
python3 InsultSubscriber.py --subscriber-port 8050
```

#### 5. Run the Client (Demonstration and Manual Testing)

The InsultClient.py is a basic client to interact with the system via the Load Balancer. It demonstrates adding insults, sending text for filtering, and is configured to register the Subscriber with the Load Balancer upon startup. It also has background processes simulating the broadcast and filtering load.

You need to provide the Load Balancer's port and the Subscriber's port.
```bash
python3 InsultClient.py --loadbalancer-port <load_balancer_port> --subscriber_port <subscriber_port>
```
**Example:**
```bash
python3 InsultClient.py --loadbalancer-port 9000 --subscriber_port 8050
```
Once running, you can use the interactive commands in the client's terminal:
- I: Get the list of insults from a service instance (via LB). 
- T: Get the list of censored texts from a filter instance (via LB).
- K: Stop the client's background processes and exit.

#### 6. Run the Stress Test (Performance Analysis)

The StressTest.py script is designed for performance analysis by generating a high volume of
requests to the Load Balancer using multiple processes.

You must specify the test mode (add_insult or filter_text), and optionally the duration,
concurrency, and the lb_url.

```bash
python3 StressTest.py <mode> [options]
```
**Arguments:**
- mode: Choose either add_insult to test the Insult Service (via LB) or filter_text to test the Insult Filter (via LB).
- -d, --duration: Test duration in seconds (default: 10).
- -c, --concurrency: Number of concurrent client processes to run (default: 10).
- -u, --lb_url: URL of the XML-RPC Load Balancer (default: http://localhost:9000/RPC2).

**Example:**
```bash
python3 StressTest.py add_insult -d 30 -c 50 -u http://localhost:9000/RPC2
```

**Important Notes:**
- Ensure all server instances (InsultService.py, InsultFilter.py), the Load Balancer 
(LoadBalancer.py), and the Subscriber (InsultSubscriber.py) are running before starting
the InsultClient.py or StressTest.py.
- For static scaling analysis, you will typically run the StressTest.py with the same 
configuration (duration, concurrency, mode) but with the Load Balancer configured to use
a varying number of backend service/filter instances (e.g., 1, 2, 3 instances). Remember
to restart the Load Balancer with the correct --service_urls and --filter_urls each time
you change the number of backend instances.
- Each component should ideally be run in its own terminal window for clarity and easy management.
### Redis Implementation

#### 1. Start the Redis Docker Container
```bash
docker start redis
```
#### 2. Start the Pyro4 Name Server

The Redis implementation uses Pyro4 only for retrieving performance statistics from the service
and filter instances. You need to run the Pyro4 Name Server.
```bash
python3 -m Pyro4.naming
```
Keep this terminal open.

#### 3. Start Insult Service Instances

Run one or more instances of the InsultService.py. These instances will consume insults from a 
Redis queue (Insults_queue) and publish random insults to a Redis channel (Insults_broadcast). 
Each instance needs a unique --instance-id for Pyro4 registration.

```bash
python3 InsultService.py --redis-host localhost --redis-port 6379 --instance-id <id_service_1>
# Example:
# python3 InsultService.py --redis-host localhost --redis-port 6379 --instance-id 1

python3 InsultService.py --redis-host localhost --redis-port 6379 --instance-id <id_service_2>
# Example:
# python3 InsultService.py --redis-host localhost --redis-port 6379 --instance-id 2

# Add more instances as needed for scaling tests
# python3 InsultService.py --redis-host localhost --redis-port 6379 --instance-id 3
```

Keep these terminals open. You should see messages indicating they are starting listener 
and notifier processes.

#### 4. Start the Insult Filter Instances

Run one or more instances of the InsultFilter.py. These instances will consume texts from a 
Redis queue (Work_queue) and store filtered results in a Redis list (RESULTS). Each instance 
also needs a unique --instance-id for Pyro4 registration. The only required argument is the
--instance-id or -id.

```bash
python3 InsultFilter.py --redis-host localhost --redis-port 6379 --instance-id <id_filter_1>
# Example:
# python3 InsultFilter.py --redis-host localhost --redis-port 6379 --instance-id 11

python3 InsultFilter.py --redis-host localhost --redis-port 6379 --instance-id <id_filter_2>
# Example:
# python3 InsultFilter.py --redis-host localhost --redis-port 6379 --instance-id 12

# Add more instances as needed for scaling tests
# python3 InsultFilter.py --redis-host localhost --redis-port 6379 --instance-id 13
```
Keep these terminals open. You should see messages indicating they are starting filtering processes.

#### 5. Start the Subscriber (Not needed if running the StressTest.py)

The Subscriber (InsultSubscriber.py) listens directly to the Redis publish/subscribe 
channel (Insults_broadcast) for random insults broadcasted by the Insult Service instances.

```bash
python3 InsultSubscriber.py
```

Keep this terminal open to see received insults.

#### 6. Run the Client (Not recommended if running the StressTest.py)

The InsultClient.py in the Redis implementation acts as a simple producer, pushing initial 
insults to the Insults_queue and then periodically pushing texts to the Work_queue. It 
interacts directly with Redis, not with the service/filter instances.
It is not recommended to run the client if you are running the StressTest.py, as the counter of
the processed insults will be incorrect because of the initial added insults.

```bash
python3 InsultClient.py
```

This client will start pushing messages to Redis. You can observe the service and filter 
instances picking up these tasks.

#### 7. Run the Stress Test (Performance Analysis)

The StressTest.py script for Redis is used for performance analysis. It uses multiprocessing 
to push a high volume of messages directly to the relevant Redis queues (Insults_queue or 
Work_queue).

```bash
python3 StressTest.py <mode> [options]
```
Arguments:

* mode: Choose either add_insult to test the Insult Service's processing of the Insults_queue
or filter_text to test the Insult Filter's processing of the Work_queue.
* -d, --duration: Test duration in seconds (default: 10).
* -c, --concurrency: Number of concurrent client processes that push messages to Redis 
(default: 10).
* --host: Redis server host (default: localhost).
* --port: Redis server port (default: 6379).
* --insult-queue: Name of the Redis queue for publishing insults (default: Insults_queue).
* --work-queue: Name of the Redis list/queue for filtering texts (default: Work_queue).
* -n, --num-service-instances: Required. The total number of backend service/filter instances 
(InsultService.py or InsultFilter.py, depending on the mode) that are running. The stress test 
script will try to get stats from redis.insultservice.1 up to redis.insultservice.n for 
add_insult mode, or redis.insultfilter.1 up to redis.insultfilter.n for filter_text.

Example:
```bash
python3 StressTest.py add_insult -d 30 -c 50 -n 2
```

**Important Notes:**
* Ensure the Redis server and Pyro4 Name Server are running before starting any service/filter 
instances.
* Ensure all service and filter instances are running and have registered with the Pyro4 Name
Server before running the StressTest.py.
* Each component should ideally be run in its own terminal window for clarity and easy management.

### RabbitMQ Implementation

### Pyro Implementation

## Multiple-Nodes Dynamic Scaling