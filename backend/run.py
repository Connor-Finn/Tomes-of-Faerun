"""Start the API.

    python run.py            -> http://127.0.0.1:5000
    python run.py --reset    wipe the database and re-seed it
"""
import os
import sys

from tof import create_app

app = create_app()

if __name__ == "__main__":
    if "--reset" in sys.argv:
        from tof.seed import reset_database
        with app.app_context():
            reset_database()
        print("Database reset and seeded.")
    app.run(
        host="127.0.0.1",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG", "1") == "1",
    )
