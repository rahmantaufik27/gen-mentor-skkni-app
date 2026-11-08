"""Dedicated full page for viewing one reading material."""

from utils.auth_guard import require_authentication
from components.material_detail import render_material_detail

require_authentication()
render_material_detail()