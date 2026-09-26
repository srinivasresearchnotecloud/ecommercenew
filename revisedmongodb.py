import streamlit as st
from pymongo import MongoClient
import datetime
import pandas as pd
import numpy as np
import requests
import json
import os

st.set_page_config(page_title="E-Commerce App", layout="wide")

# MongoDB Atlas credentials are read ONLY from Streamlit Secrets.
# Do not hard-code the MongoDB username/password in this source file.


# -------------------------
# SESSION STATE
# -------------------------
if "cart" not in st.session_state:
    st.session_state.cart = []
if "user" not in st.session_state:
    st.session_state.user = None
if "client_ip_checked" not in st.session_state:
    st.session_state.client_ip_checked = False
if "client_ip" not in st.session_state:
    st.session_state.client_ip = None
if "ml_model" not in st.session_state:
    st.session_state.ml_model = None

# -------------------------
# PRODUCT CATALOG
# -------------------------
PRODUCTS = [
    {
        "id": 1,
        "name": "Laptop",
        "price": 55000,
        "category": "Computers",
        "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/12424c6bdd48450d4060ba93bbb20a532cf46413/laptop1.jpg",
    },
    {
        "id": 2,
        "name": "iPhone 16",
        "price": 80000,
        "category": "Phones",
        "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/12424c6bdd48450d4060ba93bbb20a532cf46413/iphone16.jpg",
    },
    {
        "id": 3,
        "name": "Keyboard",
        "price": 1500,
        "category": "Accessories",
        "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/12424c6bdd48450d4060ba93bbb20a532cf46413/keyboard.jpg",
    },
    {
        "id": 4,
        "name": "Watch",
        "price": 7000,
        "category": "Wearables",
        "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/12424c6bdd48450d4060ba93bbb20a532cf46413/watch1.jpg",
    },
    {
        "id": 5,
        "name": "Headphone",
        "price": 2500,
        "category": "Audio",
        "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/12424c6bdd48450d4060ba93bbb20a532cf46413/headphone.jpg",
    },
]

# Optional: override image links from a local file if present
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


# -------------------------
# MONGODB HELPERS
# -------------------------
@st.cache_resource
def get_mongo_client():
    """Create and cache one MongoDB Atlas client per Streamlit process."""
    uri = st.secrets.get("MONGO_URI")
    if not uri:
        raise RuntimeError(
            "MONGO_URI is missing. Add it to Streamlit Cloud > Settings > Secrets."
        )

    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    # Force a connection check now so errors are reported clearly.
    client.admin.command("ping")
    return client


def get_mongo_db():
    db_name = st.secrets.get("MONGO_DB", "ecommerce_db")
    return get_mongo_client()[db_name]


def get_events_collection():
    return get_mongo_db()["events"]


def get_orders_collection():
    return get_mongo_db()["orders"]


def log_event(user, pid, pname, action, extra=None):
    """Save one event directly into MongoDB Atlas events collection."""
    event = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc),
        "user": str(user) if user is not None else "guest",
        "product_id": str(pid) if pid is not None else "-",
        "product_name": str(pname) if pname is not None else "-",
        "action": str(action),
        "extra": extra if isinstance(extra, dict) else {},
    }

    try:
        result = get_events_collection().insert_one(event)
        if result.inserted_id:
            return True
        st.error("MongoDB did not return an event ID.")
        return False
    except Exception as e:
        st.error(f"EVENT SAVE ERROR: {e}")
        return False


def load_events():
    """Load events from MongoDB into a pandas DataFrame."""
    try:
        docs = list(
            get_events_collection()
            .find({}, {"_id": 0})
            .sort("timestamp", -1)
            .limit(10000)
        )
        if not docs:
            return pd.DataFrame(
                columns=[
                    "timestamp", "user", "product_id",
                    "product_name", "action", "extra"
                ]
            )

        df = pd.DataFrame(docs)

        # MongoDB stores timestamp as a datetime; normalize for analytics.
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

        # Ensure the expected columns always exist.
        for col in ["user", "product_id", "product_name", "action", "extra"]:
            if col not in df.columns:
                df[col] = None

        return clean_df(df)

    except Exception as e:
        logs = st.session_state.get("_local_logs", [])
        if logs:
            return clean_df(pd.DataFrame(logs))

        st.session_state["_mongo_error"] = str(e)
        return pd.DataFrame(
            columns=[
                "timestamp", "user", "product_id",
                "product_name", "action", "extra"
            ]
        )


def save_order(user, name, address, items, geo=None):
    """Save a completed order into MongoDB orders collection."""
    order = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc),
        "user": str(user) if user is not None else "guest",
        "customer_name": str(name or "").strip(),
        "address": str(address or "").strip(),
        "items": items,
        "geo": geo if isinstance(geo, dict) else {},
        "total": sum(
            float(i.get("price", 0)) * int(i.get("qty", 0))
            for i in items
        ),
    }

    try:
        result = get_orders_collection().insert_one(order)
        if result.inserted_id:
            return str(result.inserted_id)
        st.error("MongoDB did not return an order ID.")
        return None
    except Exception as e:
        st.error(f"ORDER SAVE ERROR: {e}")
        return None


# -------------------------
# IP & GEO HELPERS
# -------------------------
def ensure_client_ip():
    """
    Inject JS one time to fetch client IP and reload with ?client_ip=...
    Then store that value into session_state.client_ip.
    """
    params = st.query_params

    # If IP already in query params, store and done
    if "client_ip" in params:
        value = params.get("client_ip")
        st.session_state.client_ip = value[0] if isinstance(value, list) else value
        st.session_state.client_ip_checked = True
        return

    # If we haven't tried injecting the script yet, do it once
    if not st.session_state.client_ip_checked:
        html = """
        <script>
        (async function(){
            try {
                let r = await fetch('https://api.ipify.org?format=json');
                let j = await r.json();
                let ip = j.ip;
                const qp = new URLSearchParams(window.location.search);
                if(!qp.get('client_ip')){
                    qp.set('client_ip', ip);
                    window.location.href = window.location.pathname + '?' + qp.toString();
                }
            } catch(e) {
                console.log('IP fetch failed', e);
            }
        })();
        </script>
        """
        st.components.v1.html(html, height=1)
        st.session_state.client_ip_checked = True


def get_geo(ip):
    """
    Lookup geo info for an IP using ipapi.co.
    Returns a dict with country, city, lat, lon, etc.
    """
    try:
        if not ip:
            return {}
        r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=5)
        if r.ok:
            return r.json()
    except Exception:
        pass
    return {"ip": ip} if ip else {}


# -------------------------
# LIGHTWEIGHT "ML" RECOMMENDER (toy)
# -------------------------
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
    df = load_events()

    if df.empty:
        return None
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


# -------------------------
# AUTH (simple)
# -------------------------
def login():
    st.header("Login")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        if u.strip():
            st.session_state.user = u.strip()
            st.success("Logged in")
        else:
            st.warning("Please enter a username.")


def signup():
    st.header("Signup")
    u = st.text_input("Create Username")
    p = st.text_input("Create Password", type="password")
    if st.button("Create Account"):
        if u.strip():
            st.session_state.user = u.strip()
            st.success("Account created")
        else:
            st.warning("Please enter a username.")


# -------------------------
# CART / PRODUCT FUNCTIONS
# -------------------------
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
    # Detailed logging: product added to cart
    log_event(
        user, p["id"], p["name"], "add_to_cart",
        {**geo, "quantity": int(qty)}
    )


def product_page():
    st.header("Products")

    search = st.text_input("Search")
    categories = sorted(list({p["category"] for p in PRODUCTS}))
    cat_sel = st.multiselect("Filter by Category", categories)
    sort = st.selectbox("Sort by", ["Default", "Price ↑", "Price ↓", "Name A-Z", "Name Z-A"])

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
            st.image(p["img"])
            st.write(p["name"], "₹", p["price"])
            qty = st.number_input(f"Qty_{p['id']}", min_value=1, value=1)

            if st.button(f"View {p['id']}"):
                # Detailed logging: product view
                user = st.session_state.user or "guest"
                ip = st.session_state.get("client_ip")
                geo = get_geo(ip) if ip else {}
                log_event(user, p["id"], p["name"], "view", geo)
                st.success("Product view logged")

            if st.button(f"Add {p['id']}"):
                add_to_cart(p, int(qty))
                st.success("Added to cart")


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
        st.info("Cart empty")
        return

    st.subheader("Customer Details")

    with st.form("checkout_form", clear_on_submit=False):
        name = st.text_input(
            "Your Name",
            placeholder="Enter your full name"
        )

        address = st.text_area(
            "Delivery Address",
            placeholder="Enter your complete delivery address",
            height=120
        )

        st.subheader("Order Summary")
        total = 0.0

        for item in st.session_state.cart:
            subtotal = float(item["price"]) * int(item["qty"])
            total += subtotal
            st.write(
                f"{item['name']} × {item['qty']} = ₹{subtotal:,.2f}"
            )

        st.write(f"### Total: ₹{total:,.2f}")

        place_order = st.form_submit_button(
            "Place Order",
            type="primary"
        )

    if not place_order:
        return

    if not name.strip():
        st.error("Please enter your name.")
        return

    if not address.strip():
        st.error("Please enter your delivery address.")
        return

    user = st.session_state.user or "guest"
    ip = st.session_state.get("client_ip")
    geo = get_geo(ip) if ip else {}

    items = [dict(item) for item in st.session_state.cart]

    # 1. Save the order first.
    order_id = save_order(
        user=user,
        name=name.strip(),
        address=address.strip(),
        items=items,
        geo=geo,
    )

    if not order_id:
        st.error("Order could not be saved to MongoDB.")
        return

    # 2. Save one order event for every purchased product.
    successful_events = 0
    failed_events = 0

    for item in items:
        event_saved = log_event(
            user=user,
            pid=item["id"],
            pname=item["name"],
            action="order",
            extra={
                **geo,
                "order_id": order_id,
                "quantity": int(item["qty"]),
                "price": float(item["price"]),
            },
        )

        if event_saved:
            successful_events += 1
        else:
            failed_events += 1

    st.success(f"Order placed successfully. Order ID: {order_id}")
    st.write(f"Customer: {name.strip()}")
    st.write(f"Delivery Address: {address.strip()}")

    if failed_events == 0:
        st.success(
            f"{successful_events} order event(s) saved to MongoDB events collection."
        )
        # Clear cart only after order and all order events were saved.
        st.session_state.cart = []
    else:
        st.warning(
            f"Order was saved, but {failed_events} event(s) failed. "
            "See the EVENT SAVE ERROR above."
        )


# -------------------------
# ADMIN PANEL
# -------------------------
def admin_panel():
    st.header("Admin")
    st.write("Total Products:", len(PRODUCTS))

    st.subheader("MongoDB Atlas Status")
    try:
        get_mongo_client().admin.command("ping")
        st.success("MongoDB Atlas connected successfully.")
        st.write("Database:", st.secrets.get("MONGO_DB", "ecommerce_db"))
        st.write("Events collection: events")
        st.write("Orders collection: orders")

        event_count = get_events_collection().count_documents({})
        order_count = get_orders_collection().count_documents({})

        c1, c2 = st.columns(2)
        c1.metric("Events in MongoDB", event_count)
        c2.metric("Orders in MongoDB", order_count)

        st.subheader("MongoDB Event Test")
        if st.button("Test Event Insert", key="test_event_insert"):
            ok = log_event(
                "TEST_USER",
                "TEST_PRODUCT",
                "TEST PRODUCT",
                "test_event",
                {"test": True}
            )
            if ok:
                st.success("Test event inserted into MongoDB events collection.")
            else:
                st.error("Test event insertion failed. Check EVENT SAVE ERROR above.")
    except Exception as e:
        st.error("MongoDB connection failed.")
        st.code(str(e))

    st.write("Use the Analytics tab to see detailed visitor & behavior reports.")


# -------------------------
# ANALYTICS DASHBOARD
# -------------------------
def analytics():
    st.header("Analytics Dashboard")

    # --- Load event data from MongoDB ---
    df = load_events()

    if st.session_state.get("_mongo_error"):
        st.warning(
            "MongoDB warning: " + st.session_state["_mongo_error"]
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
        st.metric("Total views (product)", int(len(views)))
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
        hourly = hourly_series.reindex(range(0, 24), fill_value=0).reset_index(name="views")
        hourly = hourly.rename(columns={"index": "hour"}) if "index" in hourly.columns else hourly
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
        country_counts = filtered["geo_country_name"].dropna().value_counts().reset_index()
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
        city_counts = filtered["geo_city"].dropna().value_counts().reset_index()
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
            st.write("Most viewed product:", most)
            st.write("Least viewed product:", least)
    else:
        st.write("No view events to compute most/least viewed products")


# -------------------------
# MAIN NAVIGATION MENU
# -------------------------
st.sidebar.title("Navigation")
choice = st.sidebar.radio("Go to", ["Home", "Products", "Cart", "Admin", "Analytics"])

# Make sure we try to capture IP early
ensure_client_ip()

# Precompute user + geo for this run
current_user = st.session_state.user or "guest"
current_ip = st.session_state.get("client_ip")
current_geo = get_geo(current_ip) if current_ip else {}

# Detailed page-level events as you requested (Option C)
if choice == "Home":
    log_event(current_user, "-", "-", "home_view", current_geo)
    st.header("Welcome to the E-Commerce App")

elif choice == "Products":
    log_event(current_user, "-", "-", "products_view", current_geo)
    product_page()

elif choice == "Cart":
    log_event(current_user, "-", "-", "cart_view", current_geo)
    show_cart()
    st.subheader("Checkout")
    checkout()

elif choice == "Admin":
    log_event(current_user, "-", "-", "admin_view", current_geo)
    admin_panel()

elif choice == "Analytics":
    log_event(current_user, "-", "-", "analytics_view", current_geo)
    analytics()

