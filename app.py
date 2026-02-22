import os
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt as pyjwt
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)

UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER") or os.path.join(
    app.static_folder, "uploads"
)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
TOKEN_EXPIRY_DAYS = 30


def get_db():
    return psycopg2.connect(
        host=os.getenv("DATABASE_HOST", "localhost"),
        port=int(os.getenv("DATABASE_PORT", 5432)),
        user=os.getenv("DATABASE_USER", "postgres"),
        password=os.getenv("DATABASE_PASSWORD", "postgres"),
        dbname=os.getenv("DATABASE_NAME", "postgres"),
    )


def create_token(user_id):
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRY_DAYS),
    }
    return pyjwt.encode(payload, SECRET_KEY, algorithm="HS256")


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authentication required"}), 401
        token = auth_header[7:]
        try:
            payload = pyjwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            request.user_id = payload["user_id"]
        except pyjwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except pyjwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        return f(*args, **kwargs)

    return decorated


def board_belongs_to_user(board_id, user_id, cur):
    cur.execute(
        "SELECT id FROM boards WHERE id = %s AND user_id = %s", (board_id, user_id)
    )
    return cur.fetchone() is not None


def card_belongs_to_user(card_id, user_id, cur):
    cur.execute(
        "SELECT c.id FROM cards c JOIN boards b ON b.id = c.board_id WHERE c.id = %s AND b.user_id = %s",
        (card_id, user_id),
    )
    return cur.fetchone() is not None


def note_belongs_to_user(note_id, user_id, cur):
    cur.execute(
        "SELECT n.id FROM notes n JOIN boards b ON b.id = n.board_id WHERE n.id = %s AND b.user_id = %s",
        (note_id, user_id),
    )
    return cur.fetchone() is not None


@app.route("/health")
def health():
    return jsonify({"message": "OK"})


@app.route("/assets/<path:filename>")
def serve_assets(filename):
    return send_from_directory("assets", filename)


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/board")
def board():
    return render_template("index.html")


# ---- Auth ----


@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    password_hash = generate_password_hash(password)
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id, email",
            (email, password_hash),
        )
        user = dict(cur.fetchone())
        conn.commit()
    except psycopg2.IntegrityError:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"error": "Email already registered"}), 409
    cur.close()
    conn.close()

    token = create_token(user["id"])
    return jsonify({"token": token, "email": user["email"]}), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id, email, password_hash FROM users WHERE email = %s", (email,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid email or password"}), 401

    token = create_token(user["id"])
    return jsonify({"token": token, "email": user["email"]})


@app.route("/api/auth/me", methods=["GET"])
@require_auth
def get_me():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id, email FROM users WHERE id = %s", (request.user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(dict(user))


# ---- Boards ----


@app.route("/api/boards", methods=["GET"])
@require_auth
def list_boards():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT id, name, created_at FROM boards WHERE user_id = %s ORDER BY created_at DESC",
        (request.user_id,),
    )
    boards = [dict(b) for b in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(boards)


@app.route("/api/boards", methods=["POST"])
@require_auth
def create_board():
    data = request.get_json()
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "INSERT INTO boards (name, user_id) VALUES (%s, %s) RETURNING id, name, created_at",
        (name, request.user_id),
    )
    board = dict(cur.fetchone())
    conn.commit()
    cur.close()
    conn.close()
    return jsonify(board), 201


@app.route("/api/boards/<int:board_id>", methods=["GET"])
@require_auth
def get_board(board_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT id, name FROM boards WHERE id = %s AND user_id = %s",
        (board_id, request.user_id),
    )
    board = cur.fetchone()
    if not board:
        cur.close()
        conn.close()
        return jsonify({"error": "Board not found"}), 404
    cur.execute(
        "SELECT id, title, description, image_path, pos_x, pos_y, pin_position FROM cards WHERE board_id = %s",
        (board_id,),
    )
    cards = [dict(c) for c in cur.fetchall()]
    cur.execute(
        """
        SELECT cn.id, cn.card_id_1, cn.card_id_2
        FROM connections cn
        JOIN cards c1 ON c1.id = cn.card_id_1
        JOIN cards c2 ON c2.id = cn.card_id_2
        WHERE c1.board_id = %s AND c2.board_id = %s
        """,
        (board_id, board_id),
    )
    connections = [dict(c) for c in cur.fetchall()]
    cur.execute(
        "SELECT id, content, pos_x, pos_y FROM notes WHERE board_id = %s",
        (board_id,),
    )
    notes = [dict(n) for n in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(
        {
            "board": dict(board),
            "cards": cards,
            "connections": connections,
            "notes": notes,
        }
    )


@app.route("/api/boards/<int:board_id>", methods=["PATCH"])
@require_auth
def rename_board(board_id):
    data = request.get_json()
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "UPDATE boards SET name = %s WHERE id = %s AND user_id = %s RETURNING id, name",
        (name, board_id, request.user_id),
    )
    board = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    if not board:
        return jsonify({"error": "Board not found"}), 404
    return jsonify(dict(board))


@app.route("/api/boards/<int:board_id>", methods=["DELETE"])
@require_auth
def delete_board(board_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM boards WHERE id = %s AND user_id = %s", (board_id, request.user_id)
    )
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"success": True})


# ---- Cards ----


@app.route("/api/boards/<int:board_id>/cards", methods=["POST"])
@require_auth
def create_card(board_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if not board_belongs_to_user(board_id, request.user_id, cur):
        cur.close()
        conn.close()
        return jsonify({"error": "Board not found"}), 404

    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    pos_x = float(request.form.get("pos_x", 200))
    pos_y = float(request.form.get("pos_y", 150))
    pin_position = request.form.get("pin_position", "center")
    if pin_position not in ("left", "center", "right"):
        pin_position = "center"

    if not title:
        cur.close()
        conn.close()
        return jsonify({"error": "Title is required"}), 400

    image_path = None
    if "image" in request.files:
        file = request.files["image"]
        if file and file.filename:
            ext = file.filename.rsplit(".", 1)[-1].lower()
            if ext not in ("jpg", "jpeg", "png"):
                cur.close()
                conn.close()
                return jsonify({"error": "Only jpg/png images are accepted"}), 400
            filename = f"{uuid.uuid4().hex}.{ext}"
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            image_path = f"/static/uploads/{filename}"

    cur.execute(
        """
        INSERT INTO cards (board_id, title, description, image_path, pos_x, pos_y, pin_position)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id, title, description, image_path, pos_x, pos_y, pin_position
        """,
        (board_id, title, description, image_path, pos_x, pos_y, pin_position),
    )
    card = dict(cur.fetchone())
    conn.commit()
    cur.close()
    conn.close()
    return jsonify(card), 201


@app.route("/api/cards/<int:card_id>", methods=["PUT"])
@require_auth
def update_card(card_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if not card_belongs_to_user(card_id, request.user_id, cur):
        cur.close()
        conn.close()
        return jsonify({"error": "Card not found"}), 404

    content_type = request.content_type or ""
    if "multipart/form-data" in content_type:
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip() or None
        if not title:
            cur.close()
            conn.close()
            return jsonify({"error": "Title is required"}), 400
        fields = ["title = %s", "description = %s"]
        values = [title, description]
        pin_position = request.form.get("pin_position")
        if pin_position in ("left", "center", "right"):
            fields.append("pin_position = %s")
            values.append(pin_position)
        if "image" in request.files:
            file = request.files["image"]
            if file and file.filename:
                ext = file.filename.rsplit(".", 1)[-1].lower()
                if ext not in ("jpg", "jpeg", "png"):
                    cur.close()
                    conn.close()
                    return jsonify({"error": "Only jpg/png images are accepted"}), 400
                filename = f"{uuid.uuid4().hex}.{ext}"
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                fields.append("image_path = %s")
                values.append(f"/static/uploads/{filename}")
        values.append(card_id)
    else:
        data = request.get_json()
        fields = []
        values = []
        for field in ("pos_x", "pos_y", "title", "description"):
            if field in data:
                fields.append(f"{field} = %s")
                values.append(data[field])
        if not fields:
            cur.close()
            conn.close()
            return jsonify({"error": "Nothing to update"}), 400
        values.append(card_id)

    cur.execute(
        f"UPDATE cards SET {', '.join(fields)} WHERE id = %s "
        "RETURNING id, title, description, image_path, pos_x, pos_y, pin_position",
        values,
    )
    card = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return jsonify(dict(card))


@app.route("/api/cards/<int:card_id>", methods=["DELETE"])
@require_auth
def delete_card(card_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if not card_belongs_to_user(card_id, request.user_id, cur):
        cur.close()
        conn.close()
        return jsonify({"error": "Card not found"}), 404
    cur.execute("DELETE FROM cards WHERE id = %s", (card_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"success": True})


# ---- Notes ----


@app.route("/api/boards/<int:board_id>/notes", methods=["POST"])
@require_auth
def create_note(board_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if not board_belongs_to_user(board_id, request.user_id, cur):
        cur.close()
        conn.close()
        return jsonify({"error": "Board not found"}), 404

    data = request.get_json()
    content = (data.get("content") or "").strip()
    pos_x = float(data.get("pos_x", 200))
    pos_y = float(data.get("pos_y", 150))
    cur.execute(
        "INSERT INTO notes (board_id, content, pos_x, pos_y) VALUES (%s, %s, %s, %s) "
        "RETURNING id, content, pos_x, pos_y",
        (board_id, content, pos_x, pos_y),
    )
    note = dict(cur.fetchone())
    conn.commit()
    cur.close()
    conn.close()
    return jsonify(note), 201


@app.route("/api/notes/<int:note_id>", methods=["PUT"])
@require_auth
def update_note(note_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if not note_belongs_to_user(note_id, request.user_id, cur):
        cur.close()
        conn.close()
        return jsonify({"error": "Note not found"}), 404

    data = request.get_json()
    fields = []
    values = []
    for field in ("content", "pos_x", "pos_y"):
        if field in data:
            fields.append(f"{field} = %s")
            values.append(data[field])
    if not fields:
        cur.close()
        conn.close()
        return jsonify({"error": "Niente da aggiornare"}), 400
    values.append(note_id)
    cur.execute(
        f"UPDATE notes SET {', '.join(fields)} WHERE id = %s "
        "RETURNING id, content, pos_x, pos_y",
        values,
    )
    note = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return jsonify(dict(note))


@app.route("/api/notes/<int:note_id>", methods=["DELETE"])
@require_auth
def delete_note(note_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if not note_belongs_to_user(note_id, request.user_id, cur):
        cur.close()
        conn.close()
        return jsonify({"error": "Note not found"}), 404
    cur.execute("DELETE FROM notes WHERE id = %s", (note_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"success": True})


# ---- Connections ----


@app.route("/api/connections", methods=["POST"])
@require_auth
def create_connection():
    data = request.get_json()
    id1 = data.get("card_id_1")
    id2 = data.get("card_id_2")
    if not id1 or not id2:
        return jsonify({"error": "Both card IDs are required"}), 400
    if id1 > id2:
        id1, id2 = id2, id1

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if not card_belongs_to_user(id1, request.user_id, cur) or not card_belongs_to_user(
        id2, request.user_id, cur
    ):
        cur.close()
        conn.close()
        return jsonify({"error": "Card not found"}), 404

    try:
        cur.execute(
            "INSERT INTO connections (card_id_1, card_id_2) VALUES (%s, %s) "
            "RETURNING id, card_id_1, card_id_2",
            (id1, id2),
        )
        connection = dict(cur.fetchone())
        conn.commit()
        cur.close()
        conn.close()
        return jsonify(connection), 201
    except psycopg2.IntegrityError:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"error": "Connection already exists"}), 409


@app.route("/api/connections", methods=["DELETE"])
@require_auth
def delete_connection():
    data = request.get_json()
    id1 = data.get("card_id_1")
    id2 = data.get("card_id_2")
    if id1 > id2:
        id1, id2 = id2, id1

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if not card_belongs_to_user(id1, request.user_id, cur) or not card_belongs_to_user(
        id2, request.user_id, cur
    ):
        cur.close()
        conn.close()
        return jsonify({"error": "Card not found"}), 404

    cur.execute(
        "DELETE FROM connections WHERE card_id_1 = %s AND card_id_2 = %s",
        (id1, id2),
    )
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"success": True})
