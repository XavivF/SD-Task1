# SD-Task1
Scaling distributed Systems using direct and indirect communication middleware

# Configuration of docker containers
The following steps explain how to set up and run Redis and RabbitMQ containers using Docker:

1. **Pull the Redis Image**:  
Download the latest Redis image from Docker Hub.  

```bash
sudo docker pull redis
```
2. **Run the Redis Container**:
Start a Redis container named redis in detached mode, exposing port 6379 for external access.

```bash
sudo docker run --name redis -d -p 6379:6379 redis
```
3. **Pull the RabbitMQ Image**:
Download the RabbitMQ image with the management plugin from Docker Hub.

```bash
sudo docker pull rabbitmq:management
```
4. Run the RabbitMQ Container:
Start a RabbitMQ container named rabbitmq-p in detached mode, exposing ports 5672 (for AMQP connections) and 15672 (for the management interface).

```bash
sudo docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:management
```

# How to Run the Different Tests

## Single-Node 
### XMLRPC Implementation

#### 1. Start Insult Service Instances

This section provides instructions to set up and run the XML-RPC based implementation of the Insult Service and Insult Filter, including the client demonstration and the stress test.

### Running the Services

You need to start each service and the subscriber in a separate terminal or command prompt window. Ensure you are in the directory containing the Python files.

#### 1. Start the Insult Service:
```
python3 InsultService.py
```

This will start the service listening on `localhost:8000`. You should see a "Server is running..." message.

#### 2. Start the Insult Filter:

```bash
python3 InsultFilter.py
```
This will start the filter service listening on `localhost:8010`. You should see a "Server is running..." message.

#### 3. Start the Insult Subscriber:
```bash 
python3 InsultSubscriber.py
```
This will start the subscriber listening on `localhost:8001`. You should see a "Subscriber running on port 8001..." message.

**Important:** Ensure all three services/subscriber are running before starting any client or test script.

### 4. Run the Client (Demonstration and Testing)

Open another terminal window and run the client script. This client interacts with the services, adds initial insults, sends text to be filtered, and triggers the broadcast mechanism.
```bash
python3 InsultClient.py
```
The client will:
* Add the subscriber (`InsultSubscriber.py`) to the service.
* Add a predefined list of insults to both the Service and the Filter.
* Periodically send random texts to the Filter service.
* Periodically request an insult from the Service and notify subscribers.
* Allow interactive commands:
    * Press `I` and Enter to see the current list of insults held by the Insult Service.
    * Press `T` and Enter to see the list of filtered texts held by the Insult Filter.
    * Press `K` and Enter to terminate the client and the spawned processes.

Observe the output in the terminals where the services and subscriber are running to see the interactions (e.g., insults being added, texts being filtered, subscriber receiving notifications).

### 5. Run the Stress Test

The StressTest.py script is used to evaluate the performance of specific functionalities under load. Open a new terminal window to run it.
```bash
python3 StressTest.py <mode> [options]
```
**Arguments:**

* `<mode>`: Specifies which functionality to test. Choose either add_insult or filter_text.

**Options:**

* -d, --duration: Test duration in seconds (default: 10).
* -c, --concurrency: Number of concurrent client processes to run (default: 10).

**Example:**

```bash
python3 StressTest.py add_insult -d 30 -c 20
```

The script will output the total time, total requests made by clients, total requests processed by the server (obtained via a method call), total errors, and calculated throughputs.

**Note:** The services (InsultService.py, InsultFilter.py) must be running before you execute the StressTest.py. The InsultSubscriber.py is not directly involved in the current stress test modes, but it doesn't hurt to have it running.
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

#### 3. Start the Insult Service

```bash
    python3 InsultService.py
```

### 4. Start the Insult Filter

```bash
    python3 InsultFilter.py
```

Leave these services running while you execute the stress tests. They will handle incoming 
requests via Redis and expose their processed counts via Pyro.

#### 5. Start the Subscriber

```bash
    python3 InsultSubscriber.py
```

Keep this terminal open to see received insults.

#### 6. Run the Client (Demonstration and Manual Testing)

```
python3 InsultClient.py
```

#### 7. Run the Stress Test (Performance Analysis)
The `StressTest.py` script accepts the following command-line arguments:

* `mode`: **Required**. The functionality to test. Choose either `add_insult` or `filter_text`.
  * `add_insult`: Tests adding insults to the system (interacts with `InsultService` via Redis Pub/Sub).
  * `filter_text`: Tests filtering texts (interacts with `InsultFilter` via Redis Lists/Queues).
* `--host`: Redis server host (default: `localhost`).
* `--port`: Redis server port (default: `6379`).
* `--insult-channel`: Name of the Redis channel for publishing insults (default: `Insults_channel`). Used with `mode=add_insult`.
* `--work-queue`: Name of the Redis list/queue for filtering texts (default: `Work_queue`). Used with `mode=filter_text`.
* `-d`, `--duration`: Test duration in seconds (default: `10`).
* `-c`, `--concurrency`: Number of concurrent client processes simulating load (default: `10`).


This test simulates multiple clients publishing insults to the Redis channel, which the `InsultService` listens to.

```bash
python3 StressTest.py add_insult -d <duration_in_seconds> -c <number_of_processes>
```

### RabbitMQ Implementation

#### 1. Start the RabbitMQ Docker Container

```bash
docker start rabbitmq
```

#### 2. Start the Pyro4 Name Server
The RabbitMQ implementation uses Pyro4 only for retrieving performance statistics from the service
and filter instances. You need to run the Pyro4 Name Server.
```bash
python3 -m Pyro4.naming
```

#### 3. Start the Insult Service

```bash
python3 InsultService.py
```

#### 4. Start the Insult Filter

```bash
python3 InsultFilter.py
```

#### 5. Start the Subscriber

```bash
python3 InsultSubscriber.py
```

#### 6. Run the Client (Demonstration and Manual Testing)

```bash
python3 InsultClient.py
```

#### 7. Run the Stress Test (Performance Analysis)
The `StressTest.py` script for RabbitMQ is used for performance analysis. It uses multiprocessing to push a
high volume of messages directly to the relevant RabbitMQ queues/exchanges (insults_exchange or text_queue).

The `StressTest.py` script accepts the following command-line arguments:

* `mode`: **Required**. The functionality to test. For RabbitMQ, choose either `add_insult` or `filter_text`.
    * `add_insult`: Tests adding insults to the system (interacts with `InsultService` via the `insults_exchange` fanout exchange).
    * `filter_text`: Tests filtering texts (interacts with `InsultFilter` via the `text_queue` work queue).
* `--host`: RabbitMQ server host (default: `localhost`).
* `--insult-exchange`: Name of the RabbitMQ exchange for adding insults (default: `insults_exchange`). Used with `mode=add_insult`.
* `--work-queue`: Name of the RabbitMQ queue for filtering texts (default: `text_queue`). Used with `mode=filter_text`.
* `--pyro-name`: The Pyro name of the service whose statistics you want to retrieve. Use `rabbit.service` for the Insult Service test and `rabbit.filter` for the Insult Filter test.
* `-d`, `--duration`: Test duration in seconds (default: `10`).
* `-c`, `--concurrency`: Number of concurrent client processes simulating load (default: `10`).

```bash
python3 StressTest.py add_insult --host <rabbitmq_host> --insult-exchange insults_exchange --pyro-name rabbit.service -d <duration_in_seconds> -c <number_of_processes>
```

Example:
```bash
python3 StressTest.py add_insult -d 60 -c 50
```

### Pyro Implementation

#### 1. Start the Name Server

Pyro requires a Name Server to discover the services. You must start this first in a dedicated terminal window.
```bash
python3 -m Pyro4.naming
```
You should see output indicating the Name Server has started. Keep this terminal open.

#### 2. Start the Insult Service:

Open separate terminal windows for each service and the subscriber. Ensure the Pyro Name Server is running before starting these.
```bash
python3 InsultService.py
```

#### 3. Start the Filter Service:
```bash
python3 InsultFilter.py
```
This script will connect to the Name Server and register the service under the name pyro.filter.

#### 4. Start the Insult Subscriber:
```bash
python3 InsultSubscriber.py
```

**Important:** Ensure the Name Server, the Insult Service, the Insult Filter, and the Insult Subscriber are all running before proceeding to the client or stress test.

#### 5. Run the Client (Demonstration and Testing)

Open another terminal window to run the client script. This client interacts with the services, adds initial insults, sends text to be filtered, and helps demonstrate the broadcast mechanism.
```bash
python3 InsultClient.py
```
The client will:
* Automatically find the services via the Name Server.
* Add a predefined list of insults to both the Service and the Filter.
* Start separate processes for periodically sending random texts to the Filter service and for triggering the broadcast of a random insult from the Service.
* Allow interactive commands:
    * Press `I` and Enter to see the current list of insults held by the Insult Service.
    * Press `T` and Enter to see the list of filtered texts held by the Insult Filter.
    * Press `K` and Enter to terminate the client and its spawned processes.

Observe the output in the terminals where the services and subscriber are running to see the interactions (e.g., insults being added, texts being filtered, subscriber receiving notifications).

#### 6. Running the Stress Test

The StressTest.py script is designed to evaluate the performance of specific functionalities under load. Open a new terminal window to run it.
```bash
python3 StressTest.py <mode> [options]
```
**Arguments:**

* `<mode>`: Specifies which functionality to test. Choose either add_insult or filter_text.

**Options:**

* -d, --duration: The duration of the test in seconds (default is 10).
* -c, --concurrency: The number of concurrent client processes to run (default is 10).

**Example:**

```bash
python3 StressTest.py -c 30 filter_text
```
The script will output the total time, total requests made by clients, total requests processed by the server (obtained via a method call), total errors, and calculated throughputs.

**Note:** The Pyro Name Server and the relevant service (InsultService.py for add_insult mode, InsultFilter.py for filter_text mode) must be running before you execute StressTest.py. The InsultSubscriber.py is not directly involved in the current stress test modes, but it doesn't hurt to have it running.


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
* mode: Choose either add_insult to test the Insult Service (via LB) or filter_text to test the Insult Filter (via LB).
* -u, --lb_url: URL of the XML-RPC Load Balancer (default: http://localhost:9000/RPC2).
* -m, --messages: Number of messages to send.
* -n, --num-service-instances: Number of service instances to retrieve stats from (default: 1)

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

#### 6. Run the Client (Demonstration and Manual Testing)

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

Once running, you can use the interactive commands in the client's terminal:
* I: Get the list of insults from the service instances (via Pyro4).
* T: Get the list of censored texts from the filter instances (via Pyro4).
* K: Stop the client's background processes and exit.

#### 7. Run the Stress Test (Performance Analysis)

The StressTest.py script for Redis is used for performance analysis. It uses multiprocessing 
to push a high volume of messages directly to the relevant Redis queues (Insults_queue or 
Work_queue).

```bash
python3 StressTest.py <mode> [options]
```

**Arguments**:

* mode: Choose either add_insult to test the Insult Service's processing of the Insults_queue
or filter_text to test the Insult Filter's processing of the Work_queue.
* -m, --messages: Number of messages to send.
* --host: Redis server host (default: localhost).
* --port: Redis server port (default: 6379).
* --insult-queue: Name of the Redis queue for publishing insults (default: Insults_queue).
* --work-queue: Name of the Redis list/queue for filtering texts (default: Work_queue).
* -n, --num-instances: Required. The total number of backend service/filter instances 
(InsultService.py or InsultFilter.py, depending on the mode) that are running.

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

#### 1. Start the RabbitMQ Docker Container

```bash
docker start rabbitmq
```

#### 2. Start the Pyro4 Name Server

The RabbitMQ implementation uses Pyro4 only for retrieving performance statistics from the service and 
filter instances. You need to run the Pyro4 Name Server.

```bash
python3 -m Pyro4.naming
```

#### 3. Start Insult Service Instances

Run one or more instances of the InsultService.py. These instances will consume insults from a RabbitMQ 
queue and publish random insults to another RabbitMQ fanout exchange 
(Insults_broadcast). Each instance needs a unique --instance-id for Pyro4 registration.
```bash
python3 InsultService.py --instance-id <id_service_1>
# Example:
# python3 InsultService.py --instance-id 1

python3 InsultService.py --instance-id <id_service_2>
# Example:
# python3 InsultService.py --instance-id 2

# Add more instances as needed for scaling tests (e.g., for 3 nodes)
# python3 InsultService.py --instance-id 3
```

Keep these terminals open. You should see messages indicating they are connecting to RabbitMQ and starting 
processes.

#### 4. Start Insult Filter Instances

Run one or more instances of the InsultFilter.py. These instances will consume texts from a RabbitMQ queue 
(text_queue) and insults from the insults_exchange. Each instance also needs a unique --instance-id for 
Pyro4 registration.

```bash
python3 InsultFilter.py --instance-id <id_filter_1>
# Example:
# python3 InsultFilter.py --instance-id 11

python3 InsultFilter.py --instance-id <id_filter_2>
# Example:
# python3 InsultFilter.py --instance-id 12

# Add more instances as needed for scaling tests (e.g., for 3 nodes)
# python3 InsultFilter.py --instance-id 13
```
Keep these terminals open. You should see messages indicating they are connecting to RabbitMQ and starting processes.

#### 5. Start the Subscriber (Not needed if running the StressTest.py)

The Subscriber (InsultSubscriber.py) listens directly to the RabbitMQ publish/subscribe exchange 
(Insults_broadcast) for random insults broadcasted by the Insult Service instances.

```bash
python3 InsultSubscriber.py
```
Keep this terminal open to see received insults.

#### 6. Run the Client (Demonstration - Producer + Stats Viewer)

The InsultClient.py in the RabbitMQ implementation acts as a producer, pushing initial insults and texts 
to the relevant RabbitMQ queues/exchanges. It also connects to the running service and filter instances 
via Pyro4 to retrieve lists of insults and censored texts.

You need to provide the number of running service instances using the -ns or --num-instances-service and running filter instances using the -nf or --num-instances-filter argument, as the client 
uses this to connect to the correct Pyro4 names (e.g., rabbit.service.1, rabbit.service.2, etc.).

```bash
python3 InsultClient.py -ns <number_of_service_instances> -nf <number_of_filter_instances>
```

**Example**:
```bash
python3 InsultClient.py -ns 2 -nf 1
```

Note: The client currently assumes the same number of service and filter instances and connects to Pyro 
names rabbit.service.1 to rabbit.service.n and rabbit.filter.1 to rabbit.filter.n

Once running, you can use the interactive commands in the client's terminal:
* I: Get the list of insults from the service instances (via Pyro4).
* T: Get the list of censored texts from the filter instances (via Pyro4).
* K: Stop the client's background processes and exit.

#### 7. Run the Stress Test (Performance Analysis)

The StressTest.py script for RabbitMQ is used for performance analysis. It uses multiprocessing to push a 
high volume of messages directly to the relevant RabbitMQ queues (insult_queue or text_queue). 
After the test duration, it connects to the Pyro4 Name Server to retrieve the total processed counts from 
the running service/filter instances specified by their IDs.

```bash
python3 StressTest.py <mode> [options]
```

**Arguments**:
* mode: Choose either add_insult to test the Insult Service's processing of the insult_queue or 
filter_text to test the Insult Filter's processing of the text_queue.
* -m, --messages: Number of messages to send.
* --host: RabbitMQ server host (default: localhost).
* --insult-queue: Name of the RabbitMQ queue for publishing insults (default: insult_queue).
* --work-queue: Name of the RabbitMQ queue for filtering texts (default: text_queue).
* -n, --num-instances: Required. The total number of backend service/filter instances (InsultService.py or 
InsultFilter.py, depending on the mode) that are running.

**Example**:
```bash
python3 StressTest.py add_insult -d 10 -c 5 -n 2
```

**Important Notes**:
* Ensure the RabbitMQ server and Pyro4 Name Server are running before starting any service/filter instances.
* Ensure all service and filter instances are running and have registered with the Pyro4 Name Server before running the InsultClient.py or StressTest.py if you want to collect statistics via Pyro4.
* Each component should ideally be run in its own terminal window for clarity and easy management.

### Pyro Implementation

#### 1. Start the Pyro4 Name Server

The Pyro4 Name Server is essential for the system to work, as components find each other through it.

```bash
python3 -m Pyro4.naming
```

Keep this terminal open.

#### 2. Start Insult Service Instances

Run one or more instances of the InsultService.py. Each instance is exposed as a Pyro4 object and registers
itself with the Name Server using a unique name based on its instance ID (e.g., pyro.service.1). Each 
instance also needs a specific port to bind its Pyro4 daemon to.

```bash
python3 InsultService.py --port <port_service_1> --instance-id <id_service_1>
# Example:
# python3 InsultService.py --port 8001 --instance-id 1

python3 InsultService.py --port <port_service_2> --instance-id <id_service_2>
# Example:
# python3 InsultService.py --port 8002 --instance-id 2

# Add more instances as needed for scaling tests
# python3 InsultService.py --port 8003 --instance-id 3
```

Keep these terminals open.

#### 3. Start Insult Filter Instances

Similarly, start one or more instances of the InsultFilter.py. Each registers with the Name Server using 
a unique name based on its instance ID (e.g., pyro.filter.1). Each also needs a specific port.

```bash
python3 InsultFilter.py --port <port_filter_1> --instance-id <id_filter_1>
# Example:
# python3 InsultFilter.py --port 8011 --instance-id 11

python3 InsultFilter.py --port <port_filter_2> --instance-id <id_filter_2>
# Example:
# python3 InsultFilter.py --port 8012 --instance-id 12

# Add more instances as needed for scaling tests
# python3 InsultFilter.py --port 8013 --instance-id 13
```

Keep these terminals open.

#### 4. Start the Load Balancer

The Load Balancer (LoadBalancer.py) acts as the central entry point for clients. It needs to know the Pyro4
names of all running Insult Service and Insult Filter instances so it can create proxies to them. The Load
Balancer also registers itself with the Name Server as pyro.loadbalancer.

```bash
python3 LoadBalancer.py --names-service <service_name_1> <service_name_2> ... --names-filter <filter_name_1> <filter_name_2> ...
```

**Example**:

```bash
python3 LoadBalancer.py --names-service pyro.service.1 pyro.service.2 --names-filter pyro.filter.1 pyro.filter.2
```

Keep this terminal open.

#### 5. Start the Subscriber

The Subscriber (InsultSubscriber.py) exposes itself as a Pyro4 object and registers with the Name Server. 
It then connects to the Load Balancer (pyro.loadbalancer) and tells it to subscribe this subscriber to 
broadcasts.

```bash
python3 InsultSubscriber.py
```

Keep this terminal open to see received insults.

#### 6. Run the Client (Demonstration and Manual Testing)

The InsultClient.py is a basic client to interact with the system. It connects to the Load Balancer 
(pyro.loadbalancer) and sends requests (add insults, filter text) and fetches results. It also starts 
background processes for broadcasting and sending text.

```bash
python3 InsultClient.py
```

Once running, you can use the interactive commands in the client's terminal:
* I: Get the list of insults (via LB).
* T: Get the list of censored texts (via LB).
* K: Stop the client's background processes and exit.

#### 7. Run the Stress Test (Performance Analysis)

The StressTest.py script is used for performance analysis. It sends a high volume of requests to the Load 
Balancer (pyro.loadbalancer) using multiple processes. It also retrieves the total processed counts from 
the Load Balancer.

```bash
python3 StressTest.py <mode> [options]
```

**Arguments**:
* mode: Choose either add_insult to test the Insult Service (via LB) or filter_text to test the Insult 
Filter (via LB).
* -m, --messages: Number of messages to send.
* -n, --num-instances: Required. The total number of backend service/filter instances.
* --ns-host: Host of the Pyro Name Server (optional, default: locate via broadcast).
* --ns-port: Port of the Pyro Name Server (optional, default: locate via broadcast).

**Example**:
```bash
python3 StressTest.py add_insult -d 15 -c 5
```

**Important Notes:**
* Ensure the Pyro4 Name Server is running before starting any other components.
* Ensure all service and filter instances are running and have registered with the Name Server before 
starting the Load Balancer.

## Multiple-Nodes Dynamic Scaling