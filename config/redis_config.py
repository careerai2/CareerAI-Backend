import redis
from config.env_config import redis_host, redis_port, redis_username, redis_password
from services.redis_service import RedisService



redis_client = redis.Redis(
    host=redis_host,
    port=redis_port,
    decode_responses=True,
    username=redis_username,
    password=redis_password
)
redis_service = RedisService(redis_client)
