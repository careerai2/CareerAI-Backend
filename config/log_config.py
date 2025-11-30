# import logging
# from rich.logging import RichHandler
# from datetime import datetime

# # Configure your global logger
# LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
# DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# logging.basicConfig(
#     level=logging.DEBUG,
#     format=LOG_FORMAT,
#     datefmt=DATE_FORMAT,
#     handlers=[RichHandler(rich_tracebacks=True)]
# )




# # Silence noisy libraries
# logging.getLogger("pymongo").setLevel(logging.CRITICAL)
# logging.getLogger("urllib3").setLevel(logging.CRITICAL)
# logging.getLogger("asyncio").setLevel(logging.CRITICAL)
# logging.getLogger("langsmith.client").setLevel(logging.CRITICAL)
# logging.getLogger("python_multipart.multipart").setLevel(logging.CRITICAL)
# logging.getLogger("grpc._cython.cygrpc").setLevel(logging.CRITICAL)


# class PrettyFormatter(logging.Formatter):
#     def format(self, record):
#         # Title (LEVEL + LOGGER NAME)
#         title = f"[{record.name}:{record.levelname}]  {record.getMessage().splitlines()[0]}"

#         # Body (remaining message below)
#         body_lines = record.getMessage().splitlines()[1:]
#         body = "\n".join(body_lines) if body_lines else ""

#         now = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

#         top_bar = f"─" * 40 + f" {now} " + "─" * 40
#         divider = "------------------------------------------------------------"

#         if body:
#             # Title + Body
#             formatted = f"{top_bar}\n{title}\n{divider}\n{body}"
#         else:
#             # Title only
#             formatted = f"{top_bar}\n{title}"

#         return formatted



# # def get_logger(name: str = "MyApp"):
# #     return logging.getLogger(name)

# def get_logger(name="MyApp"):
#     handler = RichHandler(rich_tracebacks=True, markup=True)
#     handler.setFormatter(PrettyFormatter())

#     logger = logging.getLogger(name)
#     logger.setLevel(logging.DEBUG)
#     logger.addHandler(handler)
#     logger.propagate = False
#     return logger



import logging
from rich.logging import RichHandler
from datetime import datetime

# Silence noisy libraries BEFORE logger creation
logging.getLogger("pymongo").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)
logging.getLogger("asyncio").setLevel(logging.CRITICAL)
logging.getLogger("langsmith.client").setLevel(logging.CRITICAL)
logging.getLogger("python_multipart.multipart").setLevel(logging.CRITICAL)
logging.getLogger("grpc._cython.cygrpc").setLevel(logging.CRITICAL)


class PrettyFormatter(logging.Formatter):
    def format(self, record):
        msg_lines = record.getMessage().splitlines()

        # Title = first line
        title = f"[{record.name}:{record.levelname}]  {msg_lines[0]}"

        # Body = remaining lines
        body = "\n".join(msg_lines[1:]) if len(msg_lines) > 1 else ""

        now = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

        top_bar = f"─" * 40 + f" {now} " + "─" * 40
        divider = "------------------------------------------------------------"

        if body:
            return f"{top_bar}\n{title}\n{divider}\n{body}"
        else:
            return f"{top_bar}\n{title}"





# def get_logger(name="MyApp"):
#     handler = RichHandler(rich_tracebacks=True, markup=True)
#     handler.setFormatter(PrettyFormatter())

#     logger = logging.getLogger(name)
#     logger.setLevel(logging.DEBUG)

#     # prevent multiple handlers if get_logger is called twice
#     if not logger.handlers:
#         logger.addHandler(handler)

#     logger.propagate = False
#     return logger


# # # Example
# # logger = get_logger("Test")
# # logger.info("SERVER STARTED\nServer running at port 8000")
# # logger.error("DATABASE ERROR\nCould not connect to PostgreSQL")



def get_logger(name="MyApp"):
    handler = RichHandler(
        rich_tracebacks=True,
        markup=True,
        show_time=False,
        show_level=False,
        show_path=False
    )
    handler.setFormatter(PrettyFormatter())

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        logger.addHandler(handler)

    logger.propagate = False
    return logger
