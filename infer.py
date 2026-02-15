#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(PROJECT_DIR, "qwen25-05b-jvc-merged")


os.environ.setdefault("HF_HOME", "/tmp/hf-cache")
os.makedirs(os.environ["HF_HOME"], exist_ok=True)
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"

FALLBACK_EXACT = "No lo sé basándome en mi entrenamiento."

_TOKENIZER = None
_MODEL = None

SYSTEM_NORMAL = (
    "Eres un asistente técnico y educativo en español. Responde de forma clara, precisa y profesional."
)

SYSTEM_STRICT = (
    "Eres un asistente técnico y educativo en español.\n"
    "Reglas estrictas:\n"
    "- No inventes datos.\n"
    f"- Si no tienes información suficiente, responde EXACTAMENTE: {FALLBACK_EXACT}\n"
    "- Responde en un solo párrafo.\n"
)

def _ensure_loaded():
    global _TOKENIZER, _MODEL
    if _TOKENIZER is not None and _MODEL is not None:
        return _TOKENIZER, _MODEL

    _TOKENIZER = AutoTokenizer.from_pretrained(MODEL_PATH, local_files_only=True, use_fast=True)
    if _TOKENIZER.pad_token is None:
        _TOKENIZER.pad_token = _TOKENIZER.eos_token

    use_cuda = torch.cuda.is_available()
    _MODEL = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH,
        local_files_only=True,
        device_map="auto" if use_cuda else None,
        torch_dtype=torch.float16 if use_cuda else torch.float32
    )
    if not use_cuda:
        _MODEL.to("cpu")
    _MODEL.eval()

    return _TOKENIZER, _MODEL

def _clean(text: str, strict: bool) -> str:
    t = (text or "").strip()
    if not t:
        return FALLBACK_EXACT if strict else ""

    if strict and FALLBACK_EXACT in t:
        return FALLBACK_EXACT

    
    for line in t.splitlines():
        line = line.strip()
        if line:
            return FALLBACK_EXACT if (strict and line == "") else line

    return FALLBACK_EXACT if strict else t

def infer(message: str, history=None, strict: bool = False, max_new_tokens: int = 256) -> str:
    tokenizer, model = _ensure_loaded()

    sys_prompt = SYSTEM_STRICT if strict else SYSTEM_NORMAL

    conv = [{"role": "system", "content": sys_prompt}]

   
    if history:
        for m in history[-8:]:
            role = m.get("role")
            content = (m.get("content") or "").strip()
            if role in ("user", "assistant") and content:
                conv.append({"role": role, "content": content})

    conv.append({"role": "user", "content": message})

    chat_text = tokenizer.apply_chat_template(conv, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(chat_text, return_tensors="pt")
    inputs = {k: v.to(model.device) for k, v in inputs.items()}
    input_len = inputs["input_ids"].shape[-1]

    gen_kwargs = dict(
        max_new_tokens=96 if strict else max_new_tokens,
        eos_token_id=tokenizer.eos_token_id,
        pad_token_id=tokenizer.eos_token_id,
        repetition_penalty=1.05,
    )

    if strict:
        gen_kwargs.update(do_sample=False, num_beams=1)
    else:
        gen_kwargs.update(do_sample=True, temperature=0.6, top_p=0.9, top_k=50)

    with torch.no_grad():
        out = model.generate(**inputs, **gen_kwargs)

    gen_ids = out[0, input_len:]
    raw = tokenizer.decode(gen_ids, skip_special_tokens=True)
    return _clean(raw, strict=strict)

def load_model():
    _ensure_loaded()

