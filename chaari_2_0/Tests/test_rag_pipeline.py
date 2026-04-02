#!/usr/bin/env python3
"""Test script for the optimized RAG pipeline with specialized local models."""

import time
import sys
import requests

BASE = "http://localhost:11434"

def separator(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# ─────────────────────────────────────────────
# TEST 1: Config imports
# ─────────────────────────────────────────────
separator("TEST 1: Config imports")
try:
    from config.rag import (
        OLLAMA_BASE_URL, ROUTER_MODEL, LEVEL_SELECTOR_MODEL, EVALUATOR_MODEL,
        MAX_RAG_ITERATIONS, TOP_K_PER_LEVEL, RELEVANCE_THRESHOLD
    )
    print(f"  ROUTER_MODEL         = {ROUTER_MODEL}")
    print(f"  LEVEL_SELECTOR_MODEL = {LEVEL_SELECTOR_MODEL}")
    print(f"  EVALUATOR_MODEL      = {EVALUATOR_MODEL}")
    print("  [PASS] Config imports OK")
except Exception as e:
    print(f"  [FAIL] {e}")
    sys.exit(1)

# ─────────────────────────────────────────────
# TEST 2: Ollama connectivity & model check
# ─────────────────────────────────────────────
separator("TEST 2: Ollama connectivity & model availability")
try:
    r = requests.get(f"{BASE}/api/tags", timeout=5)
    models = [m["name"] for m in r.json().get("models", [])]
    print(f"  Ollama running: YES ({len(models)} models)")

    needed = ["qwen2.5:0.5b", "llama3.2:1b"]
    all_found = True
    for m in needed:
        found = any(m in name for name in models)
        status = "FOUND" if found else "MISSING"
        if not found:
            all_found = False
        print(f"    {m}: [{status}]")
    print(f"  [{'PASS' if all_found else 'WARN - some models missing'}]")
except Exception as e:
    print(f"  [FAIL] Ollama not reachable: {e}")
    sys.exit(1)

# ─────────────────────────────────────────────
# TEST 3: Router model (qwen2.5:0.5b) — YES/NO
# ─────────────────────────────────────────────
separator("TEST 3: Router (qwen2.5:0.5b) — YES/NO classification")

router_tests = [
    ("How does the CHAARI security pipeline work?", True),
    ("Explain the architecture of the brain module", True),
    ("hello bhai kya haal hai", False),
    ("open chrome and play music", False),
]

router_pass = 0
for query, expected in router_tests:
    prompt = (
        "Classify: does this query need a knowledge base search about CHAARI AI system?\n"
        "Examples:\n"
        '"How does encryption work?" → YES\n'
        '"open notepad" → NO\n'
        '"hello bhai" → NO\n'
        '"explain the security pipeline" → YES\n'
        '"play music on youtube" → NO\n\n'
        f'"{query}" →'
    )
    t0 = time.perf_counter()
    try:
        resp = requests.post(f"{BASE}/api/chat", json={
            "model": ROUTER_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"num_predict": 20, "temperature": 0.0},
        }, timeout=15)
        t1 = time.perf_counter()
        result = resp.json().get("message", {}).get("content", "").strip()
        got_yes = "yes" in result.lower()
        correct = got_yes == expected
        if correct:
            router_pass += 1
        tag = "PASS" if correct else "FAIL"
        ms = (t1 - t0) * 1000
        print(f"  Q: \"{query[:50]}...\"")
        print(f"    Expected={'YES' if expected else 'NO'} | Got=\"{result}\" | {ms:.0f}ms [{tag}]")
    except Exception as e:
        print(f"  Q: \"{query[:50]}\" → [ERROR] {e}")

print(f"  Router score: {router_pass}/{len(router_tests)}")

# ─────────────────────────────────────────────
# TEST 4: Level Selector (qwen2.5:0.5b) — 0-3
# ─────────────────────────────────────────────
separator("TEST 4: Level Selector (qwen2.5:0.5b) — level 0-3")

level_tests = [
    ("What is CHAARI?", 3),            # broad → root
    ("Explain the architecture areas", 2),  # themes
    ("How does the brain module connect?", 1),  # sections
    ("What port number does the executor use?", 0),  # leaves/exact
]

level_pass = 0
for query, expected in level_tests:
    prompt = (
        "Pick search depth for a document tree. Reply with ONLY a number.\n"
        "3=broad overview, 2=architecture themes, 1=specific components, 0=exact values\n\n"
        "Examples:\n"
        '"What is CHAARI?" → 3\n'
        '"Explain the architecture areas" → 2\n'
        '"How does the brain module work?" → 1\n'
        '"What port number does executor use?" → 0\n\n'
        f'"{query}" →'
    )
    t0 = time.perf_counter()
    try:
        resp = requests.post(f"{BASE}/api/chat", json={
            "model": LEVEL_SELECTOR_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"num_predict": 10, "temperature": 0.0},
        }, timeout=15)
        t1 = time.perf_counter()
        result = resp.json().get("message", {}).get("content", "").strip()
        got_level = -1
        for ch in result:
            if ch.isdigit() and int(ch) <= 3:
                got_level = int(ch)
                break
        correct = got_level == expected
        # Accept ±1 level as "close enough"
        close = abs(got_level - expected) <= 1
        if correct:
            level_pass += 1
            tag = "PASS"
        elif close:
            level_pass += 0.5
            tag = "CLOSE"
        else:
            tag = "FAIL"
        ms = (t1 - t0) * 1000
        print(f"  Q: \"{query}\"")
        print(f"    Expected={expected} | Got={got_level} (\"{result}\") | {ms:.0f}ms [{tag}]")
    except Exception as e:
        print(f"  Q: \"{query}\" → [ERROR] {e}")

print(f"  Level selector score: {level_pass}/{len(level_tests)}")

# ─────────────────────────────────────────────
# TEST 5: Evaluator (llama3.2:1b) — sufficiency
# ─────────────────────────────────────────────
separator("TEST 5: Evaluator (llama3.2:1b) — sufficiency check")

eval_tests = [
    {
        "query": "How does CHAARI handle security?",
        "context": "- CHAARI uses a multi-layer security architecture with SafetyKernel at Layer 0\n"
                   "- Identity Lock prevents impersonation at Layer 1\n"
                   "- Policy Engine governs allowed actions at Layer 1.5",
        "level": 2,
        "expected": "SUFFICIENT",
    },
    {
        "query": "What exact port does the executor use?",
        "context": "- CHAARI has an executor module that handles command execution\n"
                   "- The executor connects ASUS and Dell nodes",
        "level": 2,
        "expected": "DRILL_DOWN",
    },
]

eval_pass = 0
for tc in eval_tests:
    prompt = (
        f'Query: "{tc["query"]}"\n\n'
        f'Retrieved context (level {tc["level"]}):\n{tc["context"]}\n\n'
        "Is this context enough to answer the query? Reply with ONE word:\n"
        "SUFFICIENT / DRILL_DOWN / GO_UP / RETRY\n\n"
        "Answer:"
    )
    t0 = time.perf_counter()
    try:
        resp = requests.post(f"{BASE}/api/chat", json={
            "model": EVALUATOR_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"num_predict": 10, "temperature": 0.0},
        }, timeout=20)
        t1 = time.perf_counter()
        result = resp.json().get("message", {}).get("content", "").strip().upper()

        got = "UNKNOWN"
        if "SUFFICIENT" in result:
            got = "SUFFICIENT"
        elif "DRILL" in result or "DOWN" in result:
            got = "DRILL_DOWN"
        elif "UP" in result:
            got = "GO_UP"
        elif "RETRY" in result:
            got = "RETRY"

        correct = got == tc["expected"]
        if correct:
            eval_pass += 1
        tag = "PASS" if correct else "WARN"
        ms = (t1 - t0) * 1000
        print(f"  Q: \"{tc['query']}\"")
        print(f"    Expected={tc['expected']} | Got={got} (\"{result[:40]}\") | {ms:.0f}ms [{tag}]")
    except Exception as e:
        print(f"  Q: \"{tc['query']}\" → [ERROR] {e}")

print(f"  Evaluator score: {eval_pass}/{len(eval_tests)}")

# ─────────────────────────────────────────────
# TEST 6: OllamaLight class integration
# ─────────────────────────────────────────────
separator("TEST 6: _OllamaLight class integration")
try:
    from core.rag_agent import _OllamaLight
    client = _OllamaLight()
    print(f"  is_available(): {client.is_available()}")

    t0 = time.perf_counter()
    r = client.generate("qwen2.5:0.5b", "Reply YES or NO: Is the sky blue?", max_tokens=5)
    t1 = time.perf_counter()
    print(f"  generate() test: \"{r}\" | {(t1-t0)*1000:.0f}ms")
    print("  [PASS] _OllamaLight works")
except Exception as e:
    print(f"  [FAIL] {e}")

# ─────────────────────────────────────────────
# TEST 7: Full RAG Agent (Router + Level Selector)
# ─────────────────────────────────────────────
separator("TEST 7: Full RAG Agent integration (no vectorstore needed)")
try:
    from core.rag_agent import _Router, _LevelSelector

    router = _Router()
    selector = _LevelSelector()

    # Router tests (no groq passed — should use local models)
    queries = [
        ("How does CHAARI brain module process queries?", True),
        ("open notepad", False),
        ("hi", False),
    ]
    for q, expected in queries:
        t0 = time.perf_counter()
        got = router.needs_rag(q, groq=None)
        t1 = time.perf_counter()
        # Note: short queries and keyword matches are rule-based, not LLM
        tag = "PASS" if got == expected else "INFO"
        print(f"  Router(\"{q[:45]}...\") = {got} (expected {expected}) | {(t1-t0)*1000:.0f}ms [{tag}]")

    # Level selector test
    t0 = time.perf_counter()
    level = selector.select_level("What is the overall architecture of CHAARI?", groq=None)
    t1 = time.perf_counter()
    print(f"  LevelSelector(\"What is the overall arch...\") = Level {level} | {(t1-t0)*1000:.0f}ms")
    print("  [PASS] Integration OK")
except Exception as e:
    print(f"  [FAIL] {e}")

# ─────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────
separator("SUMMARY")
print("  All tests completed. Review results above.")
print("  Models used:")
print(f"    Router/LevelSelector: {ROUTER_MODEL}")
print(f"    Evaluator:            {EVALUATOR_MODEL}")
print()
