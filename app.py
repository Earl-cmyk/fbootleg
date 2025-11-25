from flask import Flask, request, render_template, redirect, url_for, g, jsonify
import sqlite3
import os
import uuid

app = Flask(__name__)
DATABASE = "feed.db"

# -------------------------
# SIMPLE NODE / STRUCTURES
# -------------------------
class Node:
    def __init__(self, data):
        self.node = data
        self.left = None
        self.right = None

class Stack:
    def __init__(self):
        self.head = None
        self.length = 0

    def push(self, data):
        n = Node(data)
        n.left = self.head
        self.head = n
        self.length += 1

    def to_list(self):
        items = []
        cur = self.head
        while cur:
            items.append(cur.node)
            cur = cur.left
        return items

class QueueLinked:
    """Linked-list based queue used only locally in some actions."""
    def __init__(self):
        self.head = None
        self.tail = None
        self.length = 0

    def enqueue(self, data):
        n = Node(data)
        if not self.head:
            self.head = n
            self.tail = n
        else:
            self.tail.right = n
            self.tail = n
        self.length += 1

    def dequeue(self):
        if self.length == 0:
            return None
        n = self.head
        self.head = self.head.right
        self.length -= 1
        return n.node

class BST:
    def __init__(self):
        self.root = None

    def insert(self, data):
        # data expected as string
        new = Node(data)
        if not self.root:
            self.root = new
            return

        cur = self.root
        while True:
            if data < cur.node:
                if cur.left:
                    cur = cur.left
                else:
                    cur.left = new
                    return
            else:
                if cur.right:
                    cur = cur.right
                else:
                    cur.right = new
                    return

    def dfs_search(self, word):
        if not word:
            return []
        results = []
        w = word.lower()

        def walk(node):
            if not node:
                return
            try:
                if w in node.node.lower():
                    results.append(node.node)
            except Exception:
                pass
            walk(node.left)
            walk(node.right)

        walk(self.root)
        return results

# -------------------------
# DATABASE HELPERS
# -------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db:
        db.close()

def init_db():
    if not os.path.exists(DATABASE):
        conn = sqlite3.connect(DATABASE)
        with open("schema.sql", "r") as f:
            conn.executescript(f.read())
        conn.commit()
        conn.close()

# -------------------------
# FEED / SEARCH LOGIC
# -------------------------
def get_feed_stack():
    db = get_db()
    rows = db.execute("SELECT * FROM posts ORDER BY id ASC").fetchall()
    stack = Stack()
    for r in rows:
        # convert sqlite Row to regular dict to avoid sqlite Row quirks in templates/JS
        stack.push({
            "id": r["id"],
            "title": r["title"],
            "caption": r["caption"],
            "author": r["author"],
            "post_type": r["post_type"],
            "up": r["up"],
            "down": r["down"],
        })
    # returns newest-first because stack pushes in DB order; reverse if you prefer newest-first
    return stack.to_list()

def perform_bst_search(keyword):
    posts = get_feed_stack()
    bst = BST()
    for post in posts:
        title = post.get("title", "") or ""
        bst.insert(title)
    return bst.dfs_search(keyword)

# -------------------------
# ROUTES
# -------------------------
@app.route("/", methods=["GET", "POST"])
def home():
    posts = get_feed_stack()

    if request.method == "POST":
        keyword = request.form.get("search", "") or ""
        dfs_results = perform_bst_search(keyword)

        db = get_db()
        sql_results = db.execute("""
            SELECT * FROM posts 
            WHERE title LIKE ? OR caption LIKE ?
        """, (f"%{keyword}%", f"%{keyword}%")).fetchall()

        return render_template("index.html",
                               posts=posts,
                               query=keyword,
                               dfs_results=dfs_results,
                               sql_results=[dict(r) for r in sql_results])

    return render_template("index.html", posts=posts)

@app.route("/lectures", methods=["GET", "POST"])
def lectures():
    if request.method == "POST":
        db = get_db()
        db.execute("""
            INSERT INTO posts(title, caption, author, post_type, up, down)
            VALUES (?, ?, ?, ?, 0, 0)
        """, (
            request.form.get("title"),
            request.form.get("caption"),
            request.form.get("author", "Anonymous"),
            request.form.get("post_type", "regular")
        ))
        db.commit()
        return redirect(url_for("lectures"))

    db_posts = get_feed_stack()

    interactive_posts = [
        {
            "id": -1,
            "title": "Queue Interactive Demo",
            "caption": "Real-time enqueue/dequeue visualization.",
            "up": 0,
            "down": 0
        },
        {
            "id": -2,
            "title": "Stack Interactive Demo",
            "caption": "Push/pop to see LIFO behavior.",
            "up": 0,
            "down": 0
        },
        {
            "id": -3,
            "title": "Tree Interactive Demo",
            "caption": "Add nodes to grow a general tree.",
            "up": 0,
            "down": 0
        },
        {
            "id": -4,
            "title": "Binary Tree Interactive Demo",
            "caption": "Insert left/right nodes manually.",
            "up": 0,
            "down": 0
        },
        {
            "id": -5,
            "title": "Binary Search Tree Interactive Demo",
            "caption": "Automatic BST insertion.",
            "up": 0,
            "down": 0
        }
    ]

    final_posts = interactive_posts + db_posts
    return render_template("lectures.html", posts=final_posts)

@app.route("/create_post", methods=["POST"])
def create_post():
    db = get_db()
    db.execute("""
        INSERT INTO posts(title, caption, author, post_type, up, down)
        VALUES (?, ?, ?, ?, 0, 0)
    """, (
        request.form.get("title"),
        request.form.get("caption"),
        request.form.get("author", "Anonymous"),
        request.form.get("post_type", "regular")
    ))
    db.commit()
    return redirect(url_for("lectures"))

@app.route("/vote/<int:id>/<string:way>")
def vote(id, way):
    db = get_db()
    if way == "up":
        db.execute("UPDATE posts SET up = up + 1 WHERE id=?", (id,))
    else:
        db.execute("UPDATE posts SET down = down + 1 WHERE id=?", (id,))
    db.commit()
    return redirect(url_for("lectures"))

@app.route("/delete/<int:id>")
def delete(id):
    # demonstrate queue-based delete: enqueue & dequeue then delete
    q = QueueLinked()
    q.enqueue(id)
    post_id = q.dequeue()
    if post_id is None:
        return redirect(url_for("lectures"))

    db = get_db()
    db.execute("DELETE FROM posts WHERE id=?", (post_id,))
    db.commit()
    return redirect(url_for("lectures"))

@app.route("/edit/<int:id>", methods=["POST"])
def edit(id):
    new_caption = request.form.get("new_caption", "") or ""
    db = get_db()
    db.execute("UPDATE posts SET caption=? WHERE id=?", (new_caption, id))
    db.commit()
    return redirect(url_for("lectures"))

@app.route("/collaborators")
def collaborators_page():
    return render_template("collaborators.html")

# ---------------------------
# IN-MEM DATA STRUCTURES FOR INTERACTIVES (simple JS APIs)
# ---------------------------
queue = []
stack = []

tree = {"root": None}
bt = {"root": None}
bst = {"root": None}

def new_id():
    return str(uuid.uuid4())

# QUEUE API
@app.post("/queue/enqueue")
def q_enqueue():
    value = request.json.get("value")
    queue.append(value)
    return jsonify(queue=queue)

@app.post("/queue/dequeue")
def q_dequeue():
    if queue:
        queue.pop(0)
    return jsonify(queue=queue)

# STACK API
@app.post("/stack/push")
def s_push():
    value = request.json.get("value")
    stack.append(value)
    return jsonify(stack=stack)

@app.post("/stack/pop")
def s_pop():
    if stack:
        stack.pop()
    return jsonify(stack=stack)

# GENERAL TREE API
@app.post("/tree/add_root")
def t_root():
    value = request.json.get("value")
    tree["root"] = {"id": new_id(), "value": value, "children": []}
    return jsonify(tree=tree["root"])

@app.post("/tree/add_child")
def t_child():
    target = request.json.get("target")
    value  = request.json.get("value")

    def add(node):
        if node["id"] == target:
            node["children"].append({"id": new_id(), "value": value, "children": []})
            return True
        for child in node["children"]:
            if add(child):
                return True
        return False

    if tree["root"]:
        add(tree["root"])

    return jsonify(tree=tree["root"])

# BINARY TREE API
@app.post("/bt/add_left")
def bt_left():
    parent = request.json.get("parent")
    value = request.json.get("value")

    def find(node):
        if not node: return None
        if node["id"] == parent: return node
        left = find(node.get("left"))
        if left: return left
        return find(node.get("right"))

    if not bt["root"]:
        bt["root"] = {"id": new_id(), "value": value, "left": None, "right": None}
    else:
        node = find(bt["root"])
        if node and node.get("left") is None:
            node["left"] = {"id": new_id(), "value": value, "left": None, "right": None}

    return jsonify(bt=bt["root"])

@app.post("/bt/add_right")
def bt_right():
    parent = request.json.get("parent")
    value = request.json.get("value")

    def find(node):
        if not node: return None
        if node["id"] == parent: return node
        left = find(node.get("left"))
        if left: return left
        return find(node.get("right"))

    if not bt["root"]:
        bt["root"] = {"id": new_id(), "value": value, "left": None, "right": None}
    else:
        node = find(bt["root"])
        if node and node.get("right") is None:
            node["right"] = {"id": new_id(), "value": value, "left": None, "right": None}

    return jsonify(bt=bt["root"])

@app.post("/bt/reset")
def bt_reset():
    bt["root"] = None
    return jsonify(status="reset")

# BST API
@app.post("/bst/insert")
def bst_insert():
    raw = request.json.get("value")
    try:
        value = int(raw)
    except Exception:
        # ignore invalid inserts
        return jsonify(error="value must be integer"), 400

    def insert(node, v):
        if not node:
            return {"value": v, "left": None, "right": None}
        if v < node["value"]:
            node["left"] = insert(node["left"], v)
        else:
            node["right"] = insert(node["right"], v)
        return node

    bst["root"] = insert(bst["root"], value)
    return jsonify(bst=bst["root"])

@app.post("/bst/reset")
def bst_reset():
    bst["root"] = None
    return jsonify(status="reset")

# RUN
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
