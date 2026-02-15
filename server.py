#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import difflib
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder="web", static_url_path="")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KB_PATH = os.path.join(BASE_DIR, "kb.jsonl")
KB_EXTRA_PATH = os.path.join(BASE_DIR, "kb_extra.jsonl")

KB = []
KB_INDEX = {}

FALLBACK = "No lo sé basándome en mi entrenamiento."

def load_kb():
    """Carga kb.jsonl + kb_extra.jsonl (si existe)."""
    global KB, KB_INDEX
    KB, KB_INDEX = [], {}

    def load_file(path):
        if not os.path.isfile(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    q = (obj.get("question") or "").strip()
                    a = (obj.get("answer") or "").strip()
                    if q and a:
                        KB.append({"q": q, "a": a})
                        KB_INDEX[q.lower()] = a
                except Exception:
                    pass

    load_file(KB_PATH)
    load_file(KB_EXTRA_PATH)

    return True

def kb_answer(question: str):
    q = (question or "").strip()
    if not q:
        return None

    # exact
    a = KB_INDEX.get(q.lower())
    if a:
        return a

    # fuzzy
    questions = [it["q"] for it in KB]
    if not questions:
        return None

    best = difflib.get_close_matches(q, questions, n=1, cutoff=0.78)
    if best:
        best_q = best[0]
        for it in KB:
            if it["q"] == best_q:
                return it["a"]
    return None

def append_kb_extra(question: str, answer: str):
    obj = {"question": question.strip(), "answer": answer.strip()}
    if not obj["question"] or not obj["answer"]:
        raise ValueError("question/answer vacíos")


    with open(KB_EXTRA_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

_warmed = False

@app.before_request
def warmup_once():
    global _warmed
    if _warmed:
        return
    load_kb()
    _warmed = True

@app.get("/")
def index():
    return send_from_directory("web", "index.html")

@app.get("/api/health")
def health():
    return jsonify({
        "ok": True,
        "kb_loaded": bool(KB),
        "kb_items": len(KB),
        "kb_extra_exists": os.path.isfile(KB_EXTRA_PATH),
    })

@app.post("/api/chat")
def api_chat():
    data = request.get_json(force=True, silent=True) or {}
    message = (data.get("message") or "").strip()
    strict = bool(data.get("strict", False))

    if not message:
        return jsonify({"ok": False, "error": "Empty message"}), 400

    a = kb_answer(message)
    if a:
        return jsonify({"ok": True, "answer": a, "source": "kb"})


    if strict:
        return jsonify({"ok": True, "answer": FALLBACK, "source": "fallback"})

    return jsonify({"ok": True, "answer": FALLBACK, "source": "fallback"})

@app.post("/api/kb/add")
def api_kb_add():
    data = request.get_json(force=True, silent=True) or {}
    q = (data.get("question") or "").strip()
    a = (data.get("answer") or "").strip()

    if not q or not a:
        return jsonify({"ok": False, "error": "question/answer requeridos"}), 400

    try:
        append_kb_extra(q, a)

        load_kb()
        return jsonify({
            "ok": True,
            "saved_to": "kb_extra.jsonl",
            "kb_items": len(KB),
            "ts": datetime.now().isoformat(timespec="seconds")
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))
    app.run(host=host, port=port, debug=False, threaded=True)

