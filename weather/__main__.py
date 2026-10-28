import logging
import sys

from weather import db
from weather.job import run_fetch

logging.basicConfig(level=logging.INFO)

match sys.argv[1:]:
    case ["init-db"]:
        with db.connect() as conn:
            db.init_schema(conn)
    case ["fetch"]:
        for place, result in run_fetch().items():
            print(f"{place}: {result}")
    case _:
        sys.exit("usage: python -m weather init-db|fetch")
