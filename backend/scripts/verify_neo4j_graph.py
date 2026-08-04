"""
Read-only sanity-check script for the Neo4j knowledge graph. Reports node/
relationship counts and confirms the app's Unit-code convention (Unit.kode,
full 4-segment codes) lines up with knowledge_target.json.

Does NOT write anything - the graph (Unit/Concept/Evaluation/Option/Answer/
Level) already exists and is owned outside this app; this app only adds
User nodes and MASTERY relationships (done automatically by the app itself,
not by this script - see services/neo4j_service.py).

    cd backend && python scripts/verify_neo4j_graph.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.neo4j_service import Neo4jService


def main():
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    service = Neo4jService()

    print("Neo4j knowledge graph report")
    print("=" * 50)

    counts = service._run_query(
        "MATCH (n) RETURN labels(n) AS labels, count(*) AS count ORDER BY count DESC",
        purpose="verify_counts",
    )
    for row in counts:
        print(f"  {row['labels']}: {row['count']}")

    graph_units = {
        row["kode"]
        for row in service._run_query("MATCH (u:Unit) RETURN u.kode AS kode", purpose="verify_units")
    }

    target_path = os.path.join(backend_dir, "data", "knowledge_target.json")
    with open(target_path, "r", encoding="utf-8") as f:
        expected_units = {u["unit_code"] for u in json.load(f).get("units", [])}

    print()
    print("Unit.kode coverage vs knowledge_target.json:")
    missing = expected_units - graph_units
    extra = graph_units - expected_units
    if not missing and not extra:
        print("  OK - all 6 units match exactly.")
    else:
        if missing:
            print(f"  Missing from graph: {sorted(missing)}")
        if extra:
            print(f"  In graph but not in knowledge_target.json: {sorted(extra)}")

    user_count = service._run_query("MATCH (u:User) RETURN count(u) AS c", purpose="verify_users")
    mastery_count = service._run_query("MATCH ()-[m:MASTERY]->() RETURN count(m) AS c", purpose="verify_mastery")
    print()
    print(f"Users synced so far:   {user_count[0]['c'] if user_count else 0}")
    print(f"MASTERY relationships: {mastery_count[0]['c'] if mastery_count else 0}")

    service.close()
    print()
    print("Done. See logs/neo4j.log for the full query log.")


if __name__ == "__main__":
    main()
