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

### RabbitMQ Implementation

### Pyro Implementation

## Multiple-Nodes Dynamic Scaling