import os
import uuid

from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(app.static_folder, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def get_db():
    return psycopg2.connect(
        host=os.getenv("DATABASE_HOST", "localhost"),
        port=int(os.getenv("DATABASE_PORT", 5432)),
        user=os.getenv("DATABASE_USER", "postgres"),
        password=os.getenv("DATABASE_PASSWORD", "postgres"),
        dbname=os.getenv("DATABASE_NAME", "postgres"),
    )


@app.route("/assets/<path:filename>")
def serve_assets(filename):
    return send_from_directory("assets", filename)


@app.route("/")
def index():
    return render_template("index.html")


# ---- Boards ----

@app.route("/api/boards", methods=["GET"])
def list_boards():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id, name, created_at FROM boards ORDER BY created_at DESC")
    boards = [dict(b) for b in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(boards)


@app.route("/api/boards", methods=["POST"])
def create_board():
    data = request.get_json()
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "INSERT INTO boards (name) VALUES (%s) RETURNING id, name, created_at",
        (name,),
    )
    board = dict(cur.fetchone())
    conn.commit()
    cur.close()
    conn.close()
    return jsonify(board), 201


@app.route("/api/boards/<int:board_id>", methods=["GET"])
def get_board(board_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id, name FROM boards WHERE id = %s", (board_id,))
    board = cur.fetchone()
    if not board:
        cur.close()
        conn.close()
        return jsonify({"error": "Board not found"}), 404
    cur.execute(
        "SELECT id, title, description, image_path, pos_x, pos_y FROM cards WHERE board_id = %s",
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
    cur.close()
    conn.close()
    return jsonify({"board": dict(board), "cards": cards, "connections": connections})


@app.route("/api/boards/<int:board_id>", methods=["DELETE"])
def delete_board(board_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM boards WHERE id = %s", (board_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"success": True})


# ---- Cards ----

@app.route("/api/boards/<int:board_id>/cards", methods=["POST"])
def create_card(board_id):
    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    pos_x = float(request.form.get("pos_x", 200))
    pos_y = float(request.form.get("pos_y", 150))

    if not title:
        return jsonify({"error": "Title is required"}), 400

    image_path = None
    if "image" in request.files:
        file = request.files["image"]
        if file and file.filename:
            ext = file.filename.rsplit(".", 1)[-1].lower()
            if ext not in ("jpg", "jpeg", "png"):
                return jsonify({"error": "Only jpg/png images are allowed"}), 400
            filename = f"{uuid.uuid4().hex}.{ext}"
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            image_path = f"/static/uploads/{filename}"

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        INSERT INTO cards (board_id, title, description, image_path, pos_x, pos_y)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, title, description, image_path, pos_x, pos_y
        """,
        (board_id, title, description, image_path, pos_x, pos_y),
    )
    card = dict(cur.fetchone())
    conn.commit()
    cur.close()
    conn.close()
    return jsonify(card), 201


@app.route("/api/cards/<int:card_id>", methods=["PUT"])
def update_card(card_id):
    data = request.get_json()
    fields = []
    values = []
    for field in ("pos_x", "pos_y", "title", "description"):
        if field in data:
            fields.append(f"{field} = %s")
            values.append(data[field])
    if not fields:
        return jsonify({"error": "Nothing to update"}), 400
    values.append(card_id)
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        f"UPDATE cards SET {', '.join(fields)} WHERE id = %s "
        "RETURNING id, title, description, image_path, pos_x, pos_y",
        values,
    )
    card = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return jsonify(dict(card))


@app.route("/api/cards/<int:card_id>", methods=["DELETE"])
def delete_card(card_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM cards WHERE id = %s", (card_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"success": True})


# ---- Connections ----

@app.route("/api/connections", methods=["POST"])
def create_connection():
    data = request.get_json()
    id1 = data.get("card_id_1")
    id2 = data.get("card_id_2")
    if not id1 or not id2:
        return jsonify({"error": "Both card IDs are required"}), 400
    # Normalize order so smaller id is always card_id_1
    if id1 > id2:
        id1, id2 = id2, id1
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
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
def delete_connection():
    data = request.get_json()
    id1 = data.get("card_id_1")
    id2 = data.get("card_id_2")
    if id1 > id2:
        id1, id2 = id2, id1
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM connections WHERE card_id_1 = %s AND card_id_2 = %s",
        (id1, id2),
    )
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"success": True})
