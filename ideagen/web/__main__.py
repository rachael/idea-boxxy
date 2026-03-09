"""Run the web UI: python -m ideagen.web"""

import argparse
from .app import create_app


def main():
    parser = argparse.ArgumentParser(description="Idea Boxxy — Web UI")
    parser.add_argument("--db", default="data/ideagen.db", help="Database path")
    parser.add_argument("--port", type=int, default=5000, help="Port to run on")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    args = parser.parse_args()

    app = create_app(db_path=args.db)
    print(f"Idea Boxxy web UI running at http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=True)


main()
