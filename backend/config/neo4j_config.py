"""
Neo4j configuration loader from neo4j.ini file.

Mirrors config/database.py's DatabaseConfig pattern: credentials live in a
gitignored .ini file, never in code.
"""

import os
import configparser
from typing import Optional


class Neo4jConfig:
    """Neo4j configuration loader from neo4j.ini file."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize Neo4j configuration.

        Args:
            config_path: Path to neo4j.ini file. Defaults to backend/neo4j.ini
        """
        if config_path is None:
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(backend_dir, "neo4j.ini")

        self.config_path = config_path
        self.config = configparser.ConfigParser()

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Neo4j configuration file not found: {config_path}")

        self.config.read(config_path)

        if not self.config.has_section("neo4j"):
            raise ValueError("Missing [neo4j] section in neo4j.ini")

    def get_connection_params(self) -> dict:
        """
        Get Neo4j connection parameters.

        Returns:
            Dictionary with uri, user, password, database
        """
        section = "neo4j"
        return {
            "uri": self.config.get(section, "uri", fallback="bolt://localhost:7687"),
            "user": self.config.get(section, "user"),
            "password": self.config.get(section, "password"),
            "database": self.config.get(section, "database", fallback="neo4j"),
        }
