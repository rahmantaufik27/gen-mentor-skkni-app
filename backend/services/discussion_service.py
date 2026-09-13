"""
Unit Discussion service - a peer-to-peer Q&A forum, one thread per SKKNI
unit (Learning Path -> Discussion). This is the "Collaborative/Peer-Based
Personalization" feature: learners working on the same unit can post
questions and help each other, instead of everyone learning in isolation.

Standalone CRUD over its own unit_discussion_posts table (see
migrations/010_create_unit_discussions_table.py,
013_add_material_scope_to_discussions.py) - independent of Notes,
Reflection, and every other module.

A post is always scoped to a unit_code (NOT NULL), and OPTIONALLY further
scoped to one material within that unit via material_id - verified against
Neo4j before this was added: every material (Concept) has exactly one
parent Unit via (Unit)-[:HAS_CONCEPT]->(Concept), so "per-material" is
always a child of "per-unit", never a sibling of it. material_id is NULL
for the unit's general discussion, or the material's stable id (the same
one reading_materials.py's _material_source_id() already uses - its url,
or "title|unit_code") for a thread about that one material specifically.

Deliberately flat: top-level posts plus at most one level of replies
(parent_post_id) - list_posts() nests replies under their parent in the
returned payload so the frontend never has to do that itself.

Every query is scoped by unit_code (for listing) or user_id (for delete),
but posts themselves are NOT private - unlike Free Notes/Reflection, a
discussion post is inherently visible to every learner, so list_posts()
joins users.full_name at read time so replies always show the CURRENT
name, not a stale copy.
"""

from typing import Dict, Optional
from uuid import uuid4

from config.database import execute_query


class DiscussionService:
    """CRUD for per-unit (optionally per-material) peer discussion posts."""

    def create_post(
        self, user_id: str, unit_code: str, body: str, parent_post_id: Optional[str] = None,
        material_id: Optional[str] = None, material_title: Optional[str] = None,
    ) -> Dict:
        """Create a top-level post (parent_post_id=None) or a reply to an
        existing post, in the unit's general discussion (material_id=None)
        or scoped to one material. Returns {"success": True, "post_id": str}."""
        if not unit_code:
            return {"success": False, "error": "unit_code is required"}
        body = (body or "").strip()
        if not body:
            return {"success": False, "error": "Post cannot be empty"}

        try:
            post_id = str(uuid4())
            execute_query(
                """
                INSERT INTO unit_discussion_posts
                    (id, unit_code, user_id, parent_post_id, body, material_id, material_title)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (post_id, unit_code, user_id, parent_post_id, body, material_id, material_title),
            )
            return {"success": True, "post_id": post_id}
        except Exception as e:
            return {"success": False, "error": f"Failed to create post: {str(e)}"}

    def list_posts(self, unit_code: str, material_id: Optional[str] = None) -> Dict:
        """
        Every post for one unit (or, if material_id is given, just that
        material's thread within the unit), oldest first, each carrying
        its author's current full_name + profile_photo_path, its
        is_best_answer flag, and any replies nested under it (one level).

        Returns {"success": True, "posts": [{"id", "body", "created_at",
        "user_id", "author_name", "author_photo_path", "is_best_answer",
        "material_id", "material_title", "replies": [...]}, ...]}
        """
        if not unit_code:
            return {"success": False, "error": "unit_code is required"}
        try:
            if material_id:
                where_clause, params = "d.unit_code = %s AND d.material_id = %s", (unit_code, material_id)
            else:
                where_clause, params = "d.unit_code = %s AND d.material_id IS NULL", (unit_code,)

            rows = execute_query(
                f"""
                SELECT d.id, d.parent_post_id, d.body, d.created_at, d.user_id, u.full_name,
                       d.is_best_answer, u.profile_photo_path, d.material_id, d.material_title
                FROM unit_discussion_posts d
                JOIN users u ON u.id = d.user_id
                WHERE {where_clause}
                ORDER BY d.created_at ASC
                """,
                params,
                fetch=True,
            ) or []

            posts_by_id: Dict[str, Dict] = {}
            top_level = []
            for (post_id, parent_id, body, created_at, post_user_id, author_name, is_best_answer,
                 author_photo, post_material_id, post_material_title) in rows:
                post = {
                    "id": str(post_id),
                    "parent_post_id": str(parent_id) if parent_id else None,
                    "body": body,
                    "created_at": created_at.isoformat() if created_at else None,
                    "user_id": str(post_user_id),
                    "author_name": author_name,
                    "author_photo_path": author_photo,
                    "is_best_answer": bool(is_best_answer),
                    "material_id": post_material_id,
                    "material_title": post_material_title,
                    "replies": [],
                }
                posts_by_id[post["id"]] = post
                parent = posts_by_id.get(post["parent_post_id"]) if post["parent_post_id"] else None
                if parent:
                    parent["replies"].append(post)
                else:
                    # Top-level post, or a reply whose parent isn't in this
                    # result (shouldn't happen since both share unit_code,
                    # but fall back to showing it flat rather than dropping it).
                    top_level.append(post)

            return {"success": True, "posts": top_level}
        except Exception as e:
            return {"success": False, "error": f"Failed to list posts: {str(e)}"}

    def get_post_counts(self) -> Dict:
        """Post count per unit_code, across ALL units in one query - used
        by the frontend's unit picker so learners can see where the
        discussion is actually active."""
        try:
            rows = execute_query(
                "SELECT unit_code, COUNT(*) FROM unit_discussion_posts GROUP BY unit_code",
                fetch=True,
            ) or []
            return {"success": True, "counts": {unit_code: count for unit_code, count in rows}}
        except Exception as e:
            return {"success": False, "error": f"Failed to load post counts: {str(e)}"}

    def get_material_post_counts(self, unit_code: str) -> Dict:
        """Post count per material_id within one unit (excludes the general
        unit discussion, material_id IS NULL) - used by the material picker
        inside the Discussion page and by Reading Materials' "Discuss"
        links to show how active each material's thread already is."""
        if not unit_code:
            return {"success": False, "error": "unit_code is required"}
        try:
            rows = execute_query(
                """
                SELECT material_id, COUNT(*) FROM unit_discussion_posts
                WHERE unit_code = %s AND material_id IS NOT NULL
                GROUP BY material_id
                """,
                (unit_code,),
                fetch=True,
            ) or []
            return {"success": True, "counts": {material_id: count for material_id, count in rows}}
        except Exception as e:
            return {"success": False, "error": f"Failed to load material post counts: {str(e)}"}

    def set_best_answer(self, user_id: str, reply_id: str, is_best: bool) -> Dict:
        """
        Mark (or unmark) a reply as the best answer to its parent post -
        only the PARENT POST's author may do this (it's their question;
        peers don't get to declare their own answer "best").

        Marking is exclusive: setting one reply's is_best_answer to TRUE
        clears it on every other reply under the same parent in the same
        UPDATE, so "at most one best answer per post" never needs a
        separate cleanup step or a transaction across two statements.
        """
        if not reply_id:
            return {"success": False, "error": "reply_id is required"}

        try:
            rows = execute_query(
                """
                SELECT d.parent_post_id, p.user_id
                FROM unit_discussion_posts d
                JOIN unit_discussion_posts p ON p.id = d.parent_post_id
                WHERE d.id = %s
                """,
                (reply_id,),
                fetch=True,
            ) or []
            if not rows:
                return {"success": False, "error": "Reply not found (or it isn't a reply to anything)"}

            parent_post_id, parent_author_id = rows[0]
            if str(parent_author_id) != str(user_id):
                return {"success": False, "error": "Only the original poster can mark a best answer"}

            if is_best:
                execute_query(
                    "UPDATE unit_discussion_posts SET is_best_answer = (id = %s) WHERE parent_post_id = %s",
                    (reply_id, parent_post_id),
                )
            else:
                execute_query(
                    "UPDATE unit_discussion_posts SET is_best_answer = FALSE WHERE id = %s",
                    (reply_id,),
                )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": f"Failed to update best answer: {str(e)}"}

    def delete_post(self, user_id: str, post_id: str) -> Dict:
        """Delete a post (and its replies, via ON DELETE CASCADE) - scoped
        to the owning user, so nobody can delete someone else's post."""
        if not post_id:
            return {"success": False, "error": "post_id is required"}
        try:
            execute_query(
                "DELETE FROM unit_discussion_posts WHERE id = %s AND user_id = %s",
                (post_id, user_id),
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": f"Failed to delete post: {str(e)}"}
