import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import datetime
import pandas as pd
import numpy as np
import requests
import json
import os
from email.mime.text import MIMEText
import smtplib

st.set_page_config(page_title="E-Commerce App", layout="wide")

if "cart" not in st.session_state:
    st.session_state.cart = []
if "user" not in st.session_state:
    st.session_state.user = None
if "client_ip_checked" not in st.session_state:
    st.session_state.client_ip_checked = False
if "ml_model" not in st.session_state:
    st.session_state.ml_model = None

PRODUCTS = [
    {"id": 1, "name": "Laptop", "price": 55000, "category": "Computers",
     "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/12424c6bdd48450d4060ba93bbb20a532cf46413/laptop1.jpg"},
    {"id": 2, "name": "iPhone 16", "price": 80000, "category": "Phones",
     "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/12424c6bdd48450d4060ba93bbb20a532cf46413/iphone16.jpg"},
    {"id": 3, "name": "Keyboard", "price": 1500, "category": "Accessories",
     "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/12424c6bdd48450d4060ba93bbb20a532cf46413/keyboard.jpg"},
    {"id": 4, "name": "Watch", "price": 7000, "category": "Wearables",
     "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/12424c6bdd48450d4060ba93bbb20a532cf46413/watch1.jpg"},
    {"id": 5, "name": "Headphone", "price": 2500, "category": "Audio",
     "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/12424c6bdd48450d4060ba93bbb20a532cf46413/headphone.jpg"}
]

LOCAL_PATH = "/mnt/data/images link.txt"
if os.path.exists(LOCAL_PATH):
    with open(LOCAL_PATH, "r") as f:
        links = [l.strip() for l in f.readlines() if l.strip()]
    for i, link in enumerate(links):
        if i < len(PRODUCTS):
            PRODUCTS[i]["img"] = link

def get_sheet():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(st.secrets["sheets"]["sheet_id"])
    try:
        return sh.worksheet("views")
    except:
        sh.add_worksheet("views", rows="2000", cols="20")
        return sh.worksheet("views")

def log_event(user, pid, pname, action, extra=None):
    t = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    row = [t, user, pid, pname, action, json.dumps(extra or {})]
    try:
        get_sheet().append_row(row)
    except:
        st.session_state.setdefault("_local_logs", []).append(row)

def ensure_client_ip():
    if st.session_state.client_ip_checked:
        return
    params = st.experimental_get_query_params()
    if "client_ip" in params:
        st.session_state.client_ip = params["client_ip"][0]
        st.session_state.client_ip_checked = True
        return
    html = """
    <script>
    (async function(){
        let r = await fetch('https://api.ipify.org?format=json');
        let j = await r.json();
        let ip = j.ip;
        const qp = new URLSearchParams(window.location.search);
        if(!qp.get('client_ip')){
            qp.set('client_ip', ip);
            window.location.href = window.location.pathname + '?' + qp.toString();
        }
    })();
    </script>
    """
    st.components.v1.html(html, height=0)
    st.session_state.client_ip_checked = True

def get_geo(ip):
    try:
        if not ip:
            return {}
        r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=5)
        if r.ok:
            return r.json()
    except:
        pass
    return {"ip": ip} if ip else {}

def encode_texts(texts):
    vocab = {}
    encoded = []
    for t in texts:
        w = t.lower().split()
        row = []
        for word in w:
            if word not in vocab:
                vocab[word] = len(vocab)
            row.append(vocab[word])
        encoded.append(row)
    return encoded, vocab

def vectorize(encoded, size):
    X = np.zeros((len(encoded), size))
    for i, row in enumerate(encoded):
        for idx in row:
            X[i, idx] += 1
    return X

def train_lightweight_ml():
    try:
        rows = get_sheet().get_all_records()
    except:
        rows = st.session_state.get("_local_logs", [])

    if not rows:
        return None

    df = pd.DataFrame(rows)
    df = df[df["action"] == "view"]
    if df.empty:
        return None

    df["text"] = df["user"] + " " + df["product_name"]
    enc, vocab = encode_texts(df["text"].tolist())
    X = vectorize(enc, len(vocab))
    labels = df["product_name"].astype("category")
    y = labels.cat.codes
    C = labels.cat.categories

    if len(df) < 5:
        return None

    W = np.random.randn(X.shape[1])
    lr = 0.01

    for _ in range(200):
        y_pred = 1 / (1 + np.exp(-X.dot(W)))
        grad = X.T.dot(y_pred - (y / y.max()))
        W -= lr * grad

    return (W, vocab, C)

def recommend(user, model):
    if not model:
        return [p["name"] for p in PRODUCTS[:3]]
    W, vocab, classes = model
    if not user:
        user = "guest"
    words = user.lower().split()
    vec = np.zeros(len(vocab))
    for w in words:
        if w in vocab:
            vec[vocab[w]] += 1
    score = vec.dot(W)
    idx = np.argsort(-score)
    out = []
    for i in idx[:3]:
        if i < len(classes):
            out.append(classes[i])
    return out if out else [p["name"] for p in PRODUCTS[:3]]

def login():
    st.header("Login")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        st.session_state.user = u
        st.success("Logged in")

def signup():
    st.header("Signup")
    u = st.text_input("Create Username")
    p = st.text_input("Create Password", type="password")
    if st.button("Create Account"):
        st.session_state.user = u
        st.success("Account created")

def add_to_cart(p, qty):
    for item in st.session_state.cart:
        if item["id"] == p["id"]:
            item["qty"] += qty
            break
    else:
        st.session_state.cart.append({**p, "qty": qty})
    user = st.session_state.user or "guest"
    ip = st.session_state.get("client_ip")
    geo = get_geo(ip) if ip else {}
    log_event(user, p["id"], p["name"], "add_to_cart", geo)

def product_page():
    st.header("Products")
    search = st.text_input("Search")
    categories = sorted(list({p["category"] for p in PRODUCTS}))
    cat_sel = st.multiselect("Filter by Category", categories)
    sort = st.selectbox("Sort by", ["Default","Price ↑","Price ↓","Name A-Z","Name Z-A"])

    prods = PRODUCTS
    if search:
        q = search.lower()
        prods = [p for p in prods if q in p["name"].lower()]
    if cat_sel:
        prods = [p for p in prods if p["category"] in cat_sel]
    if sort == "Price ↑":
        prods = sorted(prods, key=lambda x: x["price"])
    elif sort == "Price ↓":
        prods = sorted(prods, key=lambda x: -x["price"])
    elif sort == "Name A-Z":
        prods = sorted(prods, key=lambda x: x["name"])
    elif sort == "Name Z-A":
        prods = sorted(prods, key=lambda x: x["name"], reverse=True)

    cols = st.columns(3)
    for i, p in enumerate(prods):
        with cols[i % 3]:
            st.image(p["img"], use_column_width=True)
            st.write(p["name"], "₹", p["price"])
            qty = st.number_input(f"Qty_{p['id']}", min_value=1, value=1)
            if st.button(f"View {p['id']}"):
                user = st.session_state.user or "guest"
                ip = st.session_state.get("client_ip")
                geo = get_geo(ip) if ip else {}
                log_event(user, p["id"], p["name"], "view", geo)
                st.success("Logged view")
            if st.button(f"Add {p['id']}"):
                add_to_cart(p, int(qty))
                st.success("Added")

def show_cart():
    st.header("Cart")
    if not st.session_state.cart:
        st.write("Empty cart")
        return
    df = pd.DataFrame(st.session_state.cart)
    df["subtotal"] = df["price"] * df["qty"]
    st.table(df)
    st.write("Total:", df["subtotal"].sum())

def checkout():
    st.header("Checkout")
    if not st.session_state.cart:
        st.write("Cart empty")
        return
    name = st.text_input("Your Name")
    address = st.text_area("Address")
    if st.button("Place Order"):
        user = st.session_state.user or "guest"
        ip = st.session_state.get("client_ip")
        geo = get_geo(ip) if ip else {}
        for item in st.session_state.cart:
            log_event(user, item["id"], item["name"], "order", geo)
        st.success("Order Placed")
        st.session_state.cart = []

def admin_panel():
    st.header("Admin")
    st.write("Total Products:", len(PRODUCTS))

def analytics():
    st.header("Analytics Dashboard")
    try:
        df = pd.DataFrame(get_sheet().get_all_records())
    except:
        df = pd.DataFrame(st.session_state.get("_local_logs", []),
            columns=["timestamp","user","product_id","product_name","action","extra"])

    if df.empty:
        st.write("No data yet")
        return

    st.subheader("Raw Data")
    st.dataframe(df)

    if st.button("Train ML"):
        model = train_lightweight_ml()
        st.session_state.ml_model = model
        st.success("Model trained")

    st.subheader("Recommendations")
    recs = recommend(st.session_state.user, st.session_state.ml_model)
    st.write(recs)

ensure_client_ip()

menu = ["Home","Products","Cart","Checkout","Login","Signup","Admin","Analytics"]
choice = st.sidebar.selectbox("Menu", menu)

if choice == "Home":
    user = st.session_state.user or "guest"
    ip = st.session_state.get("client_ip")
    geo = get_geo(ip) if ip else {}
    log_event(user, 0, "home", "visit", geo)
    st.title("E-Commerce App")

elif choice == "Products":
    product_page()

elif choice == "Cart":
    show_cart()

elif choice == "Checkout":
    checkout()

elif choice == "Login":
    login()

elif choice == "Signup":
    signup()

elif choice == "Admin":
    admin_panel()

elif choice == "Analytics":
    analytics()
