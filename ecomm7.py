import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import datetime
import pandas as pd
import requests
import os
import json
from collections import Counter
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression
import numpy as np
import smtplib
from email.mime.text import MIMEText

st.set_page_config(page_title="E-Commerce Full App", layout="wide")

if "cart" not in st.session_state:
    st.session_state.cart = []
if "user" not in st.session_state:
    st.session_state.user = None
if "client_ip_checked" not in st.session_state:
    st.session_state.client_ip_checked = False

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
     "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/12424c6bdd48450d4060ba93bbb20a532cf46413/headphone.jpg"},
]

LOCAL_IMAGE_LINKS_PATH = "/mnt/data/images link.txt"
if os.path.exists(LOCAL_IMAGE_LINKS_PATH):
    try:
        with open(LOCAL_IMAGE_LINKS_PATH, "r") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        for i, url in enumerate(lines):
            if i < len(PRODUCTS):
                PRODUCTS[i]["img"] = url
    except:
        pass

def get_sheet():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    client = gspread.authorize(creds)
    sh = client.open_by_key(st.secrets["sheets"]["sheet_id"])
    try:
        ws = sh.worksheet("views")
    except Exception:
        sh.add_worksheet(title="views", rows="2000", cols="20")
        ws = sh.worksheet("views")
    return ws

def log_event(user, pid, pname, action, extra=None):
    t = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    row = [t, user, pid, pname, action]
    if extra:
        row.append(json.dumps(extra))
    try:
        ws = get_sheet()
        ws.append_row(row)
    except Exception:
        key = f"{pid}_{action}"
        st.session_state.setdefault("_local_logs", []).append(row)

def ensure_client_ip():
    if st.session_state.client_ip_checked:
        return
    params = st.experimental_get_query_params()
    if "client_ip" in params and params["client_ip"]:
        st.session_state.client_ip = params["client_ip"][0]
        st.session_state.client_ip_checked = True
        return
    html = """
    <script>
    (async function() {
      try {
        let res = await fetch('https://api.ipify.org?format=json');
        let data = await res.json();
        const ip = data.ip;
        const qp = new URLSearchParams(window.location.search);
        if (!qp.get('client_ip')) {
          qp.set('client_ip', ip);
          window.location.href = window.location.pathname + '?' + qp.toString();
        }
      } catch(e) {
        console.log(e);
      }
    })();
    </script>
    """
    st.components.v1.html(html, height=0)
    st.session_state.client_ip_checked = True

def get_geo_for_ip(ip):
    try:
        r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=5)
        if r.status_code == 200:
            data = r.json()
            return {
                "ip": ip,
                "city": data.get("city"),
                "region": data.get("region"),
                "country": data.get("country_name"),
                "latitude": data.get("latitude"),
                "longitude": data.get("longitude"),
                "org": data.get("org"),
                "timezone": data.get("timezone")
            }
    except:
        pass
    return {"ip": ip}

def send_email_report(to_email, subject, html_body):
    try:
        cfg = st.secrets.get("email", {})
        smtp_host = cfg.get("smtp_host")
        smtp_port = int(cfg.get("smtp_port", 587))
        smtp_user = cfg.get("smtp_user")
        smtp_pass = cfg.get("smtp_pass")
        if not smtp_host or not smtp_user or not smtp_pass:
            st.error("Email not configured in secrets")
            return False
        msg = MIMEText(html_body, "html")
        msg["Subject"] = subject
        msg["From"] = smtp_user
        msg["To"] = to_email
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [to_email], msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False

def basic_recommender_for_user(username, topn=3):
    try:
        ws = get_sheet()
        rows = ws.get_all_records()
    except:
        rows = st.session_state.get("_local_logs", [])
    if not rows:
        return [p["name"] for p in PRODUCTS[:topn]]
    df = pd.DataFrame(rows, columns=["timestamp", "user", "product_id", "product_name", "action"][:5]) if isinstance(rows[0], list) else pd.DataFrame(rows)
    df = df[df["action"] == "view"]
    if username and username != "guest":
        user_views = df[df["user"] == username]
        if not user_views.empty:
            most_viewed = user_views["product_name"].value_counts().index.tolist()
            recs = most_viewed + df["product_name"].value_counts().index.tolist()
            seen = set()
            out = []
            for r in recs:
                if r not in seen:
                    seen.add(r)
                    out.append(r)
                if len(out) >= topn:
                    break
            return out
    pop = df["product_name"].value_counts().index.tolist()
    if not pop:
        return [p["name"] for p in PRODUCTS[:topn]]
    return pop[:topn]

def train_simple_ml():
    try:
        ws = get_sheet()
        rows = ws.get_all_records()
    except:
        rows = st.session_state.get("_local_logs", [])
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df = df[df["action"] == "view"]
    if df.empty:
        return None
    df["text"] = df["user"].astype(str) + " " + df["product_name"].astype(str)
    vec = CountVectorizer()
    X = vec.fit_transform(df["text"])
    y = df["product_name"].astype("category").cat.codes
    if X.shape[0] < 5:
        return None
    model = LogisticRegression(max_iter=200)
    try:
        model.fit(X, y)
        return (model, vec, df["product_name"].astype("category").cat.categories)
    except:
        return None

def login():
    st.header("Login")
    u = st.text_input("Username", key="login_user")
    p = st.text_input("Password", type="password", key="login_pass")
    if st.button("Login"):
        if u:
            st.session_state.user = u
            st.success("Logged in")

def signup():
    st.header("Signup")
    u = st.text_input("Create username", key="su_user")
    p = st.text_input("Create password", type="password", key="su_pass")
    if st.button("Create account"):
        if u:
            st.session_state.user = u
            st.success("Account created")

def add_to_cart(product, qty):
    exists = False
    for it in st.session_state.cart:
        if it["id"] == product["id"]:
            it["qty"] += qty
            exists = True
            break
    if not exists:
        st.session_state.cart.append({"id": product["id"], "name": product["name"], "price": product["price"], "qty": qty, "img": product["img"]})
    user = st.session_state.user if st.session_state.user else "guest"
    geo = {}
    if "client_ip" in st.session_state:
        geo = get_geo_for_ip(st.session_state.client_ip)
    log_event(user, product["id"], product["name"], "add_to_cart", extra=geo)

def product_page():
    st.header("Products")
    search = st.text_input("Search", key="search")
    cats = sorted(list({p["category"] for p in PRODUCTS}))
    selected = st.multiselect("Filter by category", options=cats, key="cats")
    sort = st.selectbox("Sort by", ["Default", "Price: Low to High", "Price: High to Low", "Name A-Z", "Name Z-A"], key="sort")
    filtered = PRODUCTS
    if search:
        q = search.lower()
        filtered = [p for p in filtered if q in p["name"].lower() or q in p.get("category","").lower()]
    if selected:
        filtered = [p for p in filtered if p["category"] in selected]
    if sort == "Price: Low to High":
        filtered = sorted(filtered, key=lambda x: x["price"])
    elif sort == "Price: High to Low":
        filtered = sorted(filtered, key=lambda x: -x["price"])
    elif sort == "Name A-Z":
        filtered = sorted(filtered, key=lambda x: x["name"])
    elif sort == "Name Z-A":
        filtered = sorted(filtered, key=lambda x: x["name"], reverse=True)
    cols = st.columns(3)
    for i, p in enumerate(filtered):
        with cols[i % 3]:
            st.image(p["img"], use_column_width=True)
            st.markdown(f"**{p['name']}**")
            st.write("Price:", p["price"])
            st.write("Category:", p["category"])
            qty = st.number_input(f"Qty_{p['id']}", min_value=1, value=1, key=f"qty_{p['id']}")
            if st.button(f"View {p['id']}", key=f"view_{p['id']}"):
                user = st.session_state.user if st.session_state.user else "guest"
                geo = {}
                if "client_ip" in st.session_state:
                    geo = get_geo_for_ip(st.session_state.client_ip)
                log_event(user, p["id"], p["name"], "view", extra=geo)
                st.success("View logged")
            if st.button(f"Add to Cart {p['id']}", key=f"add_{p['id']}"):
                add_to_cart(p, int(qty))
                st.success("Added to cart")

def show_cart():
    st.header("Cart")
    if not st.session_state.cart:
        st.write("Cart is empty")
        return
    df = pd.DataFrame(st.session_state.cart)
    df["subtotal"] = df["price"] * df["qty"]
    st.table(df[["name","price","qty","subtotal"]])
    st.markdown(f"**Total: ₹{df['subtotal'].sum()}**")
    if st.button("Clear cart"):
        st.session_state.cart = []
        st.experimental_rerun()

def checkout():
    st.header("Checkout")
    if not st.session_state.cart:
        st.write("Cart empty")
        return
    total = sum([i["price"] * i["qty"] for i in st.session_state.cart])
    st.write("Total amount:", total)
    name = st.text_input("Full name", value=st.session_state.user if st.session_state.user else "")
    address = st.text_area("Shipping address")
    if st.button("Place order"):
        user = st.session_state.user if st.session_state.user else "guest"
        geo = {}
        if "client_ip" in st.session_state:
            geo = get_geo_for_ip(st.session_state.client_ip)
        for item in st.session_state.cart:
            log_event(user, item["id"], item["name"], "order", extra=geo)
        st.success("Order placed (demo)")
        st.session_state.cart = []

def admin_panel():
    st.header("Admin")
    st.write("Products count:", len(PRODUCTS))
    st.write("Cart items:", sum([i["qty"] for i in st.session_state.cart]))
    if st.checkbox("Add new product"):
        name = st.text_input("Product name", key="np_name")
        price = st.number_input("Price", min_value=0.0, key="np_price")
        cat = st.text_input("Category", key="np_cat")
        img = st.text_input("Image URL", key="np_img")
        if st.button("Add product now"):
            new_id = max([p["id"] for p in PRODUCTS]) + 1
            PRODUCTS.append({"id": new_id, "name": name, "price": price, "category": cat or "Uncategorized", "img": img})
            st.success("Product added")
            st.experimental_rerun()

def analytics_dashboard():
    st.header("Analytics")
    try:
        ws = get_sheet()
        rows = ws.get_all_records()
        df = pd.DataFrame(rows)
    except Exception:
        logs = st.session_state.get("_local_logs", [])
        if logs:
            df = pd.DataFrame(logs, columns=["timestamp","user","product_id","product_name","action"])
        else:
            df = pd.DataFrame(columns=["timestamp","user","product_id","product_name","action"])
    if df.empty:
        st.write("No analytics yet")
        return
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    st.subheader("Recent events")
    st.dataframe(df.sort_values("timestamp", ascending=False).head(200))
    st.subheader("Aggregations")
    views = df[df["action"] == "view"].groupby("product_name").size().reset_index(name="views")
    adds = df[df["action"] == "add_to_cart"].groupby("product_name").size().reset_index(name="adds")
    orders = df[df["action"] == "order"].groupby("product_name").size().reset_index(name="orders")
    agg = views.merge(adds, on="product_name", how="outer").merge(orders, on="product_name", how="outer").fillna(0)
    st.dataframe(agg)
    st.subheader("Charts")
    if not views.empty:
        st.bar_chart(views.set_index("product_name")["views"])
    if not adds.empty:
        st.bar_chart(adds.set_index("product_name")["adds"])
    st.subheader("Geo distribution")
    geo_df = df.dropna(subset=["action"])
    if "extra" in df.columns:
        try:
            geo_series = df["extra"].dropna().apply(lambda x: json.loads(x) if isinstance(x,str) else x)
            geo_df = pd.json_normalize(geo_series)
            if "country" in geo_df.columns:
                country_counts = geo_df["country"].value_counts().reset_index()
                country_counts.columns = ["country","count"]
                st.dataframe(country_counts)
                st.bar_chart(country_counts.set_index("country")["count"])
        except:
            pass
    st.subheader("User-specific analytics")
    users = sorted(df["user"].unique().tolist())
    sel = st.selectbox("Select user", options=users)
    if sel:
        udf = df[df["user"] == sel]
        st.write("Events for user:", sel)
        st.dataframe(udf.sort_values("timestamp", ascending=False))
    st.subheader("Recommendations (basic)")
    recs = basic_recommender_for_user(st.session_state.user if st.session_state.user else "guest", topn=5)
    st.write(recs)
    st.subheader("Train simple ML (optional)")
    if st.button("Train ML model"):
        model_info = train_simple_ml()
        if model_info:
            st.success("Model trained (basic)")
        else:
            st.info("Not enough data to train model")
    st.subheader("Send weekly report (manual send now)")
    if st.text_input("Report recipient", key="report_recipient"):
        to = st.session_state.get("report_recipient")
    else:
        to = ""
    if st.button("Send report now"):
        try:
            html = "<h2>E-Commerce Analytics Report</h2>"
            html += "<h3>Aggregations</h3>"
            html += agg.to_html(index=False)
            success = send_email_report(to or (st.secrets.get("email",{}).get("notify_to") if st.secrets.get("email") else ""), "E-Commerce Report", html)
            if success:
                st.success("Report sent")
        except Exception as e:
            st.error(f"Failed to send report: {e}")

ensure_client_ip()
menu = ["Home","Products","Cart","Checkout","Login","Signup","Admin","Analytics"]
choice = st.sidebar.selectbox("Menu", menu)
if choice == "Home":
    if "client_ip" in st.experimental_get_query_params():
        st.session_state.client_ip = st.experimental_get_query_params().get("client_ip")[0]
    user = st.session_state.user if st.session_state.user else "guest"
    geo = {}
    if "client_ip" in st.session_state:
        geo = get_geo_for_ip(st.session_state.client_ip)
    log_event(user, 0, "home", "visit", extra=geo)
    st.title("E-Commerce App")
    st.write("Welcome to the demo store")
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
    analytics_dashboard()
