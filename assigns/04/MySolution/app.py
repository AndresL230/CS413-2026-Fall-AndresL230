"""Start the LAMBDA workbench on the loopback interface.

    python app.py [--port 8413] [--timeout 5]
"""
import argparse

from lambda_workbench.backend import DEFAULT_TIMEOUT_SECONDS, LambdaBackend
from lambda_workbench.controller import WorkbenchController
from lambda_workbench.examples import load_canned_examples
from lambda_workbench.model import Workbench
from lambda_workbench.web import create_app

HOST = "127.0.0.1"
DEFAULT_PORT = 8413


def main() -> None:
    parser = argparse.ArgumentParser(description="LAMBDA workbench (local, single user)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS,
                        help="seconds allowed for one Lint or Interpret run")
    args = parser.parse_args()

    controller = WorkbenchController(
        Workbench(), LambdaBackend(timeout_seconds=args.timeout), load_canned_examples())
    app = create_app(controller)
    print(f"LAMBDA workbench: http://{HOST}:{args.port}/")
    # Threaded so the page can still be served while an operation is running.
    app.run(host=HOST, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
