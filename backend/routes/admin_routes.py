"""
API routes for the Admin module, mounted under /api/admin/*.

Every route except /login requires the X-Admin-Token header issued at
login (see services/admin_auth_service.py). The frontend keeps the token in
its admin session and sends it on each call (frontend/utils/admin_api.py).

Besides the original user/inference endpoints, the admin console uses two
generic ones so each new page doesn't need its own route:
  GET  /view/<name>     data for one page   (AdminConsoleService.<name>_view)
  POST /action/<name>   one admin action
"""

from flask import Blueprint, Response, g, jsonify, request

from controllers.admin_controller import AdminController
from services.admin_auth_service import AdminAuthService
from services.admin_console_service import AdminConsoleService

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")

_VIEWS = ("overview", "users", "mastery", "engagement", "live", "competency_map", "materials",
          "questions", "discussions", "gain", "exports", "health")


def init_admin_routes(app, quiz_service=None, practice_service=None):
    console = AdminConsoleService(quiz_service, practice_service)

    @admin_bp.before_request
    def require_admin_token():
        if request.method == "OPTIONS" or request.endpoint == "admin.login":
            return None
        admin_email = AdminAuthService.admin_for_token(request.headers.get("X-Admin-Token"))
        if not admin_email:
            return jsonify({"success": False, "error": "Admin sign-in required", "auth_required": True}), 401
        g.admin_email = admin_email
        return None

    def run(fn):
        """Call fn() and wrap its result/ValueError in the usual JSON shape."""
        try:
            result = fn()
            if isinstance(result, str):
                return jsonify({"success": True, "message": result}), 200
            return jsonify({"success": True, **result}), 200
        except ValueError as e:
            return jsonify({"success": False, "error": str(e)}), 400
        except Exception as e:
            return jsonify({"success": False, "error": f"Request failed: {str(e)}"}), 500

    @admin_bp.route("/login", methods=["POST"])
    def login():
        data = request.get_json() or {}
        email, password = data.get("email", ""), data.get("password", "")
        if not email or not password:
            return jsonify({"success": False, "error": "Email and password are required"}), 400
        token = AdminAuthService.login(email, password)
        if not token:
            return jsonify({"success": False, "error": "Invalid admin email or password"}), 401
        return jsonify({"success": True, "message": "Admin login successful", "token": token,
                        "email": email.strip().lower()}), 200

    @admin_bp.route("/logout", methods=["POST"])
    def logout():
        AdminAuthService.logout(request.headers.get("X-Admin-Token"))
        return jsonify({"success": True}), 200

    # -- original user / inference endpoints ---------------------------
    @admin_bp.route("/users", methods=["GET"])
    def get_all_users():
        result = AdminController.get_all_users()
        return jsonify(result), 200 if result.get("success") else 400

    @admin_bp.route("/users/inference-method", methods=["PUT"])
    def update_all_users_inference_method():
        inference_method = (request.get_json() or {}).get("inference_method")
        if not inference_method:
            return jsonify({"success": False, "error": "inference_method is required"}), 400
        result = AdminController.update_all_users_inference_method(inference_method)
        return jsonify(result), 200 if result.get("success") else 400

    @admin_bp.route("/users/<user_id>/inference-method", methods=["PUT"])
    def update_inference_method(user_id):
        inference_method = (request.get_json() or {}).get("inference_method")
        if not inference_method:
            return jsonify({"success": False, "error": "inference_method is required"}), 400
        result = AdminController.update_inference_method(user_id, inference_method)
        return jsonify(result), 200 if result.get("success") else 400

    # -- admin console -------------------------------------------------
    @admin_bp.route("/view/<name>", methods=["GET"])
    def view(name):
        if name not in _VIEWS:
            return jsonify({"success": False, "error": "Unknown view"}), 404
        if name == "competency_map":
            return run(lambda: console.competency_map_view(request.args.get("unit", "")))
        if name in ("mastery", "gain", "questions"):
            include_test = request.args.get("include_test") == "1"
            return run(lambda: getattr(console, f"{name}_view")(include_test))
        return run(getattr(console, f"{name}_view"))

    @admin_bp.route("/learner/<user_id>", methods=["GET"])
    def learner_detail(user_id):
        return run(lambda: console.learner_detail_view(user_id))

    @admin_bp.route("/lesson", methods=["GET"])
    def lesson():
        return run(lambda: console.lesson_text(request.args.get("unit", ""), int(request.args.get("index", "0"))))

    @admin_bp.route("/export/<key>", methods=["GET"])
    def export(key):
        try:
            text = console.export_csv(key, request.args.get("anonymize", "1") == "1",
                                      request.args.get("include_test") == "1")
            return Response(text, mimetype="text/csv")
        except ValueError as e:
            return jsonify({"success": False, "error": str(e)}), 400

    @admin_bp.route("/admins", methods=["GET"])
    def admins():
        return run(lambda: {"admins": AdminAuthService.list_admins(), "current": g.admin_email})

    @admin_bp.route("/action/<name>", methods=["POST"])
    def action(name):
        data = request.get_json() or {}

        def checked(result):
            ok, message = result
            if not ok:
                raise ValueError(message)
            return message

        actions = {
            "send_reset_link": lambda: console.send_reset_link(data.get("user_id", "")),
            "resend_confirmation": lambda: console.resend_confirmation(data.get("user_id", "")),
            "send_reminders": lambda: console.send_reminders(data.get("user_ids", [])),
            "delete_users": lambda: console.delete_users(data.get("user_ids", [])),
            "delete_test_accounts": lambda: console.delete_users(test_accounts=True),
            "end_session": lambda: console.end_session(data.get("kind", ""), data.get("session_id", "")),
            "delete_post": lambda: console.delete_post(data.get("post_id", "")),
            "delete_lessons": lambda: console.delete_lessons(data.get("unit_code", ""), data.get("subtopic_index")),
            "change_password": lambda: checked(AdminAuthService.change_password(
                g.admin_email, data.get("current_password", ""), data.get("new_password", ""))),
            "add_admin": lambda: checked(AdminAuthService.add_admin(
                data.get("email", ""), data.get("full_name", ""), data.get("password", ""))),
            "set_admin_active": lambda: checked(AdminAuthService.set_active(
                data.get("email", ""), bool(data.get("is_active")), g.admin_email)),
        }
        if name not in actions:
            return jsonify({"success": False, "error": "Unknown action"}), 404
        return run(actions[name])

    app.register_blueprint(admin_bp)
