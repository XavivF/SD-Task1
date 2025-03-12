import pika
import redis

def main():
    redis_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    channel.queue_declare(queue='INSULTS')

    def callback(ch, method, properties, body):
        insult = body.decode('utf-8')
        if not redis_client.sismember('INSULTS_SET', insult):
            redis_client.sadd('INSULTS_SET', insult)
            redis_client.rpush('INSULTS', insult)
            print(f" [x] Added '{insult}' to Redis")
        else:
            print(f" [x] '{insult}' is already in Redis")

    channel.basic_consume(queue='INSULTS', on_message_callback=callback, auto_ack=True)
    print(' [*] Waiting for messages. To exit press CTRL+C')
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("\nInsultConsumer stopped.")
    finally:
        connection.close()

if __name__ == "__main__":
    main()
