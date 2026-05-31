"""
Quick Setup Script for Authentication Module
This script automates the installation and initialization of the authentication system.
"""

import os
import sys
import subprocess
from pathlib import Path


def run_command(command, description):
    """Run a shell command and return success status."""
    print(f"\n{'='*60}")
    print(f">>> {description}")
    print(f"{'='*60}")
    try:
        result = subprocess.run(command, shell=True, capture_output=False, text=True)
        return result.returncode == 0
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        return False


def main():
    """Main setup function."""
    print("\n" + "="*60)
    print("GEN-MENTOR AUTHENTICATION SETUP")
    print("="*60)
    
    # Get the project root (gen-app directory)
    script_dir = Path(__file__).parent.absolute()
    backend_dir = script_dir / "backend"
    frontend_dir = script_dir / "frontend"
    
    print(f"\nProject root: {script_dir}")
    print(f"Backend dir: {backend_dir}")
    print(f"Frontend dir: {frontend_dir}")
    
    # Check if directories exist
    if not backend_dir.exists() or not frontend_dir.exists():
        print("\n✗ Error: Backend or frontend directory not found!")
        return False
    
    # Step 1: Install backend dependencies
    print("\n\n" + "="*60)
    print("STEP 1: Installing Backend Dependencies")
    print("="*60)
    backend_cmd = f"cd {backend_dir} && pip install -r requirements.txt"
    if not run_command(backend_cmd, "Installing backend packages"):
        print("✗ Failed to install backend dependencies")
        return False
    print("✓ Backend dependencies installed successfully")
    
    # Step 2: Check database connection
    print("\n\n" + "="*60)
    print("STEP 2: Checking Database Configuration")
    print("="*60)
    db_ini = backend_dir / "db.ini"
    if not db_ini.exists():
        print(f"✗ Error: db.ini not found at {db_ini}")
        return False
    print(f"✓ Database config found: {db_ini}")
    
    # Step 3: Initialize database
    print("\n\n" + "="*60)
    print("STEP 3: Initializing Database")
    print("="*60)
    test_db_cmd = f"""
cd {backend_dir} && python -c "
from config.database import DatabaseConfig, execute_query
from migrations.001_create_users_table import create_users_table, check_users_table_exists

print('Testing database connection...')
try:
    config = DatabaseConfig()
    params = config.get_connection_params()
    print(f'✓ Database config loaded: {{params[\"host\"]}}:{{params[\"port\"]}}/{{params[\"database\"]}}')
    
    print('Creating users table...')
    create_users_table()
    
    print('Checking users table...')
    check_users_table_exists()
    
    print('✓ Database initialization complete!')
except Exception as e:
    print(f'✗ Database error: {{str(e)}}')
    exit(1)
"
"""
    if not run_command(test_db_cmd, "Testing database and creating tables"):
        print("✗ Failed to initialize database")
        print("\nPlease ensure:")
        print("  1. PostgreSQL is running on localhost:5432")
        print("  2. Database credentials in db.ini are correct")
        print("  3. Database 'genmentorskknidb' exists")
        return False
    
    # Step 4: Install frontend dependencies
    print("\n\n" + "="*60)
    print("STEP 4: Installing Frontend Dependencies")
    print("="*60)
    frontend_cmd = f"cd {frontend_dir} && pip install -r requirements.txt"
    if not run_command(frontend_cmd, "Installing frontend packages"):
        print("✗ Failed to install frontend dependencies")
        return False
    print("✓ Frontend dependencies installed successfully")
    
    # Summary
    print("\n\n" + "="*60)
    print("SETUP COMPLETE! ✓")
    print("="*60)
    print("\nYou can now start the application:")
    print(f"\n1. Start backend:")
    print(f"   cd {backend_dir}")
    print(f"   python app.py")
    print(f"\n2. Start frontend (in another terminal):")
    print(f"   cd {frontend_dir}")
    print(f"   streamlit run main.py")
    print(f"\n3. Access the application:")
    print(f"   http://localhost:8501")
    print("\n" + "="*60 + "\n")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
