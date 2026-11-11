"""Entry point: python3 server.py  ->  http://127.0.0.1:8000/rpc"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    import logging

    from lambda_rpc import config
    from lambda_rpc.transport import create_app

    logging.basicConfig(level=logging.INFO)
    app = create_app()
    app.run(host=config.HOST, port=config.PORT, threaded=True, debug=False)


if __name__ == "__main__":
    main()
