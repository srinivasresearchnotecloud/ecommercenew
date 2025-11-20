
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

def clean_df(df):
    """
    Utility to make any DataFrame safe for Streamlit/pyarrow:
    - converts column names to strings
    - removes duplicate columns
    """
    if df is None or df is pd.DataFrame() or getattr(df, "empty", False):
        return df
    df = df.copy()
    df.columns = [str(c) for c in df.columns]
    df = df.loc[:, ~pd.Index(df.columns).duplicated()]
    return df












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

    # --- Load data from Google Sheet or local session logs ---
    try:
        raw = get_sheet().get_all_records()
        df = pd.DataFrame(raw)
    except Exception:
        logs = st.session_state.get("_local_logs", [])
        if logs:
            df = pd.DataFrame(
                logs,
                columns=["timestamp", "user", "product_id", "product_name", "action", "extra"],
            )
        else:
            df = pd.DataFrame(
                columns=["timestamp", "user", "product_id", "product_name", "action", "extra"]
            )

    if df.empty:
        st.write("No data yet")
        return

    # Ensure timestamp column is datetime
    try:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    except Exception:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    # --- Parse geo/extra JSON into flat columns ---
    def parse_extra(x):
        if not x:
            return {}
        try:
            if isinstance(x, str):
                return json.loads(x)
            if isinstance(x, dict):
                return x
        except Exception:
            return {}
        return {}

    extra_parsed = df["extra"].apply(parse_extra)
    extra_df = pd.json_normalize(extra_parsed).add_prefix("geo_")

    analytics_df = pd.concat([df.drop(columns=["extra"]), extra_df], axis=1)
    analytics_df = clean_df(analytics_df)

    # --- Raw event log preview ---
    st.subheader("Raw event logs (latest 500)")
    st.dataframe(analytics_df.sort_values("timestamp", ascending=False).head(500))

    # --- Filters ---
    st.subheader("Filters")
    with st.expander("Filter events"):
        col1, col2, col3 = st.columns(3)
        with col1:
            actions = sorted(analytics_df["action"].dropna().unique().tolist())
            sel_actions = st.multiselect("Action", options=actions, default=actions)
        with col2:
            prod_names = sorted(analytics_df["product_name"].dropna().unique().tolist())
            sel_products = st.multiselect("Product", options=prod_names, default=prod_names)
        with col3:
            users = sorted(analytics_df["user"].dropna().unique().tolist())
            sel_users = st.multiselect("User", options=users, default=users)

        date_col1, date_col2 = st.columns(2)
        with date_col1:
            if analytics_df["timestamp"].notna().any():
                min_date = analytics_df["timestamp"].min().date()
                max_date = analytics_df["timestamp"].max().date()
            else:
                today = datetime.date.today()
                min_date = max_date = today
            start_date = st.date_input(
                "Start date",
                min_value=min_date,
                max_value=max_date,
                value=min_date,
            )
        with date_col2:
            end_date = st.date_input(
                "End date",
                min_value=min_date,
                max_value=max_date,
                value=max_date,
            )

    mask = (
        analytics_df["action"].isin(sel_actions)
        & analytics_df["product_name"].isin(sel_products)
        & analytics_df["user"].isin(sel_users)
        & (analytics_df["timestamp"].dt.date >= start_date)
        & (analytics_df["timestamp"].dt.date <= end_date)
    )
    filtered = analytics_df[mask].copy()
    filtered = clean_df(filtered)

    if filtered.empty:
        st.info("No events for the selected filters.")
        return

    # Convenience subsets
    views = filtered[filtered["action"] == "view"].copy()
    adds = filtered[filtered["action"] == "add_to_cart"].copy()
    orders = filtered[filtered["action"] == "order"].copy()

    # --- KPI Cards ---
    st.subheader("Key metrics")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric("Total events", len(filtered))
    with kpi2:
        st.metric("Unique users", int(filtered["user"].nunique()))
    with kpi3:
        st.metric("Total views", int(len(views)))
    with kpi4:
        st.metric("Total orders", int(len(orders)))

    # --- Summary counts by action ---
    st.subheader("Summary counts by action")
    action_counts = (
        filtered.groupby("action")
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    action_counts = clean_df(action_counts)
    st.dataframe(action_counts)

    # --- Clicks by product (views only) ---
    st.subheader("Clicks by product (views only)")
    if not views.empty:
        clicks_by_product = (
            views.groupby("product_name")
            .size()
            .reset_index(name="views")
            .sort_values("views", ascending=False)
        )
        clicks_by_product = clean_df(clicks_by_product)
        st.bar_chart(clicks_by_product.set_index("product_name")["views"])
        st.dataframe(clicks_by_product)
    else:
        st.write("No view events in selected filter")

    # --- Add-to-cart by product ---
    st.subheader("Add-to-cart by product")
    if not adds.empty:
        adds_by_product = (
            adds.groupby("product_name")
            .size()
            .reset_index(name="adds")
            .sort_values("adds", ascending=False)
        )
        adds_by_product = clean_df(adds_by_product)
        st.bar_chart(adds_by_product.set_index("product_name")["adds"])
        st.dataframe(adds_by_product)
    else:
        st.write("No add_to_cart events in selected filter")

    # --- Orders by product ---
    st.subheader("Orders by product")
    if not orders.empty:
        orders_by_product = (
            orders.groupby("product_name")
            .size()
            .reset_index(name="orders")
            .sort_values("orders", ascending=False)
        )
        orders_by_product = clean_df(orders_by_product)
        st.bar_chart(orders_by_product.set_index("product_name")["orders"])
        st.dataframe(orders_by_product)
    else:
        st.write("No order events in selected filter")

    # --- Hourly trend (views) ---
    st.subheader("Hourly trend (views)")
    if not views.empty:
        views["hour"] = views["timestamp"].dt.hour
        hourly_series = views.groupby("hour").size()
        hourly = (
            hourly_series
            .reindex(range(0, 24), fill_value=0)
            .reset_index(name="views")
        )
        hourly = clean_df(hourly)
        st.line_chart(hourly.set_index("hour")["views"])
        st.dataframe(hourly)
    else:
        st.write("No view events for hourly trend")

    # --- Daily trend (views) ---
    st.subheader("Daily trend (views)")
    if not views.empty:
        views["date"] = views["timestamp"].dt.date
        daily = (
            views.groupby("date")
            .size()
            .reset_index(name="views")
            .sort_values("date")
        )
        daily = clean_df(daily)
        st.line_chart(daily.set_index("date")["views"])
        st.dataframe(daily)
    else:
        st.write("No view events for daily trend")

    # --- Top users by events ---
    st.subheader("Top users by events")
    top_users = (
        filtered.groupby("user")
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    top_users = clean_df(top_users)
    st.dataframe(top_users)
    st.bar_chart(top_users.set_index("user")["count"])

    # --- Geo distribution (country) ---
    st.subheader("Geo distribution (country)")
    if "geo_country_name" in analytics_df.columns:
        country_counts = (
            filtered["geo_country_name"]
            .dropna()
            .value_counts()
            .reset_index()
        )
        country_counts.columns = ["country", "count"]
        country_counts = clean_df(country_counts)
        if not country_counts.empty:
            st.dataframe(country_counts)
            st.bar_chart(country_counts.set_index("country")["count"])
        else:
            st.write("No geo country data in filter")
    else:
        st.write("No geo country data available")

    # --- Clicks by city ---
    st.subheader("Clicks by city")
    if "geo_city" in analytics_df.columns:
        city_counts = (
            filtered["geo_city"]
            .dropna()
            .value_counts()
            .reset_index()
        )
        city_counts.columns = ["city", "count"]
        city_counts = clean_df(city_counts)
        if not city_counts.empty:
            st.dataframe(city_counts)
            st.bar_chart(city_counts.set_index("city")["count"])
        else:
            st.write("No city data in filter")
    else:
        st.write("No city data available")

    # --- Product vs City heatmap (pivot) ---
    st.subheader("Product vs City heatmap (pivot)")
    if "geo_city" in analytics_df.columns:
        pivot = filtered.pivot_table(
            index="product_name",
            columns="geo_city",
            values="action",
            aggfunc="count",
            fill_value=0,
        )
        pivot = clean_df(pivot)
        if not pivot.empty:
            st.dataframe(pivot)
        else:
            st.write("No pivot data for selected filter")
    else:
        st.write("City information not available for heatmap")

    # --- Map of visitor locations ---
    st.subheader("Map of visitor locations (if latitude/longitude present)")
    if "geo_latitude" in analytics_df.columns and "geo_longitude" in analytics_df.columns:
        map_df = filtered.dropna(subset=["geo_latitude", "geo_longitude"]).copy()
        try:
            map_plot = map_df[["geo_latitude", "geo_longitude"]].rename(
                columns={"geo_latitude": "lat", "geo_longitude": "lon"}
            )
            map_plot = clean_df(map_plot)
            if not map_plot.empty:
                st.map(map_plot)
            else:
                st.write("No geo coordinates in filtered data")
        except Exception:
            st.write("Unable to render map for the provided coordinates")
    else:
        st.write("Latitude/Longitude not available in data")

    # --- Export filtered events ---
    st.subheader("Export filtered events")
    csv = filtered.to_csv(index=False)
    st.download_button(
        "Download CSV of filtered events",
        csv,
        file_name="analytics_filtered.csv",
        mime="text/csv",
    )

    # --- Most / Least viewed products ---
    st.subheader("Most / Least viewed products")
    if not views.empty:
        clicks_by_product = (
            views.groupby("product_name")
            .size()
            .reset_index(name="views")
            .sort_values("views", ascending=False)
        )
        if not clicks_by_product.empty:
            most = clicks_by_product.iloc[0]["product_name"]
            least = clicks_by_product.iloc[-1]["product_name"]
            st.write("Most viewed:", most)
            st.write("Least viewed:", least)
    else:
        st.write("No view events to compute most/least viewed products")


    return

elif choice == "Analytics":
