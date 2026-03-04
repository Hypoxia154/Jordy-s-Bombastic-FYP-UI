import sys
import os

# Add the current directory to sys.path so we can import app modules
# Assumes this script is run from the 'backend' directory or project root
sys.path.append(os.getcwd())

from app.services.vector_store import VectorService

def flush_database():
    print("WARNING: This will permanently delete all ingested documents from the database.")
    confirmation = input("Are you sure? Type 'yes' to proceed: ")
    
    if confirmation.lower() == "yes":
        service = VectorService()
        result = service.clear_database()
        print(result)
    else:
        print("Operation cancelled.")

if __name__ == "__main__":
    flush_database()
