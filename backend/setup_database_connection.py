#!/usr/bin/env python3
"""
Database Connection Setup Script for Ayala_database

This script helps you set up the environment variables needed to connect to your Ayala_database.
"""

import os
import shutil

def create_env_file():
    """Create or update .env file with Ayala_database configuration"""
    
    env_content = """# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# FastAPI Configuration
HOST=localhost
PORT=8001
DEBUG=True

# CORS Settings
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# PostgreSQL Database Configuration for Ayala_database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=Ayala_database
DB_USER=postgres
DB_PASSWORD=your_password_here

# Alternative: Full database URL (optional - will be built from components above)
# DATABASE_URL=postgresql://postgres:your_password@localhost:5432/Ayala_database

# JWT Authentication
SECRET_KEY=your_secret_key_here_generate_new_one
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
"""

    # Check if .env already exists
    if os.path.exists('.env'):
        print("📋 Existing .env file found. Creating backup...")
        shutil.copy('.env', '.env.backup')
        print("✅ Backup created as .env.backup")
    
    # Write new .env file
    with open('.env', 'w') as f:
        f.write(env_content)
    
    print("✅ Created .env file with Ayala_database configuration")
    print("\n🔧 Please update the following values in your .env file:")
    print("1. DB_PASSWORD - Your PostgreSQL password")
    print("2. OPENAI_API_KEY - Your OpenAI API key")
    print("3. SECRET_KEY - Generate a secure secret key")

def check_database_requirements():
    """Check if required packages are installed"""
    
    print("🔍 Checking database requirements...")
    
    required_packages = [
        'sqlalchemy',
        'psycopg2-binary',
        'python-dotenv'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package} is installed")
        except ImportError:
            missing_packages.append(package)
            print(f"❌ {package} is missing")
    
    if missing_packages:
        print(f"\n📦 Install missing packages with:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True

def test_postgresql_connection():
    """Test if PostgreSQL is accessible"""
    
    print("\n🔍 Testing PostgreSQL connection...")
    
    try:
        import psycopg2
        
        # Try to connect with default settings
        conn = psycopg2.connect(
            host="localhost",
            port="5432",
            user="postgres",
            password="",  # Empty password for default setup
            database="postgres"  # Connect to default postgres database first
        )
        
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"✅ PostgreSQL is running: {version}")
        
        # Check if Ayala_database exists
        cursor.execute("SELECT 1 FROM pg_database WHERE datname='Ayala_database';")
        db_exists = cursor.fetchone()
        
        if db_exists:
            print("✅ Ayala_database exists")
        else:
            print("❌ Ayala_database does not exist")
            print("📝 Creating Ayala_database...")
            
            # Create the database
            conn.autocommit = True
            cursor.execute("CREATE DATABASE \"Ayala_database\";")
            print("✅ Ayala_database created successfully")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        print("\n🛠️  Troubleshooting steps:")
        print("1. Make sure PostgreSQL is installed and running")
        print("2. Check if the postgres user exists and has the right permissions")
        print("3. Update DB_PASSWORD in .env file if postgres user has a password")
        return False

def main():
    """Main setup function"""
    
    print("🚀 Setting up database connection for Ayala_database...")
    print("=" * 50)
    
    # Step 1: Check requirements
    if not check_database_requirements():
        print("\n❌ Please install missing packages first")
        return
    
    # Step 2: Create .env file
    print("\n" + "=" * 50)
    create_env_file()
    
    # Step 3: Test PostgreSQL
    print("\n" + "=" * 50)
    postgresql_ok = test_postgresql_connection()
    
    # Step 4: Summary
    print("\n" + "=" * 50)
    print("📋 Setup Summary:")
    print("✅ Requirements checked")
    print("✅ .env file configured")
    
    if postgresql_ok:
        print("✅ PostgreSQL connection verified")
        print("\n🎉 Setup complete! You can now run:")
        print("python test_users_connection.py")
    else:
        print("❌ PostgreSQL setup needs attention")
        print("\n📝 Next steps:")
        print("1. Install and start PostgreSQL")
        print("2. Update database credentials in .env file")
        print("3. Run this script again to verify connection")

if __name__ == "__main__":
    main() 