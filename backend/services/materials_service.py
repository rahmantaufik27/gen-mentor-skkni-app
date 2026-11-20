"""
Service for reading materials and recommending them by mastery gap.

Materials now live in the Neo4j knowledge graph (see services/neo4j_service.py
and scripts/seed_neo4j.py) instead of data/materials.json - Neo4j is the
runtime source for both "All Materials" and "Recommended for You". The
recommendation engine itself (Neo4jService.get_recommended_materials) is
injected/swappable: this service's public contract (get_all_materials,
get_recommended_materials) is unchanged, so neither the API layer nor the
frontend needed to change to pick this up.

get_recommended_materials() narrows Neo4j's Test-Remedial fetch down to
MasteryService.get_effective_remedial_units() - Remedial per the latest
Test AND not yet demonstrated Mastered in Practice since that Test - so
materials for a unit the learner has since mastered in Practice stop being
recommended without needing any change to the Neo4j query/sync itself.
"""

import json
import re
import uuid
from typing import Dict, List, Optional

from config.database import execute_query
from services.mastery_service import MasteryService
from services.llm import get_llm_provider
from services.neo4j_service import Neo4jService, get_neo4j_service


def _truncate_unit_code(unit_code: Optional[str]) -> str:
    """Reduce a full unit code (e.g. 'J.620100.010.01') to its 3-segment main
    code, matching the convention used by Postgres/MasteryService."""
    parts = (unit_code or "").split(".")
    return ".".join(parts[:3]) if len(parts) >= 3 else (unit_code or "")


# Every unit's full set of DEDUPLICATED reference text measured in the graph
# today is 9.6k-24.4k chars (~2.4k-6.1k tokens) - comfortably inside a single
# LLM call with huge headroom, so there's no real need to split generation
# into per-topic sections/multiple calls. This budget just guards against a
# future unit whose reference corpus grows far past that.
_REFERENCE_CHAR_BUDGET = 30_000


def _select_references(examples: List[str]) -> List[str]:
    """Pick which (already-deduplicated) reference texts to include in the
    prompt. Under budget: include everything verbatim, untouched - the
    normal case for every unit today.

    Over budget (not yet observed, just future-proofing): the old logic did
    a plain greedy fill - append full texts in order until the character
    budget ran out - which let one long early reference (or, before
    dedup existed, several duplicate copies of it) burn the ENTIRE budget
    and starve every other topic out of the prompt completely. This does
    one fair "water-filling" pass instead: split the budget evenly across
    every reference, then hand the leftover from references shorter than
    their even share to the ones that need truncating - so the model still
    sees a sample from every topic, not just the first one or two."""
    total_len = sum(len(e) for e in examples)
    if total_len <= _REFERENCE_CHAR_BUDGET:
        return examples

    share = _REFERENCE_CHAR_BUDGET // len(examples)
    short = [e for e in examples if len(e) <= share]
    long = [e for e in examples if len(e) > share]
    leftover = sum(share - len(e) for e in short)
    long_share = share + (leftover // len(long)) if long else share

    return [e if len(e) <= share else e[:long_share] for e in examples]


# References come back ordered by lm.urutan - the graph's own intended
# lesson sequence - so a plain positional chunk (no embeddings/semantic
# clustering needed) already groups related material reasonably well.
_REFERENCE_GROUP_SIZE = 8


def _extract_material_body(content: str) -> str:
    """Strip the "TOPIC: ...\\n---\\nMATERIAL:" scaffolding the prompt asks
    for, returning just the lesson body. The TOPIC line is intentionally
    discarded here, not displayed - it's a free-text field the model writes
    itself, and letting it stand in as the displayed title let the model's
    own paraphrase drift away from the unit's real, official competency
    name (e.g. generating "Pengembangan Web dengan Bahasa Pemrograman dan
    Sistem Komputer" for a unit actually titled "Menerapkan Perintah
    Eksekusi..."). generate_learning_material uses competency_name itself -
    already ground truth, already what was clicked - as the topic instead.
    Falls back to the raw content unchanged if the model didn't follow the
    "MATERIAL:" marker format."""
    marker = "MATERIAL:"
    idx = content.rfind(marker)
    body = content.strip() if idx == -1 else content[idx + len(marker):].strip()
    # Defensive cleanup: the model occasionally leaves a stray, unmatched
    # "**" on its own line right at the start (seemingly an abandoned
    # attempt to bold the TOPIC line that ends up on the wrong side of the
    # "MATERIAL:" split) - strip it so a lone "**" never renders as a
    # visible artifact before the first real heading.
    first_line, _, rest = body.partition("\n")
    if first_line.strip("*").strip() == "":
        body = rest.lstrip()
    return body


def _parse_numbered_list(content: str, expected: int) -> List[str]:
    """Parse a "1. foo\\n2. bar\\n..." numbered list response into a plain
    list of title strings. Tolerant of minor formatting drift: a stray
    blank line is skipped, "1)" works the same as "1.", and a line with no
    leading number is treated as a continuation of the previous title
    (small models sometimes wrap a long title onto two lines) rather than
    dropped. Always returns exactly `expected` items - padded with a
    generic fallback title if the model returned fewer, truncated if it
    returned more - so a caller never has to handle a list/subtopic-group
    length mismatch."""
    import re

    titles: List[str] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        pattern = r"^\d+[.)]\s*(.+)$"
        match = re.match(pattern, line)
        if match:
            titles.append(match.group(1).strip())
        elif titles:
            titles[-1] = f"{titles[-1]} {line}".strip()

    while len(titles) < expected:
        titles.append(f"Subtopik {len(titles) + 1}")
    return titles[:expected]


def _group_references(references: List[str]) -> List[List[str]]:
    """Split the selected reference texts into fixed-size groups, in order.
    Handing the model one undifferentiated blob of 60+ short reference
    snippets lets it quietly cover only the few it finds most interesting
    and never mention the rest - having the input itself already broken
    into labeled "KELOMPOK N" groups (see generate_learning_material, which
    renders and references them in the prompt) gives the prompt something
    concrete to point at and ask the model to address, group by group,
    instead of trusting it to notice everything unprompted."""
    return [
        references[i:i + _REFERENCE_GROUP_SIZE]
        for i in range(0, len(references), _REFERENCE_GROUP_SIZE)
    ]


class MaterialsService:
    """Reads materials from Neo4j and cross-references them with unit mastery."""

    def __init__(self, mastery_service: Optional[MasteryService] = None, neo4j_service: Optional[Neo4jService] = None):
        # MasteryService (Postgres, the source of truth) is used to
        # determine "has this user mastered everything" and to narrow
        # recommendations to units still effectively Remedial (Test AND
        # Practice combined) - the actual material list/ranking still
        # comes from Neo4j.
        self.mastery_service = mastery_service or MasteryService()
        self.neo4j_service = neo4j_service or get_neo4j_service()

    def get_all_materials(self) -> List[Dict]:
        """Return every material in the Neo4j knowledge graph, unfiltered."""
        return self.neo4j_service.get_all_materials()

    def get_all_units(self) -> List[Dict]:
        """Every unit's code + human-readable title (static, not
        user-specific) - e.g. for the Discussion page's unit picker."""
        return self.neo4j_service.get_all_units()

    def _groups_for_unit(self, unit_code: str) -> List[List[str]]:
        """Fetch + dedupe + budget-select + group a unit's reference
        material - shared by generate_learning_material, list_subtopics,
        and generate_subtopic_material so all three always see the exact
        same subtopic split for a given unit (group N means the same thing
        everywhere, since this is a deterministic function of unit_code -
        no server-side caching of the split needed between a "list
        subtopics" call and a later "generate subtopic N" call)."""
        examples = self.neo4j_service.get_existing_learning_materials(unit_code)
        if not examples:
            raise ValueError(f"No reference learning materials found for unit {unit_code}.")
        return _group_references(_select_references(examples))

    # --- Shared generation cache ---------------------------------------
    # Generated content is NOT personalized per learner (same unit_code +
    # subtopic_index always yields the same prompt), so it's cached ONCE
    # and shared across every user instead of per-user - this keeps
    # storage bounded by (units x subtopics), not by (users x units), and
    # means the LLM only ever runs once per subtopic, no matter how many
    # learners later open it. The "Generate" button's flow stays the
    # same from the user's point of view: click it, get material - it's
    # just that a cache hit returns instantly instead of re-running the
    # ~2 minute local-LLM call.

    def _get_cached_subtopics(self, unit_code: str) -> Optional[List[Dict]]:
        rows = execute_query(
            "SELECT subtopics FROM generated_subtopic_lists WHERE unit_code = %s",
            (unit_code,),
            fetch=True,
        )
        if not rows:
            return None
        subtopics = rows[0][0]
        return subtopics if isinstance(subtopics, list) else json.loads(subtopics)

    def _cache_subtopics(self, unit_code: str, subtopics: List[Dict], provider: str) -> None:
        execute_query(
            """
            INSERT INTO generated_subtopic_lists (id, unit_code, subtopics, provider)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (unit_code) DO NOTHING
            """,
            (str(uuid.uuid4()), unit_code, json.dumps(subtopics), provider),
        )

    def _get_cached_subtopic_material(self, unit_code: str, subtopic_index: int) -> Optional[Dict]:
        rows = execute_query(
            """
            SELECT subtopic_title, material, provider
            FROM generated_subtopic_materials
            WHERE unit_code = %s AND subtopic_index = %s
            """,
            (unit_code, subtopic_index),
            fetch=True,
        )
        if not rows:
            return None
        subtopic_title, material, provider = rows[0]
        return {"topic": subtopic_title, "material": material, "provider": provider}

    def _cache_subtopic_material(
        self, unit_code: str, subtopic_index: int, subtopic_title: str, material: str, provider: str
    ) -> None:
        execute_query(
            """
            INSERT INTO generated_subtopic_materials
                (id, unit_code, subtopic_index, subtopic_title, material, provider)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (unit_code, subtopic_index) DO NOTHING
            """,
            (str(uuid.uuid4()), unit_code, subtopic_index, subtopic_title, material, provider),
        )

    def generate_learning_material(self, unit_code: str, competency_name: str) -> Dict:
        """Generate learning material centered on a competency, using references as support."""
        unit_code = (unit_code or "").strip()
        competency_name = (competency_name or "").strip()
        if not unit_code:
            raise ValueError("Unit code is required.")
        if not competency_name:
            raise ValueError("Competency name is required.")

        groups = self._groups_for_unit(unit_code)
        # Wrapped as <referensi-N>...</referensi-N> markup, NOT "KELOMPOK N:"
        # headings - the earlier heading-shaped label ("KELOMPOK 1:" on its
        # own line) kept getting echoed back verbatim as a section title
        # no matter how strongly the prompt forbade it (tested against
        # qwen3:4b-instruct specifically - small local models pattern-match
        # on prominent heading-shaped structure in the input more reliably
        # than they follow a negative instruction buried in prose). Markup
        # tags don't look like a heading to copy, so the model has nothing
        # heading-shaped to latch onto in the first place.
        reference_text = "\n\n".join(
            f"<referensi-{i + 1}>\n" + "\n---\n".join(group) + f"\n</referensi-{i + 1}>"
            for i, group in enumerate(groups)
        )
        num_groups = len(groups)

        prompt = f"""You are a curriculum writer.
            LANGUAGE: Bahasa Indonesia ONLY. Every word of your response - the
            topic, every heading, every sentence, every case study - must be
            written in Bahasa Indonesia. Do not write in English at any point,
            even for section labels. Code examples/snippets may keep their
            programming-language syntax, but all surrounding explanation stays
            in Bahasa Indonesia.

            UNIT CODE: {unit_code}
            CORE COMPETENCY: {competency_name}

            PRIMARY TASK:
            Write detailed learning material in Bahasa Indonesia that directly teaches and develops the CORE COMPETENCY above. Keep every explanation, example, and learning objective centered on this competency.
            Give a a section name or heading for each new topic, and use bullet points where appropriate. Avoid generic or unrelated content.
            you may add code example if explaining programming concepts, but keep it concise and relevant to the competency.

            SUPPORTING REFERENCES:
            The references below are wrapped in {num_groups} <referensi-N> tags purely so YOU can track which ones you've covered while writing - this markup is structural bookkeeping, not content, and must never appear in your output in any form (no "<referensi-1>", no "referensi 1", no echoing a tag name as a heading or anywhere else). COVERAGE IS MANDATORY: your material must include content addressing what's inside every single <referensi-N> tag - do not skip any of them, and do not let any one go completely unaddressed.

            HEADING RULE (strict): every section heading must be a real, descriptive Bahasa Indonesia title that says what the section actually teaches - never a bare placeholder. None of these are ever allowed as a heading, in any language or format: "Referensi 1", "Kelompok 1", "Ke-1", "Ke-2", "Bagian 1", "Bagian 2", "Grup 1", "Section 1", or any other ordinal/number standing alone as a title. Correct examples: "Menggunakan JavaScript untuk Validasi Form", "Python untuk Backend dan Pengolahan Data", "Perbedaan Compiler, Assembler, dan Interpreter". One <referensi-N> tag is not required to become its own section - merge several into one section, or split one across sections, whatever reads best - but by the end, every tag's content must be addressed somewhere under a heading that describes its real topic.

            FORMATTING RULE (strict): every section heading MUST be written in markdown bold, on its own line, like this exact pattern: **Judul Section Di Sini**. Never write a heading as plain unformatted text - a reader scanning the material must be able to see every section break at a glance. Within each section, write substantial, detailed paragraphs (not one-liners) and use bullet points (`-`) for lists of steps/items. Add a short, runnable code snippet for any section that explains a programming concept.

            Use these references only as supplemental context, examples, or enriching details that stay centered on the CORE COMPETENCY above - do not let them replace, narrow, or redirect the material away from it.
            {reference_text}

            Include practical examples and relevant Junior Web Developer case studies where appropriate. Avoid repeating reference text verbatim.

            Output format (write it all in Bahasa Indonesia - "TOPIC"/"MATERIAL" are the only English words allowed, as literal labels):
            TOPIC: <topik yang berpusat pada kompetensi, dalam Bahasa Indonesia>
            ---
            MATERIAL:
            <materi baru, seluruhnya dalam Bahasa Indonesia, mencakup isi semua {num_groups} referensi, dengan judul section dalam format **bold** (bukan angka atau label), paragraf yang detail, dan contoh kode di tiap section yang relevan>

            Reminder: respond entirely in Bahasa Indonesia, bold every section heading with **asterisks**, and make sure every one of the {num_groups} reference groups is addressed somewhere in the material."""
        print("unit_code:", unit_code)
        print("competency name:", competency_name)
        print()

        provider = get_llm_provider()
        content = provider.chat([{"role": "user", "content": prompt}])
        return {
            "topic": competency_name,
            "material": _extract_material_body(content),
            "provider": provider.name,
        }

    def list_subtopics(self, unit_code: str, competency_name: str) -> Dict:
        """Return one short title per reference group, for a "pick a
        subtopic, then generate just that one" UI - the user explicitly
        wants subtopic generation to be USER-TRIGGERED per subtopic, not a
        single automatic multi-call loop (which would queue up behind
        itself on our single local Ollama instance and take longer in
        total than one combined call, not less). This call is deliberately
        cheap: titles only, not full material, so listing subtopics stays
        fast regardless of how long any one subtopic's full generation
        later takes.

        Returns {"subtopics": [{"index": int, "title": str}, ...]} -
        `index` is what generate_subtopic_material expects back, since the
        underlying grouping (_groups_for_unit) is a deterministic function
        of unit_code and needs no server-side session/cache between this
        call and a later per-subtopic generate call."""
        unit_code = (unit_code or "").strip()
        competency_name = (competency_name or "").strip()
        if not unit_code:
            raise ValueError("Unit code is required.")
        if not competency_name:
            raise ValueError("Competency name is required.")

        cached = self._get_cached_subtopics(unit_code)
        if cached is not None:
            return {"subtopics": cached, "provider": "cache"}

        groups = self._groups_for_unit(unit_code)
        reference_text = "\n\n".join(
            f"<referensi-{i + 1}>\n" + "\n---\n".join(group) + f"\n</referensi-{i + 1}>"
            for i, group in enumerate(groups)
        )

        prompt = f"""You are a curriculum writer planning a lesson outline.
            LANGUAGE: Bahasa Indonesia ONLY - every title must be written in Bahasa Indonesia.

            UNIT CODE: {unit_code}
            CORE COMPETENCY: {competency_name}

            Below are {len(groups)} groups of reference material (wrapped in <referensi-N> tags), each about a different subtopic. For EACH group, write exactly ONE short, descriptive subtopic title in Bahasa Indonesia (roughly 4-10 words) that says specifically what that group is about. Never use a placeholder like "Referensi 1", "Kelompok 1", or a bare number as a title.

            {reference_text}

            Output format: exactly {len(groups)} lines, nothing else - no intro, no explanation, no blank lines between them - numbered 1 to {len(groups)}, one subtopic title per line:
            1. <judul subtopik 1>
            2. <judul subtopik 2>
            ..."""

        provider = get_llm_provider()
        content = provider.chat([{"role": "user", "content": prompt}])
        titles = _parse_numbered_list(content, expected=len(groups))
        subtopics = [{"index": i, "title": title} for i, title in enumerate(titles)]
        self._cache_subtopics(unit_code, subtopics, provider.name)
        return {"subtopics": subtopics, "provider": provider.name}

    def generate_subtopic_material(
        self, unit_code: str, competency_name: str, subtopic_index: int, subtopic_title: str = ""
    ) -> Dict:
        """Generate full, detailed material for ONE subtopic (one reference
        group) only - called when the user clicks that specific subtopic's
        own button in list_subtopics' results, never automatically for
        every subtopic in a loop. Scoping one call to one subtopic (instead
        of asking one call to cover all of them, as
        generate_learning_material does) lets this subtopic use its whole
        output budget on real depth."""
        unit_code = (unit_code or "").strip()
        competency_name = (competency_name or "").strip()
        if not unit_code:
            raise ValueError("Unit code is required.")
        if not competency_name:
            raise ValueError("Competency name is required.")

        cached = self._get_cached_subtopic_material(unit_code, subtopic_index)
        if cached is not None:
            if subtopic_title and not cached.get("topic"):
                cached["topic"] = subtopic_title
            cached["provider"] = "cache"
            return cached

        groups = self._groups_for_unit(unit_code)
        if not isinstance(subtopic_index, int) or not (0 <= subtopic_index < len(groups)):
            raise ValueError(
                f"Invalid subtopic index {subtopic_index!r} (unit {unit_code} has {len(groups)} subtopics, indices 0-{len(groups) - 1})."
            )

        subtopic_title = (subtopic_title or "").strip() or f"Subtopik {subtopic_index + 1}"
        reference_text = "\n\n---\n\n".join(groups[subtopic_index])

        prompt = f"""You are a curriculum writer.
            LANGUAGE: Bahasa Indonesia ONLY. Every word of your response - every
            heading, every sentence, every case study - must be written in
            Bahasa Indonesia. Code examples/snippets may keep their
            programming-language syntax, but all surrounding explanation stays
            in Bahasa Indonesia.

            UNIT CODE: {unit_code}
            CORE COMPETENCY: {competency_name}
            SUBTOPIC TO TEACH NOW: {subtopic_title}

            PRIMARY TASK:
            Write DETAILED learning material in Bahasa Indonesia that teaches this SUBTOPIC in real depth, as one part of the broader CORE COMPETENCY above. This is a focused, standalone deep-dive on just this one subtopic - go further and more thoroughly than a general overview would, since this subtopic has the full output to itself.

            FORMATTING RULE (strict): every section heading MUST be written in markdown bold, on its own line, like this exact pattern: **Judul Section Di Sini** - never a placeholder, number, or bare label. Within each section, write substantial, detailed paragraphs (not one-liners) and use bullet points (`-`) for lists of steps/items. Add a short, runnable code snippet for any part that explains a programming concept.

            SUPPORTING REFERENCE MATERIAL FOR THIS SUBTOPIC:
            Use the material below as supplemental context, examples, or enriching detail - stay centered on the SUBTOPIC and CORE COMPETENCY above, don't let it narrow or redirect the material away from them.
            {reference_text}

            Include practical examples and relevant Junior Web Developer case studies. Avoid repeating reference text verbatim.

            Output format (write it all in Bahasa Indonesia - "MATERIAL" is the only English word allowed, as a literal label):
            MATERIAL:
            <materi baru tentang subtopik ini, seluruhnya dalam Bahasa Indonesia, detail, dengan judul section dalam format **bold** dan contoh kode yang relevan>"""

        provider = get_llm_provider()
        content = provider.chat([{"role": "user", "content": prompt}])
        material = _extract_material_body(content)
        self._cache_subtopic_material(unit_code, subtopic_index, subtopic_title, material, provider.name)
        return {
            "topic": subtopic_title,
            "material": material,
            "provider": provider.name,
        }

    def get_recommended_materials(self, user_id: str) -> Dict:
        """
        Materials for units that are currently effectively Remedial - per
        the latest Test AND not yet demonstrated Mastered in Practice
        since that Test (see MasteryService.get_effective_remedial_units) -
        prioritized by Neo4jService (lowest knowledge level first).

        Returns:
            {"materials": [...], "all_mastered": bool}
        """
        summary = self.mastery_service.get_user_mastery_summary(user_id)
        has_attempts = bool(summary.get("success") and summary.get("has_attempts"))
        effective_remedial = set(summary.get("effective_remedial_units", []))

        recommended = self.neo4j_service.get_recommended_materials(user_id)
        recommended = [
            m for m in recommended if _truncate_unit_code(m.get("unit_code")) in effective_remedial
        ]

        # "All mastered" only once the learner has actually taken a Test -
        # a brand-new user has no effective_remedial_units either, but
        # hasn't earned this message yet (see get_user_mastery_summary).
        all_mastered = has_attempts and not effective_remedial

        return {
            "materials": recommended,
            "all_mastered": all_mastered,
        }
