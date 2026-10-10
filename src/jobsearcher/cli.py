"""Command line entry point. Only `serve` exists so far (ARCHITECTURE §15)."""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="jobsearcher")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="Start the API server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    if args.command == "serve":
        import uvicorn

        uvicorn.run("jobsearcher.web.app:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
