import logging

# Configure your global logger
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

logging.basicConfig(
    level=logging.DEBUG,  # You can still use logger.debug/info etc.
    format=LOG_FORMAT,
    datefmt=DATE_FORMAT
)

# Silence everything else
logging.getLogger("pymongo").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)
logging.getLogger("asyncio").setLevel(logging.CRITICAL)
logging.getLogger("langsmith.client").setLevel(logging.CRITICAL)
logging.getLogger("python_multipart.multipart").setLevel(logging.CRITICAL)
 

def get_logger(name: str = "MyApp"):
    """Return a logger for your app"""
    return logging.getLogger(name)
