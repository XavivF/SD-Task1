import redis
import config

class RedisManager:
    def __init__(self):
        try:
            self.r = redis.Redis(host=config.REDIS_HOST,
                                 port=config.REDIS_PORT,
                                 db=config.REDIS_DB,
                                 decode_responses=True)
            self.r.ping()
            print("Successfully connected to Redis.")
        except redis.exceptions.ConnectionError as e:
            print(f"Error connecting to Redis: {e}")
            raise

    def add_insult(self, insult: str) -> bool:
        """Adds an insult to the set. Returns True if added, False if already exists."""
        return self.r.sadd(config.REDIS_INSULTS_SET_KEY, insult.lower()) == 1

    def get_all_insults(self) -> list:
        """Returns a list of all unique insults."""
        return list(self.r.smembers(config.REDIS_INSULTS_SET_KEY))

    def is_insult(self, word: str) -> bool:
        """Checks if a word is in the insults set."""
        return self.r.sismember(config.REDIS_INSULTS_SET_KEY, word.lower())

    def add_censored_text(self, text: str):
        """Adds a censored text to the list."""
        self.r.rpush(config.REDIS_CENSORED_TEXTS_LIST_KEY, text)

    def get_censored_texts(self, start: int = 0, end: int = -1) -> list:
        """Returns a range of censored texts."""
        return self.r.lrange(config.REDIS_CENSORED_TEXTS_LIST_KEY, start, end)

    def get_censored_texts_count(self) -> int:
        """Returns the total number of censored texts."""
        return self.r.llen(config.REDIS_CENSORED_TEXTS_LIST_KEY)

    def increment_processed_count(self, value: int = 1) -> int:
        """Increments the total processed texts counter."""
        return self.r.incr(config.REDIS_PROCESSED_COUNTER_KEY, value)

    def get_processed_count(self) -> int:
        """Gets the total processed texts counter."""
        val = self.r.get(config.REDIS_PROCESSED_COUNTER_KEY)
        return int(val) if val else 0

    def reset_processed_count(self):
        """Resets the total processed texts counter."""
        self.r.delete(config.REDIS_PROCESSED_COUNTER_KEY)

# Singleton instance
redis_cli = RedisManager()