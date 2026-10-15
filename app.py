import os
import re
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from flask import Flask, abort, flash, g, redirect, render_template, request, send_from_directory, session, url_for
from flask_wtf.csrf import CSRFProtect
from PIL import Image, UnidentifiedImageError
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from config import Config

CATEGORIES = ["Litter / waste", "Damaged equipment", "Broken lights", "Water / irrigation", "Overgrown plants", "Pathway damage", "Other"]
STATUSES = ["Submitted", "Under Review", "In Progress", "Resolved", "Closed"]
MAX_PHOTO_BYTES = 5 * 1024 * 1024


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    CSRFProtect(app)

    def connect_db():
        db = sqlite3.connect(app.config["DATABASE"])
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        return db

    with connect_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS complaints (
          id INTEGER PRIMARY KEY, tracking_id TEXT UNIQUE NOT NULL, name TEXT NOT NULL, email TEXT NOT NULL,
          location TEXT NOT NULL, category TEXT NOT NULL, description TEXT NOT NULL, photo_filename TEXT,
          status TEXT NOT NULL DEFAULT 'Submitted', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS updates (
          id INTEGER PRIMARY KEY, complaint_id INTEGER NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
          status TEXT NOT NULL, note TEXT, created_at TEXT NOT NULL);
        """)

    def now():
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def get_db():
        if "db" not in g:
            g.db = connect_db()
        return g.db

    @app.teardown_appcontext
    def close_db(_error=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    def admin_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("admin_id"):
                flash("Please sign in to access the admin area.", "info")
                return redirect(url_for("admin_login"))
            return view(*args, **kwargs)
        return wrapped

    @app.context_processor
    def shared_context():
        return {"current_year": datetime.now().year, "categories": CATEGORIES, "statuses": STATUSES}

    @app.route("/")
    def home():
        return render_template("home.html")

    @app.route("/report", methods=["GET", "POST"])
    def report():
        if request.method == "POST":
            values = {key: request.form.get(key, "").strip() for key in ("name", "email", "location", "category", "description")}
            errors = []
            if not values["name"] or len(values["name"]) > 100: errors.append("Enter your name (up to 100 characters).")
            if not values["email"] or len(values["email"]) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", values["email"]): errors.append("Enter a valid email address.")
            if not values["location"] or len(values["location"]) > 160: errors.append("Enter a park or location (up to 160 characters).")
            if values["category"] not in CATEGORIES: errors.append("Choose an issue category from the list.")
            if len(values["description"]) < 10 or len(values["description"]) > 3000: errors.append("Describe the issue in 10 to 3,000 characters.")
            photo = request.files.get("photo")
            photo_name = None
            if photo and photo.filename:
                safe_original = secure_filename(photo.filename)
                ext = safe_original.rsplit(".", 1)[-1].lower() if "." in safe_original else ""
                if ext not in {"jpg", "jpeg", "png", "webp"}:
                    errors.append("Photo must be a JPG, PNG, or WebP image.")
                else:
                    photo.stream.seek(0, os.SEEK_END)
                    size = photo.stream.tell()
                    photo.stream.seek(0)
                    if size > MAX_PHOTO_BYTES:
                        errors.append("Photo must be 5 MB or smaller.")
                    else:
                        try:
                            with Image.open(photo.stream) as image:
                                actual_format = image.format
                                image.verify()
                            expected_formats = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}
                            if actual_format != expected_formats[ext]:
                                errors.append("The photo content does not match its file type.")
                            else:
                                photo.stream.seek(0)
                                photo_name = f"{uuid.uuid4().hex}.{ext}"
                        except (UnidentifiedImageError, OSError):
                            errors.append("The uploaded file is not a valid JPG, PNG, or WebP image.")
            if errors:
                for error in errors: flash(error, "error")
                return render_template("report.html", values=values), 400
            tracking_id = "PC-" + secrets.token_hex(4).upper()
            db = get_db()
            while db.execute("SELECT 1 FROM complaints WHERE tracking_id=?", (tracking_id,)).fetchone():
                tracking_id = "PC-" + secrets.token_hex(4).upper()
            timestamp = now()
            try:
                db.execute("INSERT INTO complaints (tracking_id,name,email,location,category,description,photo_filename,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                           (tracking_id, values["name"], values["email"], values["location"], values["category"], values["description"], photo_name, "Submitted", timestamp, timestamp))
                complaint_id = db.execute("SELECT id FROM complaints WHERE tracking_id=?", (tracking_id,)).fetchone()["id"]
                db.execute("INSERT INTO updates (complaint_id,status,note,created_at) VALUES (?,?,?,?)", (complaint_id, "Submitted", "Complaint received.", timestamp))
                db.commit()
                if photo_name: photo.save(Path(app.config["UPLOAD_FOLDER"]) / photo_name)
            except Exception:
                db.rollback()
                if photo_name: (Path(app.config["UPLOAD_FOLDER"]) / photo_name).unlink(missing_ok=True)
                raise
            return render_template("submitted.html", tracking_id=tracking_id)
        return render_template("report.html", values={})

    @app.route("/track", methods=["GET", "POST"])
    def track():
        tracking_id = request.values.get("tracking_id", "").strip().upper()
        complaint = None
        history = []
        searched = request.method == "POST" or bool(tracking_id)
        if tracking_id:
            complaint = get_db().execute("SELECT tracking_id,location,category,description,status,created_at,updated_at FROM complaints WHERE tracking_id=?", (tracking_id,)).fetchone()
            if complaint:
                history = get_db().execute("SELECT status,note,created_at FROM updates WHERE complaint_id=(SELECT id FROM complaints WHERE tracking_id=?) ORDER BY id", (tracking_id,)).fetchall()
            elif searched: flash("We couldn't find that tracking ID. Check it and try again.", "error")
        return render_template("track.html", complaint=complaint, history=history, tracking_id=tracking_id, searched=searched)

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if session.get("admin_id"): return redirect(url_for("admin_dashboard"))
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            admin = get_db().execute("SELECT id,username,password_hash FROM admins WHERE username=?", (username,)).fetchone()
            if admin and check_password_hash(admin["password_hash"], password):
                session.clear()
                session["admin_id"], session["admin_username"] = admin["id"], admin["username"]
                return redirect(url_for("admin_dashboard"))
            flash("Username or password is incorrect.", "error")
        return render_template("admin_login.html")

    @app.route("/admin/logout", methods=["POST"])
    @admin_required
    def admin_logout():
        session.clear()
        flash("You have signed out.", "success")
        return redirect(url_for("home"))

    @app.route("/admin")
    @admin_required
    def admin_dashboard():
        status_filter = request.args.get("status", "")
        if status_filter and status_filter not in STATUSES: status_filter = ""
        db = get_db()
        counts = {row["status"]: row["count"] for row in db.execute("SELECT status,COUNT(*) AS count FROM complaints GROUP BY status")}
        total = sum(counts.values())
        if status_filter:
            complaints = db.execute("SELECT * FROM complaints WHERE status=? ORDER BY created_at DESC", (status_filter,)).fetchall()
        else:
            complaints = db.execute("SELECT * FROM complaints ORDER BY created_at DESC").fetchall()
        return render_template("admin_dashboard.html", counts=counts, total=total, complaints=complaints, status_filter=status_filter)

    @app.route("/admin/complaint/<int:complaint_id>/update", methods=["POST"])
    @admin_required
    def update_complaint(complaint_id):
        status, note = request.form.get("status", ""), request.form.get("note", "").strip()
        if status not in STATUSES or len(note) > 500:
            flash("Choose a valid status and keep the note under 500 characters.", "error")
            return redirect(url_for("admin_dashboard"))
        db = get_db()
        if not db.execute("SELECT id FROM complaints WHERE id=?", (complaint_id,)).fetchone(): abort(404)
        timestamp = now()
        db.execute("UPDATE complaints SET status=?,updated_at=? WHERE id=?", (status, timestamp, complaint_id))
        db.execute("INSERT INTO updates (complaint_id,status,note,created_at) VALUES (?,?,?,?)", (complaint_id, status, note or None, timestamp))
        db.commit()
        flash("Complaint status and history updated.", "success")
        return redirect(url_for("admin_dashboard", status=request.args.get("status", "")))

    @app.route("/uploads/<path:filename>")
    @admin_required
    def admin_upload(filename):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    @app.cli.command("create-admin")
    def create_admin():
        """Create or replace an administrator account using local prompts."""
        import getpass
        username = input("Admin username: ").strip()
        if len(username) < 3 or len(username) > 80: raise SystemExit("Username must be between 3 and 80 characters.")
        password = getpass.getpass("Admin password (12+ characters): ")
        confirm = getpass.getpass("Confirm password: ")
        if len(password) < 12 or password != confirm: raise SystemExit("Passwords must match and be at least 12 characters.")
        db = connect_db()
        existing = db.execute("SELECT id FROM admins WHERE username=?", (username,)).fetchone()
        if existing: db.execute("UPDATE admins SET password_hash=? WHERE id=?", (generate_password_hash(password), existing["id"]))
        else: db.execute("INSERT INTO admins (username,password_hash,created_at) VALUES (?,?,?)", (username, generate_password_hash(password), now()))
        db.commit(); db.close()
        print("Administrator account saved.")

    @app.errorhandler(413)
    def too_large(_error):
        flash("The request is too large. Photos must be 5 MB or smaller.", "error")
        return render_template("report.html", values={}), 413

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
