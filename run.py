"""DBSafe entry point:  python run.py"""
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    host = os.environ.get("DBSAFE_HOST", "127.0.0.1")
    port = int(os.environ.get("DBSAFE_PORT", "5000"))
    print(f"DBSafe running on http://{host}:{port}")
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
