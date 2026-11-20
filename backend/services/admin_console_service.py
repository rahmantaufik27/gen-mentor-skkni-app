"""
Data and actions behind the admin console (frontend/pages/admin_dashboard.py).

Read-mostly: every `*_view` method returns a plain dict for one admin page,
built from Postgres (accounts, attempts, activity) and Neo4j (units,
questions, materials). The few write actions are account-level ones
(emails, deleting accounts, removing a discussion post, clearing saved
lessons). Curriculum content (questions, materials, units) is shown but
not edited here - it lives in the knowledge graph.

Unit codes: Postgres stores the 3-segment code ("J.620100.010"); the graph
and the UI use the full one ("J.620100.010.01"). `_full` maps between them.
"""

import csv
import io
import json
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from config.database import execute_query
from config.mail import mail_enabled, send_email
from services import account_email_service
from services.mastery_service import MasteryService
from services.neo4j_service import get_neo4j_service

TEST_EMAIL_DOMAIN = "example.com"
QUIET_AFTER_DAYS = 14
BLOOM = ["C1", "C2", "C3", "C4", "C5", "C6"]
_GRAPH_DB = "fix-knowledge-question-base"

STAGE_REGISTERED = "Registered only"
STAGE_PRE = "Pre-Test done"
STAGE_PRACTICE = "Practising"
STAGE_POST = "Post-Test taken"
STAGE_PASSED = "Post-Test passed"
STAGES = [STAGE_REGISTERED, STAGE_PRE, STAGE_PRACTICE, STAGE_POST, STAGE_PASSED]


def _rank(level) -> int:
    try:
        return BLOOM.index(str(level).upper()) + 1
    except ValueError:
        return 0


def _iso(value) -> Optional[str]:
    return value.isoformat() if value else None


def _short(code: str) -> str:
    parts = (code or "").split(".")
    return ".".join(parts[:3]) if len(parts) >= 3 else (code or "")


def _is_test(email: str) -> bool:
    return (email or "").lower().endswith("@" + TEST_EMAIL_DOMAIN)


class AdminConsoleService:
    def __init__(self, quiz_service=None, practice_service=None):
        self.quiz_service = quiz_service
        self.practice_service = practice_service
        self.neo4j = get_neo4j_service()
        self.targets: Dict[str, str] = dict(MasteryService().targets)  # short code -> target level
        self._units_cache = None

    # ------------------------------------------------------------------
    # shared building blocks
    # ------------------------------------------------------------------
    def units(self) -> List[dict]:
        """[{code (full), short, title, target}] in code order."""
        if self._units_cache is None:
            titles = {u["unit_code"]: u.get("title") or "" for u in self.neo4j.get_all_units()}
            by_short = {_short(code): code for code in titles}
            self._units_cache = [
                {"code": by_short.get(short, short), "short": short,
                 "title": titles.get(by_short.get(short, ""), ""), "target": target}
                for short, target in sorted(self.targets.items())
            ]
        return self._units_cache

    def _full(self, short: str) -> str:
        return next((u["code"] for u in self.units() if u["short"] == short), short)

    def _learners(self) -> List[dict]:
        """One dict per user with stage, latest levels and activity."""
        users = execute_query(
            """
            SELECT id, full_name, email, created_at, inference_method, email_verified,
                   target_role, target_level, onboarding_completed
            FROM users ORDER BY created_at DESC
            """, fetch=True) or []
        attempts = execute_query(
            """
            SELECT DISTINCT ON (user_id, test_stage) id, user_id, test_stage, completed_at, passed, score
            FROM quiz_attempts WHERE completed_at IS NOT NULL
            ORDER BY user_id, test_stage, completed_at DESC
            """, fetch=True) or []
        mastery = execute_query(
            "SELECT attempt_id, unit_code, unit_mastery_level, mastery_status FROM user_mastery_level", fetch=True) or []
        practice = execute_query(
            """
            SELECT pa.user_id, pa.completed_at, pu.unit_code, pu.unit_mastery_level
            FROM practice_attempts pa LEFT JOIN practice_attempt_units pu ON pu.practice_attempt_id = pa.id
            ORDER BY pa.completed_at
            """, fetch=True) or []
        sessions = execute_query(
            "SELECT user_id, COUNT(*), MAX(completed_at) FROM practice_attempts GROUP BY user_id", fetch=True) or []
        activity = execute_query(
            "SELECT user_id, MAX(occurred_at) FROM user_activity GROUP BY user_id", fetch=True) or []

        mastery_by_attempt = defaultdict(dict)
        for attempt_id, unit_code, level, status in mastery:
            mastery_by_attempt[str(attempt_id)][unit_code] = (level, status)
        tests = defaultdict(dict)
        for attempt_id, user_id, stage, completed_at, passed, score in attempts:
            tests[str(user_id)][stage or "pre"] = {
                "attempt_id": str(attempt_id), "completed_at": completed_at, "passed": bool(passed),
                "score": float(score or 0), "units": mastery_by_attempt.get(str(attempt_id), {}),
            }
        practice_levels = defaultdict(dict)   # user -> unit -> (level, when), latest wins
        for user_id, completed_at, unit_code, level in practice:
            if unit_code:
                practice_levels[str(user_id)][unit_code] = (level, completed_at)
        session_info = {str(u): (n, last) for u, n, last in sessions}
        last_activity = {str(u): when for u, when in activity}

        learners = []
        for (user_id, full_name, email, created_at, inference, verified, goal_role, goal_level, onboarded) in users:
            uid = str(user_id)
            user_tests = tests.get(uid, {})
            pre, post = user_tests.get("pre"), user_tests.get("post")
            latest_test = post or pre
            n_sessions, last_practice = session_info.get(uid, (0, None))
            levels, at_target = {}, 0
            for unit in self.units():
                short = unit["short"]
                test_level, test_status = (latest_test["units"].get(short, (None, None)) if latest_test else (None, None))
                level, met = test_level, test_status == "Mastered"
                prac = practice_levels.get(uid, {}).get(short)
                if prac and latest_test and prac[1] and prac[1] >= latest_test["completed_at"]:
                    level = prac[0] or level
                    met = met or _rank(prac[0]) >= _rank(unit["target"])
                levels[unit["code"]] = {"level": level, "met": bool(met)}
                at_target += 1 if met else 0
            if post and post["passed"]:
                stage = STAGE_PASSED
            elif post:
                stage = STAGE_POST
            elif pre and n_sessions:
                stage = STAGE_PRACTICE
            elif pre:
                stage = STAGE_PRE
            else:
                stage = STAGE_REGISTERED
            last_seen = max([d for d in (last_activity.get(uid), last_practice,
                                         latest_test["completed_at"] if latest_test else None, created_at) if d])
            learners.append({
                "id": uid, "full_name": full_name, "email": email, "created_at": _iso(created_at),
                "inference_method": inference, "email_verified": bool(verified), "is_test": _is_test(email),
                "goal": f"L{goal_level} {goal_role}" if goal_role else "Not chosen",
                "onboarding_completed": bool(onboarded), "stage": stage, "tested": bool(latest_test),
                "units_at_target": at_target if latest_test else None, "levels": levels if latest_test else {},
                "practice_sessions": n_sessions, "last_practice": _iso(last_practice),
                "last_active": _iso(last_seen), "days_since_active": (datetime.now() - last_seen).days,
                "pre": user_tests.get("pre"), "post": user_tests.get("post"),
            })
        return learners

    @staticmethod
    def _public(learner: dict) -> dict:
        return {k: v for k, v in learner.items() if k not in ("pre", "post")}

    # ------------------------------------------------------------------
    # pages
    # ------------------------------------------------------------------
    def overview_view(self) -> dict:
        learners = self._learners()
        real = [l for l in learners if not l["is_test"]]
        tested = [l for l in real if l["tested"]]
        below = Counter()
        for l in tested:
            for code, info in l["levels"].items():
                if not info["met"]:
                    below[code] += 1
        quiet = [l for l in tested if l["days_since_active"] >= QUIET_AFTER_DAYS and l["stage"] != STAGE_PASSED]
        unanswered = execute_query(
            """
            SELECT COUNT(*) FROM unit_discussion_posts p WHERE p.parent_post_id IS NULL
            AND NOT EXISTS (SELECT 1 FROM unit_discussion_posts r WHERE r.parent_post_id = p.id)
            """, fetch=True)[0][0]
        return {
            "total_accounts": len(learners), "real_learners": len(real), "test_accounts": len(learners) - len(real),
            "tested": len(tested), "practising": sum(1 for l in real if l["practice_sessions"]),
            "passed": sum(1 for l in real if l["stage"] == STAGE_PASSED),
            "stage_counts": {stage: sum(1 for l in real if l["stage"] == stage) for stage in STAGES},
            "units_below_target": [{"code": code, "learners": below.get(code, 0)} for code in (u["code"] for u in self.units())],
            "unverified": sum(1 for l in real if not l["email_verified"]),
            "quiet": len(quiet), "unanswered_posts": unanswered,
            "open_sessions": len(self.live_view()["sessions"]),
        }

    def users_view(self) -> dict:
        learners = self._learners()
        return {"users": [self._public(l) for l in learners], "stages": STAGES,
                "test_accounts": sum(1 for l in learners if l["is_test"]), "mail_enabled": mail_enabled()}

    def mastery_view(self, include_test: bool = False) -> dict:
        tested = [l for l in self._learners() if l["tested"] and (include_test or not l["is_test"])]
        distribution = []
        for unit in self.units():
            counts = [0] * 7  # index 0 = no level
            for l in tested:
                counts[_rank(l["levels"][unit["code"]]["level"])] += 1
            distribution.append({"code": unit["code"], "target": unit["target"], "counts": counts,
                                 "at_target": sum(1 for l in tested if l["levels"][unit["code"]]["met"])})
        return {"units": self.units(), "tested": len(tested), "distribution": distribution,
                "learners": [self._public(l) for l in tested]}

    def learner_detail_view(self, user_id: str) -> dict:
        learner = next((l for l in self._learners() if l["id"] == user_id), None)
        if not learner:
            raise ValueError("Learner not found")

        tests = []
        for stage in ("pre", "post"):
            attempt = learner[stage]
            if not attempt:
                continue
            total, correct = execute_query(
                "SELECT COUNT(*), COALESCE(SUM(CASE WHEN is_correct THEN 1 ELSE 0 END), 0) "
                "FROM quiz_attempt_details WHERE attempt_id = %s", (attempt["attempt_id"],), fetch=True)[0]
            tests.append({
                "stage": stage, "completed_at": _iso(attempt["completed_at"]), "passed": attempt["passed"],
                "score": attempt["score"], "total_questions": int(total), "correct_answers": int(correct),
                "units": {self._full(short): {"level": level, "status": status}
                          for short, (level, status) in attempt["units"].items()},
            })

        practice_rows = execute_query(
            """
            SELECT pa.id, pa.completed_at, pa.total_questions, pa.correct_answers, pa.total_score,
                   pa.max_possible_score, pu.unit_code, pu.unit_mastery_level
            FROM practice_attempts pa LEFT JOIN practice_attempt_units pu ON pu.practice_attempt_id = pa.id
            WHERE pa.user_id = %s ORDER BY pa.completed_at
            """, (user_id,), fetch=True) or []
        sessions, order = {}, []
        for pid, when, total, correct, score, max_score, unit_code, level in practice_rows:
            pid = str(pid)
            if pid not in sessions:
                order.append(pid)
                sessions[pid] = {"number": len(order), "completed_at": _iso(when), "total_questions": total,
                                 "correct_answers": correct, "total_score": float(score or 0),
                                 "max_possible_score": float(max_score or 0), "units": {}}
            if unit_code:
                sessions[pid]["units"][self._full(unit_code)] = level

        # Per unit: Pre-Test level -> each Practice level in order -> Post-Test level
        journey = []
        for unit in self.units():
            steps = []
            for test in tests:
                if test["stage"] == "pre" and unit["code"] in test["units"]:
                    steps.append({"label": "Pre-Test", "level": test["units"][unit["code"]]["level"]})
            for pid in order:
                if unit["code"] in sessions[pid]["units"]:
                    steps.append({"label": f"Practice #{sessions[pid]['number']}", "level": sessions[pid]["units"][unit["code"]]})
            for test in tests:
                if test["stage"] == "post" and unit["code"] in test["units"]:
                    steps.append({"label": "Post-Test", "level": test["units"][unit["code"]]["level"]})
            current = learner["levels"].get(unit["code"], {})
            journey.append({"code": unit["code"], "title": unit["title"], "target": unit["target"],
                            "level": current.get("level"), "met": current.get("met", False), "steps": steps})

        activity_counts = dict(execute_query(
            "SELECT activity_type, COUNT(*) FROM user_activity WHERE user_id = %s GROUP BY 1", (user_id,), fetch=True) or [])
        recent = execute_query(
            "SELECT activity_type, metadata, occurred_at FROM user_activity WHERE user_id = %s "
            "ORDER BY occurred_at DESC LIMIT 25", (user_id,), fetch=True) or []
        material_views = Counter()
        for row in execute_query(
                "SELECT metadata FROM user_activity WHERE user_id = %s AND activity_type = 'material_view'",
                (user_id,), fetch=True) or []:
            meta = row[0] if isinstance(row[0], dict) else json.loads(row[0] or "{}")
            material_views[meta.get("unit_code") or "Unknown"] += 1

        def count(table: str) -> int:
            return execute_query(f"SELECT COUNT(*) FROM {table} WHERE user_id = %s", (user_id,), fetch=True)[0][0]

        reflections = execute_query(
            "SELECT question_key, answer_text, answer_number, updated_at FROM user_reflections "
            "WHERE user_id::text = %s ORDER BY updated_at DESC", (user_id,), fetch=True) or []
        return {
            "learner": self._public(learner), "tests": tests,
            "practice_sessions": [sessions[pid] for pid in order], "journey": journey,
            "activity_counts": activity_counts,
            "recent_activity": [{"type": t, "detail": (m or {}).get("unit_code", "") if isinstance(m, dict) else "",
                                 "at": _iso(at)} for t, m, at in recent],
            "material_views": [{"unit": unit, "views": n} for unit, n in material_views.most_common()],
            "counts": {
                "notes": execute_query("SELECT COUNT(*) FROM user_notes WHERE user_id::text = %s", (user_id,), fetch=True)[0][0],
                "free_notes": count("user_free_notes"), "discussion_posts": count("unit_discussion_posts"),
                "reflections": len(reflections),
            },
            "reflections": [{"question": key, "answer": text if text else number, "updated_at": _iso(at)}
                            for key, text, number, at in reflections],
        }

    def engagement_view(self) -> dict:
        since = datetime.now() - timedelta(days=30)
        counts = dict(execute_query(
            "SELECT activity_type, COUNT(*) FROM user_activity WHERE occurred_at >= %s GROUP BY 1", (since,), fetch=True) or [])
        counts["practice_session"] = execute_query(
            "SELECT COUNT(*) FROM practice_attempts WHERE completed_at >= %s", (since,), fetch=True)[0][0]
        counts["note_saved"] = execute_query(
            "SELECT (SELECT COUNT(*) FROM user_notes WHERE created_at >= %s) + "
            "(SELECT COUNT(*) FROM user_free_notes WHERE created_at >= %s)", (since, since), fetch=True)[0][0]
        counts["reflection"] = execute_query(
            "SELECT COUNT(*) FROM user_reflections WHERE updated_at >= %s", (since,), fetch=True)[0][0]
        views = Counter()
        for (meta,) in execute_query(
                "SELECT metadata FROM user_activity WHERE activity_type = 'material_view' AND occurred_at >= %s",
                (since,), fetch=True) or []:
            meta = meta if isinstance(meta, dict) else json.loads(meta or "{}")
            views[meta.get("unit_code") or "Unknown"] += 1
        daily = execute_query(
            "SELECT occurred_at::date, COUNT(*) FROM user_activity WHERE occurred_at >= %s GROUP BY 1 ORDER BY 1",
            (since,), fetch=True) or []
        learners = self._learners()
        real = [l for l in learners if not l["is_test"]]
        quiet = [self._public(l) for l in real
                 if l["days_since_active"] >= QUIET_AFTER_DAYS and l["stage"] != STAGE_PASSED]
        return {
            "counts": counts, "views_by_unit": [{"unit": u, "views": n} for u, n in views.most_common()],
            "daily": [{"date": str(day), "events": n} for day, n in daily],
            "active_this_week": sum(1 for l in real if l["days_since_active"] < 7), "real_learners": len(real),
            "quiet": sorted(quiet, key=lambda l: -l["days_since_active"]), "quiet_after_days": QUIET_AFTER_DAYS,
            "mail_enabled": mail_enabled(),
        }

    def live_view(self) -> dict:
        names = {str(uid): (name, email) for uid, name, email in
                 execute_query("SELECT id, full_name, email FROM users", fetch=True) or []}
        sessions = []
        for kind, service in (("Test", self.quiz_service), ("Practice", self.practice_service)):
            for session_id, session in list(getattr(service, "sessions", {}).items()):
                name, email = names.get(str(session.get("user_id")), ("Unknown", ""))
                label = kind
                if kind == "Test":
                    label = "Post-Test" if session.get("test_stage") == "post" else "Pre-Test"
                started = session.get("started_at")
                sessions.append({
                    "session_id": session_id, "kind": kind, "exam": label, "learner": name, "email": email,
                    "answered": len(session.get("answers", [])), "total": len(session.get("questions", [])),
                    "started_at": started if isinstance(started, str) else _iso(started),
                })
        return {"sessions": sessions}

    def end_session(self, kind: str, session_id: str) -> str:
        service = self.quiz_service if kind == "Test" else self.practice_service
        if session_id not in getattr(service, "sessions", {}):
            raise ValueError("That session is no longer open")
        del service.sessions[session_id]
        return "Session ended. Its answers were discarded."

    def competency_map_view(self, unit_code: str = "") -> dict:
        units = self.units()
        unit_code = unit_code or (units[0]["code"] if units else "")
        rows = self.neo4j._run_query(
            """
            MATCH (cu:CompetencyUnit {kode: $kode})-[:HAS_ELEMENT]->(e:ElementCompetency)
            OPTIONAL MATCH (e)-[:HAS_PERFORMANCE_CRITERION]->(pc:PerformanceCriterion)
            OPTIONAL MATCH (pc)-[:ASSESSED_BY]->(q:EvaluationQuestion)
            RETURN e.text AS element, pc.text AS criterion, count(DISTINCT q) AS questions
            ORDER BY element, criterion
            """, {"kode": unit_code}, purpose="admin_competency_map", database=_GRAPH_DB)
        elements = defaultdict(list)
        for row in rows:
            if row.get("criterion"):
                elements[row["element"]].append({"criterion": row["criterion"], "questions": row["questions"]})
            else:
                elements[row["element"]]
        totals = self.neo4j._run_query(
            """
            MATCH (cu:CompetencyUnit)
            OPTIONAL MATCH (cu)-[:HAS_ELEMENT]->(e:ElementCompetency)
            OPTIONAL MATCH (e)-[:HAS_PERFORMANCE_CRITERION]->(pc:PerformanceCriterion)
            OPTIONAL MATCH (pc)-[:ASSESSED_BY]->(q:EvaluationQuestion)
            WITH cu, e, pc, count(DISTINCT q) AS n
            RETURN cu.kode AS code, count(DISTINCT e) AS elements, count(DISTINCT pc) AS criteria,
                   sum(CASE WHEN pc IS NOT NULL AND n = 0 THEN 1 ELSE 0 END) AS criteria_without_questions
            ORDER BY code
            """, purpose="admin_competency_totals", database=_GRAPH_DB)
        references = {code: len(self.neo4j.get_existing_learning_materials(code)) for code in (u["code"] for u in units)}
        return {
            "units": units, "unit_code": unit_code,
            "elements": [{"element": name, "criteria": items} for name, items in elements.items()],
            "totals": [{**row, "reference_snippets": references.get(row["code"], 0)} for row in totals],
        }

    def materials_view(self) -> dict:
        materials = self.neo4j.get_all_materials()
        listed = {code: len(subtopics if isinstance(subtopics, list) else json.loads(subtopics))
                  for code, subtopics in execute_query(
                      "SELECT unit_code, subtopics FROM generated_subtopic_lists", fetch=True) or []}
        lessons = execute_query(
            "SELECT unit_code, subtopic_index, subtopic_title, LENGTH(material), provider, created_at "
            "FROM generated_subtopic_materials ORDER BY unit_code, subtopic_index", fetch=True) or []
        views = Counter()
        for (meta,) in execute_query(
                "SELECT metadata FROM user_activity WHERE activity_type = 'material_view'", fetch=True) or []:
            meta = meta if isinstance(meta, dict) else json.loads(meta or "{}")
            views[meta.get("unit_code") or ""] += 1
        generated = Counter(code for code, *_ in lessons)
        return {
            "materials": [{"title": m.get("title"), "unit_code": m.get("unit_code"), "type": m.get("type"),
                           "url": m.get("url")} for m in materials],
            "units": [{"code": u["code"], "title": u["title"], "subtopics_listed": listed.get(u["code"]),
                       "lessons_generated": generated.get(u["code"], 0), "views": views.get(u["code"], 0)}
                      for u in self.units()],
            "lessons": [{"unit_code": code, "subtopic_index": idx, "title": title, "characters": length,
                         "provider": provider, "created_at": _iso(when)}
                        for code, idx, title, length, provider, when in lessons],
        }

    def lesson_text(self, unit_code: str, subtopic_index: int) -> dict:
        rows = execute_query(
            "SELECT subtopic_title, material FROM generated_subtopic_materials WHERE unit_code = %s AND subtopic_index = %s",
            (unit_code, subtopic_index), fetch=True)
        if not rows:
            raise ValueError("Lesson not found")
        return {"title": rows[0][0], "material": rows[0][1]}

    def delete_lessons(self, unit_code: str = "", subtopic_index: Optional[int] = None) -> str:
        if unit_code and subtopic_index is not None:
            execute_query("DELETE FROM generated_subtopic_materials WHERE unit_code = %s AND subtopic_index = %s",
                          (unit_code, subtopic_index))
            return "Lesson deleted. It will be generated again the next time a learner asks for it."
        if unit_code:
            execute_query("DELETE FROM generated_subtopic_materials WHERE unit_code = %s", (unit_code,))
            execute_query("DELETE FROM generated_subtopic_lists WHERE unit_code = %s", (unit_code,))
            return f"Saved lessons and subtopic list for {unit_code} cleared."
        execute_query("DELETE FROM generated_subtopic_materials")
        execute_query("DELETE FROM generated_subtopic_lists")
        return "All saved lessons and subtopic lists cleared."

    def questions_view(self, include_test: bool = False) -> dict:
        coverage_rows = self.neo4j._run_query(
            """
            MATCH (cu:CompetencyUnit)-[:HAS_ELEMENT]->(:ElementCompetency)
                  -[:HAS_PERFORMANCE_CRITERION]->(:PerformanceCriterion)-[:ASSESSED_BY]->(q:EvaluationQuestion)
            RETURN cu.kode AS code, q.bloom_level AS level, count(DISTINCT q) AS n
            """, purpose="admin_question_coverage", database=_GRAPH_DB)
        coverage = {u["code"]: {level: 0 for level in BLOOM} for u in self.units()}
        for row in coverage_rows:
            if row["code"] in coverage and row["level"] in coverage[row["code"]]:
                coverage[row["code"]][row["level"]] = row["n"]

        answers = execute_query(
            "SELECT d.question_id, d.unit_code, d.bloom_level, d.selected_answer, d.correct_answer, d.is_correct "
            "FROM quiz_attempt_details d JOIN quiz_attempts a ON a.id = d.attempt_id JOIN users u ON u.id = a.user_id "
            "WHERE %s OR u.email NOT LIKE %s", (include_test, "%@" + TEST_EMAIL_DOMAIN), fetch=True) or []
        stats = {}
        for qid, unit, level, selected, key, is_correct in answers:
            item = stats.setdefault(qid, {"question_id": qid, "unit_code": self._full(unit), "level": level,
                                          "key": key, "asked": 0, "correct": 0, "picks": Counter()})
            item["asked"] += 1
            item["correct"] += 1 if is_correct else 0
            if selected:
                item["picks"][selected] += 1
        # Every question in the current bank (the same list the Test serves),
        # with its answer statistics merged in. Answers recorded against
        # question ids from the older bank (before the move to Neo4j) can't be
        # matched to a question any more, so they are only counted.
        try:
            bank = self.quiz_service.question_loader.load_questions()
        except Exception:
            bank = []
        items = []
        for q in bank:
            item = stats.pop(q.id, None) or {"asked": 0, "correct": 0, "picks": Counter()}
            key = next((c.id for c in q.choices if c.is_correct), "")
            wrong = [(choice, n) for choice, n in item["picks"].most_common() if choice != key]
            top_wrong = wrong[0] if wrong else (None, 0)
            asked = item["asked"]
            items.append({
                "question_id": q.id, "text": q.question_text, "unit_code": q.unit, "level": q.bloom_level,
                "key": key, "choices": [{"id": c.id, "text": c.text, "is_correct": c.is_correct} for c in q.choices],
                "explanation": q.explanation or "", "asked": asked,
                "correct_pct": round(item["correct"] / asked * 100) if asked else None,
                "top_wrong": top_wrong[0], "top_wrong_pct": round(top_wrong[1] / asked * 100) if asked else None,
                "top_wrong_count": top_wrong[1], "unanswered": asked - sum(item["picks"].values()),
                "review": bool(top_wrong[0]) and top_wrong[1] > item["correct"] and asked >= 3,
            })
        items.sort(key=lambda i: (i["unit_code"], _rank(i["level"]), i["text"]))
        return {"units": self.units(), "levels": BLOOM, "coverage": coverage, "include_test": include_test,
                "total_questions": len(bank), "items": items,
                "old_bank_questions": len(stats), "old_bank_answers": sum(s["asked"] for s in stats.values())}

    def discussions_view(self) -> dict:
        rows = execute_query(
            """
            SELECT p.id, p.unit_code, p.body, p.created_at, p.material_title, u.full_name,
                   (SELECT COUNT(*) FROM unit_discussion_posts r WHERE r.parent_post_id = p.id) AS replies,
                   EXISTS (SELECT 1 FROM unit_discussion_posts r WHERE r.parent_post_id = p.id AND r.is_best_answer) AS solved
            FROM unit_discussion_posts p JOIN users u ON u.id = p.user_id
            WHERE p.parent_post_id IS NULL ORDER BY p.created_at DESC
            """, fetch=True) or []
        posts = [{"id": str(pid), "unit_code": unit, "body": body, "created_at": _iso(when), "material": material,
                  "author": author, "replies": replies, "solved": solved}
                 for pid, unit, body, when, material, author, replies, solved in rows]
        return {"posts": sorted(posts, key=lambda p: (p["replies"] > 0, p["created_at"] or ""), reverse=False)}

    def delete_post(self, post_id: str) -> str:
        execute_query("DELETE FROM unit_discussion_posts WHERE id = %s", (post_id,))
        return "Post removed, along with its replies."

    def gain_view(self, include_test: bool = False) -> dict:
        both = [l for l in self._learners() if l["pre"] and l["post"] and (include_test or not l["is_test"])]
        tested = sum(1 for l in self._learners() if l["tested"] and (include_test or not l["is_test"]))
        per_unit = []
        for unit in self.units():
            short = unit["short"]
            pre = [_rank(l["pre"]["units"].get(short, (None, None))[0]) for l in both]
            post = [_rank(l["post"]["units"].get(short, (None, None))[0]) for l in both]
            per_unit.append({
                "code": unit["code"], "target": unit["target"],
                "pre_avg": round(sum(pre) / len(pre), 2) if pre else None,
                "post_avg": round(sum(post) / len(post), 2) if post else None,
                "mastered_before": sum(1 for l in both if l["pre"]["units"].get(short, (None, None))[1] == "Mastered"),
                "mastered_after": sum(1 for l in both if l["post"]["units"].get(short, (None, None))[1] == "Mastered"),
            })
        learners = [{"full_name": l["full_name"], "email": l["email"], "pre_score": l["pre"]["score"],
                     "post_score": l["post"]["score"], "practice_sessions": l["practice_sessions"],
                     "passed": l["post"]["passed"]} for l in both]
        return {"both": len(both), "tested": tested, "per_unit": per_unit, "learners": learners,
                "pre_avg_score": round(sum(l["pre_score"] for l in learners) / len(learners), 1) if learners else None,
                "post_avg_score": round(sum(l["post_score"] for l in learners) / len(learners), 1) if learners else None}

    def health_view(self) -> dict:
        checks = []
        try:
            users = execute_query("SELECT COUNT(*) FROM users", fetch=True)[0][0]
            checks.append({"service": "PostgreSQL", "used_for": "Accounts, attempts, notes", "ok": True,
                           "detail": f"{users} accounts"})
        except Exception as e:
            checks.append({"service": "PostgreSQL", "used_for": "Accounts, attempts, notes", "ok": False, "detail": str(e)})
        try:
            n = self.neo4j._run_query("MATCH (q:EvaluationQuestion) RETURN count(q) AS n",
                                      purpose="admin_health", database=_GRAPH_DB)
            checks.append({"service": "Neo4j", "used_for": "Units, questions, materials", "ok": bool(n),
                           "detail": f"{n[0]['n']} questions in the graph" if n else "No answer from the graph"})
        except Exception as e:
            checks.append({"service": "Neo4j", "used_for": "Units, questions, materials", "ok": False, "detail": str(e)})
        try:
            from services.llm.ollama_provider import OllamaProvider
            provider = OllamaProvider()
            base = getattr(provider, "base_url", None) or getattr(provider, "host", "http://localhost:11434")
            with urllib.request.urlopen(f"{str(base).rstrip('/')}/api/tags", timeout=4) as response:
                models = [m.get("name") for m in json.loads(response.read()).get("models", [])]
            checks.append({"service": "Ollama (LLM)", "used_for": "Generated lessons, chatbot", "ok": True,
                           "detail": f"{len(models)} model(s) installed"})
        except Exception as e:
            checks.append({"service": "Ollama (LLM)", "used_for": "Generated lessons, chatbot", "ok": False,
                           "detail": f"Not reachable: {str(e)[:120]}"})
        checks.append({"service": "Email", "used_for": "Confirmation, reset, reminders", "ok": mail_enabled(),
                       "detail": "Switched on" if mail_enabled() else "Off - set the app password in mail.ini"})
        open_sessions = len(self.live_view()["sessions"])
        lessons, chars = execute_query(
            "SELECT COUNT(*), COALESCE(SUM(LENGTH(material)), 0) FROM generated_subtopic_materials", fetch=True)[0]
        return {"checks": checks, "open_sessions": open_sessions,
                "saved_lessons": lessons, "saved_lesson_characters": int(chars)}

    # ------------------------------------------------------------------
    # account actions
    # ------------------------------------------------------------------
    def send_reset_link(self, user_id: str) -> str:
        rows = execute_query("SELECT email FROM users WHERE id = %s", (user_id,), fetch=True)
        if not rows:
            raise ValueError("User not found")
        ok, message = account_email_service.request_password_reset(rows[0][0])
        if not ok:
            raise ValueError(message)
        return f"Password reset link sent to {rows[0][0]}."

    def resend_confirmation(self, user_id: str) -> str:
        rows = execute_query("SELECT email, email_verified FROM users WHERE id = %s", (user_id,), fetch=True)
        if not rows:
            raise ValueError("User not found")
        if rows[0][1]:
            return "That email is already confirmed."
        ok, message = account_email_service.resend_verification(rows[0][0])
        if not ok:
            raise ValueError(message)
        return f"Confirmation email sent to {rows[0][0]}."

    def send_reminders(self, user_ids: List[str]) -> str:
        if not mail_enabled():
            raise ValueError("Email is off. Set the app password in mail.ini to send reminders.")
        rows = execute_query("SELECT full_name, email FROM users WHERE id::text = ANY(%s)", (list(user_ids),), fetch=True) or []
        sent = 0
        for full_name, email in rows:
            send_email(
                email, "Your GAMASKILL practice is waiting",
                f"Hi {full_name},\n\nIt has been a while since your last GAMASKILL session. Your practice "
                "questions are still focused on the units below target, so a short session will pick up "
                f"where you left off:\n\n{account_email_service.app_url()}\n",
            )
            sent += 1
        return f"Reminder sent to {sent} learner(s)."

    def delete_users(self, user_ids: Optional[List[str]] = None, test_accounts: bool = False) -> str:
        """Delete accounts and everything recorded for them."""
        if test_accounts:
            rows = execute_query("SELECT id FROM users WHERE email LIKE %s", ("%@" + TEST_EMAIL_DOMAIN,), fetch=True) or []
            user_ids = [str(r[0]) for r in rows]
        user_ids = list(user_ids or [])
        if not user_ids:
            return "No accounts to delete."
        ids = (user_ids,)
        # Tables without ON DELETE CASCADE to users are cleared explicitly first.
        execute_query("DELETE FROM quiz_attempt_details WHERE attempt_id IN "
                      "(SELECT id FROM quiz_attempts WHERE user_id::text = ANY(%s))", ids)
        execute_query("DELETE FROM user_mastery_level WHERE user_id::text = ANY(%s)", ids)
        execute_query("DELETE FROM quiz_attempts WHERE user_id::text = ANY(%s)", ids)
        execute_query("DELETE FROM user_notes WHERE user_id::text = ANY(%s)", ids)
        execute_query("DELETE FROM user_reflections WHERE user_id::text = ANY(%s)", ids)
        execute_query("DELETE FROM users WHERE id::text = ANY(%s)", ids)
        try:
            self.neo4j._run_query("MATCH (u:User) WHERE u.id IN $ids DETACH DELETE u", {"ids": user_ids},
                                  purpose="admin_delete_users")
        except Exception:
            pass
        return f"Deleted {len(user_ids)} account(s) and their records."

    # ------------------------------------------------------------------
    # exports
    # ------------------------------------------------------------------
    EXPORTS = {
        "test_attempts": ("Test attempts", "learner and test",
                          "SELECT a.user_id, a.test_stage, a.score, a.passed, a.started_at, a.completed_at "
                          "FROM quiz_attempts a WHERE a.completed_at IS NOT NULL ORDER BY a.completed_at"),
        "test_answers": ("Test answers", "learner, test and question",
                         "SELECT a.user_id, a.test_stage, d.question_id, d.unit_code, d.bloom_level, "
                         "d.selected_answer, d.correct_answer, d.is_correct FROM quiz_attempt_details d "
                         "JOIN quiz_attempts a ON a.id = d.attempt_id ORDER BY a.completed_at, d.question_id"),
        "unit_mastery": ("Unit mastery", "learner, test and unit",
                         "SELECT m.user_id, a.test_stage, m.unit_code, m.unit_mastery_level, m.mastery_status, "
                         "m.unit_score FROM user_mastery_level m JOIN quiz_attempts a ON a.id = m.attempt_id "
                         "ORDER BY a.completed_at, m.unit_code"),
        "practice_sessions": ("Practice sessions", "learner, session and unit",
                              "SELECT p.user_id, p.completed_at, p.total_questions, p.correct_answers, p.total_score, "
                              "u.unit_code, u.unit_mastery_level FROM practice_attempts p "
                              "LEFT JOIN practice_attempt_units u ON u.practice_attempt_id = p.id ORDER BY p.completed_at"),
        "activity_log": ("Activity log", "event",
                         "SELECT user_id, activity_type, metadata::text, occurred_at FROM user_activity ORDER BY occurred_at"),
        "reflections": ("Reflections", "learner and reflection answer",
                        "SELECT user_id, question_key, answer_text, answer_number, updated_at FROM user_reflections "
                        "ORDER BY updated_at"),
    }
    _EXPORT_HEADERS = {
        "test_attempts": ["test_stage", "score", "passed", "started_at", "completed_at"],
        "test_answers": ["test_stage", "question_id", "unit_code", "bloom_level", "selected_answer", "correct_answer", "is_correct"],
        "unit_mastery": ["test_stage", "unit_code", "unit_mastery_level", "mastery_status", "unit_score"],
        "practice_sessions": ["completed_at", "total_questions", "correct_answers", "total_score", "unit_code", "unit_mastery_level"],
        "activity_log": ["activity_type", "metadata", "occurred_at"],
        "reflections": ["question_key", "answer_text", "answer_number", "updated_at"],
    }

    def exports_view(self) -> dict:
        datasets = []
        for key, (label, per, query) in self.EXPORTS.items():
            rows = execute_query(f"SELECT COUNT(*) FROM ({query.split(' ORDER BY ')[0]}) q", fetch=True)[0][0]
            datasets.append({"key": key, "label": label, "one_row_per": per, "rows": rows})
        return {"datasets": datasets}

    def export_csv(self, key: str, anonymize: bool = True, include_test: bool = False) -> str:
        if key not in self.EXPORTS:
            raise ValueError("Unknown dataset")
        users = {str(uid): (name, email) for uid, name, email in
                 execute_query("SELECT id, full_name, email FROM users ORDER BY created_at", fetch=True) or []}
        anon = {uid: f"L{i + 1:03d}" for i, uid in enumerate(users)}
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow((["learner_id"] if anonymize else ["full_name", "email"]) + self._EXPORT_HEADERS[key])
        for row in execute_query(self.EXPORTS[key][2], fetch=True) or []:
            uid = str(row[0])
            name, email = users.get(uid, ("", ""))
            if not include_test and _is_test(email):
                continue
            who = [anon.get(uid, "unknown")] if anonymize else [name, email]
            writer.writerow(who + [_iso(v) if isinstance(v, datetime) else v for v in row[1:]])
        return out.getvalue()
