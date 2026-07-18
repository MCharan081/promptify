from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
import random
import os

app = Flask(__name__)
app.secret_key = "replace-this-with-a-secure-random-key-in-production"
DB = "promptify.db"

ROLE = {
    "coding": "Senior Software Engineer",
    "writing": "Professional Writer",
    "study": "Expert Educator",
    "marketing": "Marketing Strategist",
    "custom": "Helpful AI Assistant",
}

BANK = {
    "coding": [
        "Write a Python Bank Management System using OOP.",
        "Create a Flask REST API with CRUD operations.",
    ],
    "writing": [
        "Write an article about Artificial Intelligence.",
        "Write a motivational speech for students.",
    ],
    "study": [
        "Explain Morphology in Natural Language Processing.",
        "Explain Machine Learning with examples.",
    ],
    "marketing": [
        "Write Instagram ads for a clothing brand.",
        "Create SEO content for an AI website.",
    ],
}


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(conn, table, column, coltype="TEXT"):
    """Add a column to an existing table if it doesn't already exist (safe upgrade)."""
    cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")


def init_db():
    try:
        conn = db()
        # Users Table
        conn.execute(
            """CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            username TEXT UNIQUE, password TEXT, 
            name TEXT, email TEXT, gender TEXT)"""
        )
        # History
        # source_prompt = the raw text the USER typed (before generation/enhancement).
        # prompt = the AI-built output shown to the user.
        conn.execute(
            """CREATE TABLE IF NOT EXISTS history(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, prompt TEXT, category TEXT,
            action TEXT, source_prompt TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""
        )
        # Favorites
        conn.execute(
            """CREATE TABLE IF NOT EXISTS favorites(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, prompt TEXT, category TEXT,
            source_prompt TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""
        )
        # Saved
        conn.execute(
            """CREATE TABLE IF NOT EXISTS saved(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, prompt TEXT, category TEXT,
            source_prompt TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""
        )

        # Safe upgrade path for databases created before this column existed.
        _ensure_column(conn, "history", "source_prompt", "TEXT")
        _ensure_column(conn, "favorites", "source_prompt", "TEXT")
        _ensure_column(conn, "saved", "source_prompt", "TEXT")

        # Prevent the same prompt being added twice for the same user
        # (this is what stops Save / Favorite from creating duplicates).
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_favorites_user_prompt ON favorites(user_id, prompt)"
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_saved_user_prompt ON saved(user_id, prompt)"
        )

        conn.commit()
        conn.close()
    except sqlite3.Error:
        print("Database system initialization error.")


def mock_call_model(instruction):
    role = "custom"
    if "Professional Writer" in instruction: role = "writing"
    elif "Senior Software Engineer" in instruction: role = "coding"
    elif "Expert Educator" in instruction: role = "study"
    elif "Marketing Strategist" in instruction: role = "marketing"

    topic = "General Input"
    if "Original prompt: " in instruction:
        topic = instruction.split("Original prompt: ")[-1].split("\n")[0].strip()
    elif "Topic: " in instruction:
        topic = instruction.split("Topic: ")[-1].split("\n")[0].strip()

    if "Improve this prompt" in instruction:
        if role == "coding":
            return f"### 💻 Optimized Senior Developer Prompt\nAct as an expert Software Engineer. Refactor and maximize the execution efficiency of the following implementation: '{topic}'. Ensure optimal time complexity, modular clean functions, and robust handling blocks."
        elif role == "writing":
            return f"### ✍️ Enhanced Professional Writer Prompt\nAct as a master editor and creative copywriter. Rewrite and elevate the creative depth, narrative pacing, and engaging tone of the core idea: '{topic}'."
        elif role == "study":
            return f"### 🎓 Refined Academic Lesson Blueprint\nAct as a university professor. Reconstruct the pedagogical explanation of '{topic}' into a structured, step-by-step framework complete with real-world scenarios and focus definitions."
        elif role == "marketing":
            return f"### 📈 Premium Growth Marketing Strategy\nAct as a high-conversion digital marketer. Redraft the advertisement blueprint for '{topic}' to maximize conversion parameters, clear pain-point metrics, and distinct Call-To-Action options."
        else:
            return f"### ✧ Improved AI Prompt Constraints\nOptimized prompt structure for '{topic}' focusing on enhanced context layout, output limits, and specific response formats."

    if role == "coding":
        return f"### 💻 New System Architecture Blueprint\nAct as a Senior Software Engineer specializing in scalable applications. Create structural templates, production boilerplate logic code, and unit test edge cases for handling: '{topic}'."
    elif role == "writing":
        return f"### ✍️ New Content Composition Layout\nAct as an author. Design a comprehensive narrative outline, three click-worthy header variations, and an immersive introduction tracking the theme: '{topic}'."
    elif role == "study":
        return f"### 🎓 New Educational Roadmap\nAct as an expert tutor. Provide a full study plan analyzing '{topic}'. Break down definitions for a beginner, present a technical deep-dive breakdown, and add concept evaluation queries."
    elif role == "marketing":
        return f"### 📈 New High-Conversion Copy Campaign\nAct as a growth strategist. Formulate a full multi-channel launching plan, target audience demographic parameters, and alternative promotional messaging drafts for: '{topic}'."
    else:
        return f"### ✧ New AI Functional Prompt\nAct as a helpful general AI system assistant. Deliver an exhaustive architectural exploration and systematic investigation parameters into the core subject: '{topic}'."


@app.route("/")
def index():
    if "user_id" not in session:
        return render_template("index.html", auth_view=True)
    return render_template("index.html", auth_view=False)


# --- AUTHENTICATION ENDPOINTS ---
@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json(force=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    gender = data.get("gender", "Male").strip()

    if not username or not password or not name or not email:
        return jsonify({"error": "All profile fields are required."}), 400

    try:
        conn = db()
        conn.execute(
            "INSERT INTO users (username, password, name, email, gender) VALUES (?, ?, ?, ?, ?)",
            (username, password, name, email, gender)
        )
        conn.commit()
        conn.close()
        return jsonify({"message": "Registration successful! Please login now."})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Username already exists."}), 400
    except sqlite3.Error:
        return jsonify({"error": "Database error. Please try again later."}), 500


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(force=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    try:
        conn = db()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ? AND password = ?", (username, password)
        ).fetchone()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return jsonify({"message": "Login successful!"})
        
        return jsonify({"error": "Invalid username or password."}), 401
    except sqlite3.Error:
        return jsonify({"error": "Database is temporarily unavailable."}), 500


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully"})


@app.route("/api/auth/verify-user", methods=["POST"])
def verify_user():
    data = request.get_json(force=True) or {}
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    
    if not username or not email:
        return jsonify({"error": "Username and Email are both required."}), 400

    try:
        conn = db()
        user = conn.execute(
            "SELECT id FROM users WHERE username = ? AND email = ?", (username, email)
        ).fetchone()
        conn.close()
        
        if user:
            return jsonify({"message": "User credentials verified."}), 200
        return jsonify({"error": "No user matches that username and email combination."}), 404
    except sqlite3.Error:
        return jsonify({"error": "Database connection error."}), 500


@app.route("/api/auth/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json(force=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    
    if not username or not password:
        return jsonify({"error": "Missing critical parameters."}), 400
        
    try:
        conn = db()
        conn.execute("UPDATE users SET password = ? WHERE username = ?", (password, username))
        conn.commit()
        conn.close()
        return jsonify({"message": "Password updated successfully."})
    except sqlite3.Error:
        return jsonify({"error": "Failed to update password in database."}), 500


@app.route("/api/profile", methods=["GET"])
def get_profile():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        conn = db()
        user = conn.execute("SELECT username, name, email, gender FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        conn.close()
        return jsonify(dict(user))
    except sqlite3.Error:
        return jsonify({"error": "Could not read profile metadata."}), 500


@app.route("/api/profile", methods=["POST"])
def update_profile():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(force=True) or {}
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    gender = data.get("gender", "Male").strip()
    password = data.get("password", "").strip()
    
    if not name or not email:
        return jsonify({"error": "Name and Email are required."}), 400
        
    try:
        conn = db()
        if password:
            conn.execute(
                "UPDATE users SET name = ?, email = ?, gender = ?, password = ? WHERE id = ?",
                (name, email, gender, password, session["user_id"])
            )
        else:
            conn.execute(
                "UPDATE users SET name = ?, email = ?, gender = ? WHERE id = ?",
                (name, email, gender, session["user_id"])
            )
        conn.commit()
        conn.close()
        return jsonify({"message": "Profile updated smoothly!"})
    except sqlite3.Error:
        return jsonify({"error": "Could not save profile changes."}), 500


# --- GENERATOR PIPELINES ---
@app.route("/api/generate", methods=["POST"])
def generate():
    if "user_id" not in session: return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(force=True) or {}
    category = data.get("category", "coding")
    topic = (data.get("prompt") or "").strip()

    user_typed = topic  # what the user actually typed, before we fall back to a random topic
    if not topic:
        topic = random.choice(BANK.get(category, BANK["coding"]))
        user_typed = topic  # nothing was typed, so the random topic is what "produced" this result

    instruction = f"Create AI prompt.\nRole: {ROLE.get(category)}\nTopic: {topic}\n"
    prompt = mock_call_model(instruction)

    try:
        conn = db()
        conn.execute(
            "INSERT INTO history(user_id, prompt, category, action, source_prompt) VALUES(?,?,?,?,?)",
            (session["user_id"], prompt, category, "generated", user_typed)
        )
        conn.commit()
        conn.close()
        return jsonify({"prompt": prompt, "category": category, "source_prompt": user_typed})
    except sqlite3.Error:
        return jsonify({"error": "Could not save generation history."}), 500


@app.route("/api/enhance", methods=["POST"])
def enhance():
    if "user_id" not in session: return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(force=True) or {}
    text = (data.get("prompt") or "").strip()
    category = data.get("category", "coding")

    if not text:
        return jsonify({"error": "Prompt text is required"}), 400

    instruction = f"Improve this prompt.\nRole: {ROLE.get(category)}\nOriginal prompt: {text}\n"
    improved = mock_call_model(instruction)

    try:
        conn = db()
        conn.execute(
            "INSERT INTO history(user_id, prompt, category, action, source_prompt) VALUES(?,?,?,?,?)",
            (session["user_id"], improved, category, "enhanced", text)
        )
        conn.commit()
        conn.close()
        return jsonify({"prompt": improved, "category": category, "source_prompt": text})
    except sqlite3.Error:
        return jsonify({"error": "Could not save optimization data."}), 500


# --- COLLECTIONS ---
@app.route("/api/history", methods=["GET"])
def get_history():
    if "user_id" not in session: return jsonify([]), 401
    try:
        conn = db()
        rows = conn.execute("SELECT * FROM history WHERE user_id = ? ORDER BY id DESC LIMIT 50", (session["user_id"],)).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except sqlite3.Error:
        return jsonify([])


@app.route("/api/history/<int:hid>", methods=["DELETE"])
def delete_history_item(hid):
    if "user_id" not in session: return jsonify({"error": "Unauthorized"}), 401
    try:
        conn = db()
        conn.execute("DELETE FROM history WHERE id=? AND user_id=?", (hid, session["user_id"]))
        conn.commit()
        conn.close()
        return jsonify({"message": "Removed from History"})
    except sqlite3.Error:
        return jsonify({"error": "Could not delete history item."}), 500


@app.route("/api/history/clear", methods=["DELETE"])
def clear_history():
    if "user_id" not in session: return jsonify({"error": "Unauthorized"}), 401
    try:
        conn = db()
        conn.execute("DELETE FROM history WHERE user_id = ?", (session["user_id"],))
        conn.commit()
        conn.close()
        return jsonify({"message": "History cleared"})
    except sqlite3.Error:
        return jsonify({"error": "Could not purge database rows."}), 500


@app.route("/api/favorites", methods=["GET", "POST"])
def handle_favorites():
    if "user_id" not in session: return jsonify([]), 401
    try:
        conn = db()
        if request.method == "POST":
            data = request.get_json(force=True) or {}
            prompt = data.get("prompt", "")
            cur = conn.execute(
                "INSERT OR IGNORE INTO favorites(user_id, prompt, category, source_prompt) VALUES(?,?,?,?)",
                (session["user_id"], prompt, data.get("category", "custom"), data.get("source_prompt", prompt))
            )
            conn.commit()
            already_existed = cur.rowcount == 0
            conn.close()
            if already_existed:
                return jsonify({"message": "Already in Favorites", "duplicate": True})
            return jsonify({"message": "Added to Favorites", "duplicate": False})
        else:
            rows = conn.execute("SELECT * FROM favorites WHERE user_id = ? ORDER BY id DESC", (session["user_id"],)).fetchall()
            conn.close()
            return jsonify([dict(r) for r in rows])
    except sqlite3.Error:
        return jsonify({"error": "Favorites storage connection failed."}), 500


@app.route("/api/favorites/<int:fid>", methods=["DELETE"])
def delete_favorite(fid):
    if "user_id" not in session: return jsonify({"error": "Unauthorized"}), 401
    try:
        conn = db()
        conn.execute("DELETE FROM favorites WHERE id=? AND user_id=?", (fid, session["user_id"]))
        conn.commit()
        conn.close()
        return jsonify({"message": "Removed from Favorites"})
    except sqlite3.Error:
        return jsonify({"error": "Could not remove element item."}), 500


@app.route("/api/saved", methods=["GET", "POST"])
def handle_saved():
    if "user_id" not in session: return jsonify([]), 401
    try:
        conn = db()
        if request.method == "POST":
            data = request.get_json(force=True) or {}
            prompt = data.get("prompt", "")
            cur = conn.execute(
                "INSERT OR IGNORE INTO saved(user_id, prompt, category, source_prompt) VALUES(?,?,?,?)",
                (session["user_id"], prompt, data.get("category", "custom"), data.get("source_prompt", prompt))
            )
            conn.commit()
            already_existed = cur.rowcount == 0
            conn.close()
            if already_existed:
                return jsonify({"message": "Already in Saved", "duplicate": True})
            return jsonify({"message": "Saved successfully", "duplicate": False})
        else:
            rows = conn.execute("SELECT * FROM saved WHERE user_id = ? ORDER BY id DESC", (session["user_id"],)).fetchall()
            conn.close()
            return jsonify([dict(r) for r in rows])
    except sqlite3.Error:
        return jsonify({"error": "Collection files storage link dropped."}), 500


@app.route("/api/saved/<int:sid>", methods=["DELETE"])
def delete_saved(sid):
    if "user_id" not in session: return jsonify({"error": "Unauthorized"}), 401
    try:
        conn = db()
        conn.execute("DELETE FROM saved WHERE id=? AND user_id=?", (sid, session["user_id"]))
        conn.commit()
        conn.close()
        return jsonify({"message": "Removed from Saved"})
    except sqlite3.Error:
        return jsonify({"error": "Could not delete layout collection file."}), 500


# --- SETTINGS / PURGE ALL PROMPTS FIX ---
@app.route("/api/settings/purge-databases", methods=["DELETE"])
def purge_databases():
    if "user_id" not in session: return jsonify({"error": "Unauthorized"}), 401
    try:
        conn = db()
        conn.execute("DELETE FROM history WHERE user_id = ?", (session["user_id"],))
        conn.execute("DELETE FROM favorites WHERE user_id = ?", (session["user_id"],))
        conn.execute("DELETE FROM saved WHERE user_id = ?", (session["user_id"],))
        conn.commit()
        conn.close()
        return jsonify({"message": "All database layers dropped. System structure cleanly reinitialized."})
    except sqlite3.Error:
        return jsonify({"error": "Failed complete drop layout wipe process."}), 500


@app.route("/api/settings/delete-account", methods=["DELETE"])
def delete_account():
    if "user_id" not in session: return jsonify({"error": "Unauthorized"}), 401
    uid = session["user_id"]
    try:
        conn = db()
        conn.execute("DELETE FROM users WHERE id = ?", (uid,))
        conn.execute("DELETE FROM history WHERE user_id = ?", (uid,))
        conn.execute("DELETE FROM favorites WHERE user_id = ?", (uid,))
        conn.execute("DELETE FROM saved WHERE user_id = ?", (uid,))
        conn.commit()
        conn.close()
        session.clear()
        return jsonify({"message": "Account metrics and user files deleted."})
    except sqlite3.Error:
        return jsonify({"error": "Failed profile termination chain metrics process."}), 500


init_db()
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)