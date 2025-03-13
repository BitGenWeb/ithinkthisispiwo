import os
import hashlib
import sqlite3
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
import logging
import shutil

app = Flask(__name__)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s - [PID:%(process)d TID:%(thread)d]',
    handlers=[logging.FileHandler("server.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Константы
DB_PATH = "server.db"
BUILDS_DIR = "server_builds"
DATETIME_FORMAT = "%Y-%m-%d"

if not os.path.exists(BUILDS_DIR):
    os.makedirs(BUILDS_DIR)
    logger.info(f"Created builds directory at {BUILDS_DIR}")


# Инициализация базы данных
def init_db():
    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
                        username TEXT PRIMARY KEY,
                        password TEXT,
                        license_expiry TEXT,
                        role TEXT DEFAULT 'Player',
                        uuid TEXT)''')  # Добавили поле uuid
        c.execute('''CREATE TABLE IF NOT EXISTS builds (
                        build_name TEXT PRIMARY KEY,
                        hash TEXT,
                        created_at TEXT,
                        mc_version TEXT DEFAULT 'Unknown',
                        modloader TEXT DEFAULT 'Unknown')''')
        c.execute('''CREATE TABLE IF NOT EXISTS user_builds (
                        username TEXT,
                        build_name TEXT,
                        FOREIGN KEY(username) REFERENCES users(username),
                        FOREIGN KEY(build_name) REFERENCES builds(build_name))''')

        # Удаляем дубликаты перед созданием индекса
        c.execute("""
            DELETE FROM user_builds
            WHERE rowid NOT IN (
                SELECT MIN(rowid)
                FROM user_builds
                GROUP BY username, build_name
            )
        """)

        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS unique_user_build ON user_builds (username, build_name)")
        conn.commit()
        logger.info("Database initialized successfully")


# Вычисление хеша папки
def calculate_folder_hash(folder_path):
    sha256 = hashlib.sha256()
    try:
        for root, _, files in sorted(os.walk(folder_path)):
            for file in sorted(files):
                file_path = os.path.join(root, file)
                with open(file_path, "rb") as f:
                    sha256.update(f.read())
        return sha256.hexdigest()
    except Exception as e:
        logger.error(f"Error calculating folder hash for {folder_path}: {str(e)}")
        return None


# Обновление или добавление сборки в базу данных
def update_build_in_db(build_name, build_path, conn):
    c = conn.cursor()
    build_hash = calculate_folder_hash(build_path)
    if build_hash is None:
        logger.warning(f"Skipping {build_name} due to hash calculation failure")
        return
    current_time = datetime.now().strftime(DATETIME_FORMAT)
    c.execute(
        "INSERT OR REPLACE INTO builds (build_name, hash, created_at, mc_version, modloader) VALUES (?, ?, ?, ?, ?)",
        (build_name, build_hash, current_time, "Unknown", "Unknown"))
    logger.info(f"Updated build {build_name} in database with hash {build_hash}")


# Добавление тестовых данных и синхронизация сборок
def populate_test_data():
    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        c = conn.cursor()
        current_time = datetime.now().strftime(DATETIME_FORMAT)

        # Пользователи с UUID
        c.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?, ?)",
                  ("user1", "pass1", "2025-12-31", "Admin", str(uuid.uuid4())))
        c.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?, ?)",
                  ("user2", "pass2", "2025-01-01", "Player", str(uuid.uuid4())))

        # Сборки из папки server_builds
        for build_name in os.listdir(BUILDS_DIR):
            build_path = os.path.join(BUILDS_DIR, build_name)
            if os.path.isdir(build_path):
                update_build_in_db(build_name, build_path, conn)
                c.execute("INSERT OR IGNORE INTO user_builds VALUES (?, ?)", ("user1", build_name))

        # Тестовые сборки
        c.execute("INSERT OR IGNORE INTO builds VALUES (?, ?, ?, ?, ?)",
                  ("Server Build 1", "abc123", current_time, "1.20.1", "Forge"))
        c.execute("INSERT OR IGNORE INTO builds VALUES (?, ?, ?, ?, ?)",
                  ("Server Build 2", "def456", current_time, "1.19.2", "Fabric"))
        c.execute("INSERT OR IGNORE INTO user_builds VALUES (?, ?)", ("user1", "Server Build 1"))
        c.execute("INSERT OR IGNORE INTO user_builds VALUES (?, ?)", ("user1", "Server Build 2"))

        conn.commit()
        logger.info("Test data populated and builds synchronized successfully")


@app.route("/api/auth", methods=["POST"])
def auth():
    data = request.get_json()
    if not data or "action" not in data or data["action"] != "login":
        return jsonify({"error": "Invalid request format or action"}), 400

    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            c = conn.cursor()
            c.execute("SELECT password, license_expiry, role, uuid FROM users WHERE username = ?", (username,))
            result = c.fetchone()

            if not result or result[0] != password:
                return jsonify({"error": "Invalid credentials"}), 401

            stored_password, license_expiry, role, stored_uuid = result
            license_expiry_date = datetime.strptime(license_expiry, DATETIME_FORMAT)
            offline_mode = license_expiry_date < datetime.now()

            # Если UUID нет, генерируем новый и сохраняем
            if not stored_uuid:
                stored_uuid = str(uuid.uuid4())
                c.execute("UPDATE users SET uuid = ? WHERE username = ?", (stored_uuid, username))
                conn.commit()

            c.execute("""
                SELECT DISTINCT b.build_name, b.mc_version, b.modloader
                FROM user_builds ub
                JOIN builds b ON ub.build_name = b.build_name
                WHERE ub.username = ?
            """, (username,))
            builds = [{"name": row[0], "mc_version": row[1], "modloader": row[2]} for row in c.fetchall()]

            logger.info(
                f"User {username} authenticated successfully. UUID: {stored_uuid}, Available builds: {builds}, role: {role}")
            return jsonify({
                "status": "offline" if offline_mode else "success",
                "username": username,
                "uuid": stored_uuid,
                "builds": builds,
                "license_expiry": license_expiry,
                "role": role
            }), 200
    except sqlite3.Error as e:
        logger.error(f"Database error during auth: {str(e)}")
        return jsonify({"error": "Server database unavailable"}), 500


# Остальные маршруты остаются без изменений
@app.route("/api/check_build/<build_name>", methods=["GET"])
def check_build(build_name):
    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        c = conn.cursor()
        build_path = os.path.join(BUILDS_DIR, build_name)
        if os.path.exists(build_path):
            server_hash = calculate_folder_hash(build_path)
            c.execute("UPDATE builds SET hash = ? WHERE build_name = ?", (server_hash, build_name))
            conn.commit()
        else:
            c.execute("SELECT hash FROM builds WHERE build_name = ?", (build_name,))
            result = c.fetchone()
            if not result:
                return jsonify({"error": "Build not found"}), 404
            server_hash = result[0]
        return jsonify({"hash": server_hash}), 200


@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"error": "Логин и пароль обязательны"}), 400

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)",
                      (username, password, "2025-12-31", "Player", str(uuid.uuid4())))
            conn.commit()
            return jsonify({"status": "success"}), 201
        except sqlite3.IntegrityError:
            return jsonify({"error": "Логин занят"}), 409

@app.route("/api/download_build/<build_name>", methods=["GET"])
def download_build(build_name):
    build_path = os.path.join(BUILDS_DIR, build_name)
    if not os.path.exists(build_path):
        return jsonify({"error": "Build not found"}), 404
    archive_name = f"{build_name.replace(' ', '_')}.zip"
    archive_path = os.path.join(BUILDS_DIR, archive_name)
    if os.path.exists(archive_path):
        os.remove(archive_path)
    shutil.make_archive(archive_name.replace('.zip', ''), 'zip', build_path)
    return send_from_directory(BUILDS_DIR, archive_name, as_attachment=True)


if __name__ == "__main__":
    logger.info("Starting server initialization...")
    init_db()
    populate_test_data()
    logger.info("Server starting on 0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)