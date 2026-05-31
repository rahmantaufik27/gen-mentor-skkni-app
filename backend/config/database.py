"""Database configuration and connection management."""

import os
import configparser
import psycopg2
from psycopg2 import Error
from typing import Optional


class DatabaseConfig:
    """Database configuration loader from db.ini file."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize database configuration.
        
        Args:
            config_path: Path to db.ini file. Defaults to backend/db.ini
        """
        if config_path is None:
            # Get the backend directory path
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(backend_dir, "db.ini")
        
        self.config_path = config_path
        self.config = configparser.ConfigParser()
        
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Database configuration file not found: {config_path}")
        
        self.config.read(config_path)
        
        if not self.config.has_section("postgresql"):
            raise ValueError("Missing [postgresql] section in db.ini")
    
    def get_connection_params(self) -> dict:
        """
        Get database connection parameters.
        
        Returns:
            Dictionary with database connection parameters
        """
        section = "postgresql"
        return {
            "host": self.config.get(section, "host"),
            "database": self.config.get(section, "database"),
            "user": self.config.get(section, "user"),
            "password": self.config.get(section, "password"),
            "port": self.config.getint(section, "port", fallback=5432)
        }


def get_db_connection():
    """
    Establish and return a PostgreSQL database connection.
    
    Returns:
        psycopg2 connection object
        
    Raises:
        Exception: If connection fails
    """
    try:
        config = DatabaseConfig()
        params = config.get_connection_params()
        connection = psycopg2.connect(**params)
        return connection
    except Error as e:
        raise Exception(f"Database connection failed: {str(e)}")
    except Exception as e:
        raise Exception(f"Configuration error: {str(e)}")


def execute_query(query: str, params: tuple = None, fetch: bool = False):
    """
    Execute a database query with proper error handling.
    
    Args:
        query: SQL query string
        params: Query parameters tuple (for parameterized queries to prevent SQL injection)
        fetch: If True, returns results; if False, commits transaction
        
    Returns:
        Query results if fetch=True, else None
        
    Raises:
        Exception: If query execution fails
    """
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        if fetch:
            result = cursor.fetchall()
            cursor.close()
            return result
        else:
            connection.commit()
            cursor.close()
            return None
            
    except Error as e:
        if connection:
            connection.rollback()
        raise Exception(f"Query execution failed: {str(e)}")
    finally:
        if connection:
            connection.close()
