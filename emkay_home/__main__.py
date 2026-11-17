"""emkay-home: the page, and hivemind-core next to it.

    python -m emkay_home            # both
    python -m emkay_home --no-hivemind
"""
import argparse
import asyncio
import logging

from . import app, hive, house, settings


async def main(run_hivemind=True):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s emkay-home %(levelname)s %(message)s")
    house.seed_ovos_profile()
    hive.write_server_config()
    app.make_app().listen(settings.LISTEN_PORT, settings.LISTEN_HOST)
    logging.getLogger("emkay-home").info("the page is on %s:%s", settings.LISTEN_HOST, settings.LISTEN_PORT)
    if run_hivemind:
        await hive.keep_running()
    await asyncio.Event().wait()


def run():
    p = argparse.ArgumentParser(prog="emkay-home")
    p.add_argument("--no-hivemind", action="store_true", help="only the page")
    a = p.parse_args()
    asyncio.run(main(not a.no_hivemind))


if __name__ == "__main__":
    run()
