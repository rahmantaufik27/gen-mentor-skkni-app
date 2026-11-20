"""
Technical evaluation harness for the subtopic-based learning material
generator (services/materials_service.py), built for an IEEE conference
paper's technical-evaluation section (coverage/grounding, format/language
compliance, and performance - see the session this was built in for the
fuller discussion of what's in/out of scope for a 5-page paper).

Read-only against the app's data (never writes to Neo4j/Postgres); it DOES
call the configured LLM provider for real, once per sampled subtopic, so a
full run is slow (observed ~60-140s per subtopic on local CPU-only Ollama -
see services/llm/ollama_provider.py's own notes on throughput) and a `--full`
run across every unit/subtopic can take well over an hour. Start with the
small default sample to sanity-check the harness itself before committing to
a full run; consider running in the background for `--full`.

Dependency NOT in requirements.txt (this script only, not the running app):
    pip install langdetect

Usage:
    cd backend && python scripts/eval_technical.py                     # quick sample (2 units x 2 subtopics)
    cd backend && python scripts/eval_technical.py --subtopics-per-unit 4
    cd backend && python scripts/eval_technical.py --full              # every unit, every subtopic
    cd backend && python scripts/eval_technical.py --units J.620100.010.01 --subtopics-per-unit 3

Outputs (next to this script):
    eval_results.csv   one row per generated subtopic, every metric below
    eval_summary.json  aggregate stats, ready to drop into a LaTeX table
"""

import argparse
import csv
import json
import os
import re
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.materials_service import MaterialsService  # noqa: E402

try:
    from langdetect import detect, DetectorFactory
    DetectorFactory.seed = 0  # deterministic output across runs
except ImportError:
    print("langdetect not installed - run: pip install langdetect", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Metric 1: language compliance (the PRIMARY_TASK prompt requires 100%
# Bahasa Indonesia - see materials_service.py's LANGUAGE instruction block).
# ---------------------------------------------------------------------------

_CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)


def _strip_code(text: str) -> str:
    """Remove fenced code blocks before language detection - code syntax
    (keywords like `function`, `return`, `class`) otherwise biases
    langdetect toward English even when every surrounding sentence is
    Bahasa Indonesia, which the prompt explicitly allows (code keeps its
    own language, prose around it must be Indonesian)."""
    return _CODE_FENCE.sub(" ", text)


def is_indonesian(material_text: str) -> bool:
    prose = _strip_code(material_text).strip()
    if not prose:
        return False
    try:
        return detect(prose) == "id"
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Metric 2: heading format compliance (FORMATTING RULE: every section
# heading must be markdown **bold** on its own line).
# ---------------------------------------------------------------------------

_BOLD_HEADING = re.compile(r"^\*\*(.+?)\*\*\s*$", re.MULTILINE)


def count_bold_headings(material_text: str) -> int:
    return len(_BOLD_HEADING.findall(material_text))


# ---------------------------------------------------------------------------
# Metric 3: prompt-scaffolding leak (HEADING RULE: the model must never
# echo "KELOMPOK N", "referensi-N", "Ke-N", etc. - see materials_service.py
# for the cascade-trap-style debugging history behind this specific check).
# ---------------------------------------------------------------------------

_LEAK_PATTERNS = [
    re.compile(r"\bKELOMPOK\s*\d+\b", re.IGNORECASE),
    re.compile(r"\breferensi-\d+\b", re.IGNORECASE),
    re.compile(r"\bKe-\d+\b"),
    re.compile(r"\bBagian\s*\d+\b", re.IGNORECASE),
    re.compile(r"\bGrup\s*\d+\b", re.IGNORECASE),
]


def find_leaks(material_text: str) -> list:
    found = []
    for pattern in _LEAK_PATTERNS:
        found.extend(pattern.findall(material_text))
    return found


# ---------------------------------------------------------------------------
# Metric 4: reference utilization (coverage) - a lexical-overlap PROXY for
# RAGAS-style "context recall", cheap enough to run at scale without a
# second LLM call as judge. Caveat worth stating in the paper's limitations:
# this is surface-form term overlap, not semantic entailment, so it likely
# UNDER-counts coverage when the model legitimately paraphrases a reference
# concept using different vocabulary.
# ---------------------------------------------------------------------------

_STOPWORDS_ID_EN = {
    "yang", "dan", "adalah", "untuk", "dengan", "dalam", "pada", "ini", "itu",
    "dapat", "akan", "dari", "atau", "juga", "tidak", "satu", "dua", "serta",
    "sebuah", "seperti", "sebagai", "oleh", "karena", "jika", "maka", "lebih",
    "dibuat", "berupa", "digunakan", "menggunakan", "bisa", "harus", "antara",
    "the", "and", "for", "with", "that", "this", "from", "are", "was", "were",
    "have", "has", "their", "which", "into", "such", "than", "then", "there",
}


def _significant_terms(text: str, min_len: int = 5) -> set:
    words = re.findall(r"[A-Za-z]{%d,}" % min_len, text.lower())
    return {w for w in words if w not in _STOPWORDS_ID_EN}


def reference_utilization(reference_group: list, material_text: str) -> float:
    """Fraction of the reference group's distinct significant terms that
    also appear (case-insensitive substring) in the generated material."""
    ref_text = " ".join(reference_group)
    ref_terms = _significant_terms(ref_text)
    if not ref_terms:
        return 0.0
    material_lower = material_text.lower()
    hit = sum(1 for term in ref_terms if term in material_lower)
    return hit / len(ref_terms)


# ---------------------------------------------------------------------------
# Supplementary depth metrics (not a compliance check, just useful context
# for the ablation table - e.g. comparing strategy (c) per-subtopic depth
# against the old single-call strategies' per-topic depth).
# ---------------------------------------------------------------------------

def word_count(material_text: str) -> int:
    return len(_strip_code(material_text).split())


def code_block_count(material_text: str) -> int:
    return len(_CODE_FENCE.findall(material_text))


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

def run_eval(units: list, subtopics_per_unit: int, row_writer=None) -> list:
    """row_writer, if given, is called with each row dict as soon as it's
    computed (and flushed to disk) - a full run is 1.5-2+ hours, so results
    need to survive a crash/kill partway through, not just get written once
    at the very end."""
    service = MaterialsService()
    rows = []

    for unit_code, competency_name in units:
        print(f"\n=== Unit {unit_code} - {competency_name} ===")
        try:
            groups = service._groups_for_unit(unit_code)
        except Exception as e:
            print(f"  [skip] could not fetch reference groups: {e}")
            continue

        t0 = time.time()
        try:
            sub_result = service.list_subtopics(unit_code, competency_name)
        except Exception as e:
            print(f"  [skip] list_subtopics failed: {e}")
            continue
        list_time = time.time() - t0
        subtopics = sub_result.get("subtopics", [])
        print(f"  {len(subtopics)} subtopics listed in {list_time:.1f}s")

        sample = subtopics[:subtopics_per_unit] if subtopics_per_unit else subtopics
        for sub in sample:
            idx, title = sub["index"], sub["title"]
            print(f"  -> generating subtopic {idx + 1}/{len(subtopics)}: {title}")
            t0 = time.time()
            try:
                result = service.generate_subtopic_material(unit_code, competency_name, idx, title)
            except Exception as e:
                print(f"     [FAILED] {e}")
                fail_row = {
                    "unit_code": unit_code, "subtopic_index": idx, "subtopic_title": title,
                    "success": False, "error": str(e),
                }
                rows.append(fail_row)
                if row_writer:
                    row_writer(fail_row)
                continue
            gen_time = time.time() - t0
            material = result.get("material", "")

            row = {
                "unit_code": unit_code,
                "subtopic_index": idx,
                "subtopic_title": title,
                "success": True,
                "generation_time_s": round(gen_time, 1),
                "is_indonesian": is_indonesian(material),
                "bold_heading_count": count_bold_headings(material),
                "has_scaffolding_leak": bool(find_leaks(material)),
                "leaked_tokens": ";".join(find_leaks(material)),
                "reference_utilization": round(reference_utilization(groups[idx], material), 3),
                "word_count": word_count(material),
                "code_block_count": code_block_count(material),
            }
            rows.append(row)
            if row_writer:
                row_writer(row)
            print(
                f"     {gen_time:.1f}s | id={row['is_indonesian']} | "
                f"headings={row['bold_heading_count']} | leak={row['has_scaffolding_leak']} | "
                f"coverage={row['reference_utilization']:.0%} | words={row['word_count']}"
            )

    return rows


def summarize(rows: list) -> dict:
    ok = [r for r in rows if r.get("success")]
    n = len(ok)
    if n == 0:
        return {"n": 0, "note": "no successful generations to summarize"}

    def pct(key):
        return round(100 * sum(1 for r in ok if r[key]) / n, 1)

    def avg(key):
        return round(statistics.mean(r[key] for r in ok), 3)

    return {
        "n_total": len(rows),
        "n_success": n,
        "n_failed": len(rows) - n,
        "pct_indonesian": pct("is_indonesian"),
        "pct_scaffolding_leak_free": round(100 - pct("has_scaffolding_leak"), 1),
        "mean_bold_headings_per_material": avg("bold_heading_count"),
        "mean_reference_utilization": avg("reference_utilization"),
        "median_reference_utilization": round(statistics.median(r["reference_utilization"] for r in ok), 3),
        "mean_generation_time_s": avg("generation_time_s"),
        "median_generation_time_s": round(statistics.median(r["generation_time_s"] for r in ok), 1),
        "mean_word_count": avg("word_count"),
        "mean_code_blocks_per_material": avg("code_block_count"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--subtopics-per-unit", type=int, default=2,
                         help="How many subtopics to sample per unit (0 = all). Default: 2 (quick sanity run).")
    parser.add_argument("--full", action="store_true",
                         help="Shortcut for --subtopics-per-unit 0 (every subtopic of every unit). Slow.")
    parser.add_argument("--units", nargs="*", default=None,
                         help="Restrict to these unit_codes (default: every unit in the graph).")
    args = parser.parse_args()

    subtopics_per_unit = 0 if args.full else args.subtopics_per_unit

    service = MaterialsService()
    all_units = service.get_all_units()
    if args.units:
        wanted = set(args.units)
        all_units = [u for u in all_units if u.get("unit_code") in wanted]
    units = [(u["unit_code"], u["title"]) for u in all_units if u.get("unit_code") and u.get("title")]

    print(f"Evaluating {len(units)} unit(s), up to "
          f"{'all' if subtopics_per_unit == 0 else subtopics_per_unit} subtopic(s) each.")
    print("This calls the real LLM provider once per subtopic - expect ~60-140s each.\n")

    out_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(out_dir, "eval_results.csv")
    json_path = os.path.join(out_dir, "eval_summary.json")
    fieldnames = [
        "unit_code", "subtopic_index", "subtopic_title", "success",
        "generation_time_s", "is_indonesian", "bold_heading_count",
        "has_scaffolding_leak", "leaked_tokens", "reference_utilization",
        "word_count", "code_block_count", "error",
    ]

    # Opened up front and written to (with an explicit flush) after EVERY
    # row, not just once at the end - a full run takes 1.5-2+ hours, so a
    # crash/kill partway through must not lose everything computed so far.
    csv_file = open(csv_path, "w", newline="", encoding="utf-8")
    csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames, extrasaction="ignore")
    csv_writer.writeheader()
    csv_file.flush()

    def write_row(row):
        csv_writer.writerow(row)
        csv_file.flush()
        os.fsync(csv_file.fileno())

    try:
        rows = run_eval(units, subtopics_per_unit, row_writer=write_row)
    finally:
        csv_file.close()

    summary = summarize(rows)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print(f"\nPer-item results -> {csv_path}")
    print(f"Summary stats     -> {json_path}")


if __name__ == "__main__":
    main()
