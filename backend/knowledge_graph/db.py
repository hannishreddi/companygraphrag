"""Neo4j connection (lazy, so the API starts without graph credentials)."""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

_driver = None

# Neo4j reports deprecations of the fulltext procedure on every call; they are noise in the logs.
logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)


class GraphNotConfigured(RuntimeError):
    """Neo4j credentials are missing; callers that treat the graph as optional skip quietly."""


def get_driver():
    global _driver
    if _driver is None:
        from neo4j import GraphDatabase

        uri, user, password = (os.getenv(k) for k in ("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD"))
        if not all([uri, user, password]):
            raise GraphNotConfigured("Missing NEO4J_URI, NEO4J_USER or NEO4J_PASSWORD. Set them in backend/.env.")
        # Aura closes idle connections after a few minutes: recycle them before that and probe stale ones.
        driver = GraphDatabase.driver(uri, auth=(user, password), max_connection_lifetime=170,
                                      liveness_check_timeout=30, keep_alive=True, connection_timeout=20)
        try:
            driver.verify_connectivity()
        except Exception:
            driver.close()
            raise
        _driver = driver
    return _driver


def _with_reconnect(call):
    """Run `call`; if the connection died (Aura idle timeout, network blip), reconnect once and run it again."""
    from neo4j.exceptions import ServiceUnavailable, SessionExpired

    try:
        return call()
    except (ServiceUnavailable, SessionExpired):
        close_driver()
        return call()


def run(query: str, **params) -> list[dict]:
    """Run one Cypher statement in its own auto-commit transaction and return the rows."""
    def call():
        with get_driver().session() as session:
            return session.run(query, params).data()

    return _with_reconnect(call)


def run_read(query: str, params: dict | None = None, limit: int = 50, timeout: float = 15) -> list[dict]:
    """Run a query in a READ transaction (the server rejects writes) with a time and row limit."""
    import itertools

    from neo4j import unit_of_work

    @unit_of_work(timeout=timeout)  # transaction timeout; Query(timeout=...) only works with session.run
    def work(tx):
        result = tx.run(query, params or {})
        return [record.data() for record in itertools.islice(result, limit)]

    def call():
        with get_driver().session() as session:
            return session.execute_read(work)

    return _with_reconnect(call)


def close_driver():
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None
