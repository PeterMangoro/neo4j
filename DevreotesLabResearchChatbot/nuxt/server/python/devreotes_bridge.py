import json
import os
import sys
from pathlib import Path


def main() -> int:
    question = (sys.stdin.read() or "").strip()
    if not question:
        err = json.dumps({"error": "Empty question"})
        print(err, file=sys.stderr, flush=True)
        print(err, flush=True)
        return 1

    # Allow override via env, default to parent project folder.
    devreotes_root = Path(
        os.getenv("DEVREOTES_ROOT", str(Path(__file__).resolve().parents[3]))
    ).resolve()
    # Keep retrieval stable on machines with constrained GPU memory.
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
    os.chdir(devreotes_root)
    sys.path.insert(0, str(devreotes_root))
    backend_path = devreotes_root / "backend"
    sys.path.insert(0, str(backend_path))

    try:
        if os.getenv("DEVREOTES_STREAM", "").lower() in ("1", "true", "yes", "on"):
            from backend.app.chatbot import iter_answer_ndjson

            try:
                for line in iter_answer_ndjson(question):
                    sys.stdout.write(line)
                    sys.stdout.flush()
            except Exception as stream_exc:
                err = json.dumps({"error": str(stream_exc)})
                print(err, file=sys.stderr, flush=True)
                print(err, flush=True)
                return 2
            return 0

        from backend.app.chatbot import answer_question_with_metadata

        result = answer_question_with_metadata(question)
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except Exception as exc:  # pragma: no cover - runtime bridge safety
        err = json.dumps({"error": str(exc)})
        print(err, file=sys.stderr, flush=True)
        print(err, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
