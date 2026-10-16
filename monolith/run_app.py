"""
Application Launcher
====================
Run this script to start the Flask web application
"""

import os
import sys
import warnings
warnings.filterwarnings('ignore')

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from utils.database import init_db

if __name__ == '__main__':
    print("\n" + "="*60)
    print("BANGALORE CLIMATE ANALYTICS SYSTEM")
    print("Flask Web Application")
    print("="*60)
    
    # Initialize database
    print("\nInitializing database...")
    init_db()
    
    # Check for trained models
    if not os.path.exists('saved_models'):
        print("\n⚠️  WARNING: No trained models found!")
        print("   Please run 'python train_models.py' first")
        print("   Using fallback synthetic forecasts...")
    else:
        models_found = os.listdir('saved_models')
        if len(models_found) > 0:
            print(f"\n✅ Found {len(models_found)} trained models")
        else:
            print("\n⚠️  Models directory exists but is empty")
            print("   Please run 'python train_models.py'")
    
    print("\n" + "="*60)
    print("Starting Flask server...")
    print("Visit: http://127.0.0.1:5000")
    print("="*60 + "\n")
    
    app.run(debug=True, host='127.0.0.1', port=5000)