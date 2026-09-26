import streamlit as st
from pymongo import MongoClient
from pymongo.errors import PyMongoError
import datetime
import pandas as pd
import numpy as np
import requests
import json
import os


# ============================================================
# STREAMLIT CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="E-Commerce App",
    layout="wide"
)


# ============================================================
# SESSION STATE
# ============================================================

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


# ============================================================
# PRODUCT CATALOG
# ============================================================

PRODUCTS = [
    {
        "id": 1,
        "name": "Laptop",
        "price": 55000,
        "category": "Computers",
        "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/main/laptop1.jpg",
    },
    {
        "id": 2,
        "name": "iPhone 16",
        "price": 80000,
        "category": "Phones",
        "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/main/iphone16.jpg",
    },
    {
        "id": 3,
        "name": "Keyboard",
        "price": 1500,
        "category": "Accessories",
        "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/main/keyboard.jpg",
    },
    {
        "id": 4,
        "name": "Watch",
        "price": 7000,
        "category": "Wearables",
        "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/main/watch1.jpg",
    },
    {
        "id": 5,
        "name": "Headphone",
        "price": 2500,
        "category": "Audio",
        "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/main/headphone.jpg",
    },
]


# ============================================================
# OPTIONAL LOCAL IMAGE LINK OVERRIDE
# ============================================================

LOCAL_PATH = "/mnt/data/images link.txt"

if os.path.exists(LOCAL_PATH):

    try:
        with open(LOCAL_PATH, "r", encoding="utf-8") as f:
            links = [
                line.strip()
                for line in f.readlines()
                if line.strip()
            ]

        for i, link in enumerate(links):
            if i < len(PRODUCTS):
                PRODUCTS[i]["img"] = link

    except Exception:
        pass


# ============================================================
# DATAFRAME CLEANING
# ============================================================

def clean_df(df):

    if df is None:
        return df

    if getattr(df, "empty", False):
        return df

    df = df.copy()

    df.columns = [str(c) for c in df.columns]

    df = df.loc[
        :,
        ~pd.Index(df.columns).duplicated()
    ]

    return df


# ============================================================
# MONGODB CONNECTION
# ============================================================

@st.cache_resource
def get_mongo_client():

    uri = st.secrets.get("MONGO_URI")

    if not uri:
        raise RuntimeError(
            "MONGO_URI is missing. "
            "Go to Streamlit Cloud > Settings > Secrets "
            "and add MONGO_URI."
        )

    client = MongoClient(
        uri,
        serverSelectionTimeoutMS=10000,
        connectTimeoutMS=10000,
        socketTimeoutMS=10000,
        tls=True
    )

    # Force connection test
    client.admin.command("ping")

    return client


def get_mongo_db():

    db_name = st.secrets.get(
        "MONGO_DB",
        "ecommerce_db"
    )

    return get_mongo_client()[db_name]


def get_events_collection():

    return get_mongo_db()["events"]


def get_orders_collection():

    return get_mongo_db()["orders"]


# ============================================================
# EVENT LOGGING
# ============================================================

def log_event(
    user,
    pid,
    pname,
    action,
    extra=None
):

    """
    Store an event directly in MongoDB Atlas.

    Every event contains:
    timestamp
    user
    product_id
    product_name
    action
    extra
    """

    event = {
        "timestamp": datetime.datetime.now(
            datetime.timezone.utc
        ),
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

        st.error(
            "MongoDB did not return an event ID."
        )

        return False

    except PyMongoError as e:

        st.error(
            f"Event logging failed: {e}"
        )

        return False

    except Exception as e:

        st.error(
            f"Unexpected event logging error: {e}"
        )

        return False


# ============================================================
# LOAD EVENTS
# ============================================================

def load_events():

    try:

        docs = list(
            get_events_collection()
            .find(
                {},
                {"_id": 0}
            )
            .sort(
                "timestamp",
                -1
            )
            .limit(10000)
        )

        if not docs:

            return pd.DataFrame(
                columns=[
                    "timestamp",
                    "user",
                    "product_id",
                    "product_name",
                    "action",
                    "extra"
                ]
            )

        df = pd.DataFrame(docs)

        if "timestamp" in df.columns:

            df["timestamp"] = pd.to_datetime(
                df["timestamp"],
                errors="coerce"
            )

        expected_columns = [
            "timestamp",
            "user",
            "product_id",
            "product_name",
            "action",
            "extra"
        ]

        for col in expected_columns:

            if col not in df.columns:
                df[col] = None

        return clean_df(df)

    except Exception as e:

        st.error(
            f"Unable to load events from MongoDB: {e}"
        )

        return pd.DataFrame(
            columns=[
                "timestamp",
                "user",
                "product_id",
                "product_name",
                "action",
                "extra"
            ]
        )


# ============================================================
# SAVE ORDER
# ============================================================

def save_order(
    user,
    name,
    address,
    items,
    geo=None
):

    """
    Saves the completed order into MongoDB.

    Returns:
        inserted order ID as string
        or None if unsuccessful
    """

    order = {
        "timestamp": datetime.datetime.now(
            datetime.timezone.utc
        ),
        "user": str(user) if user is not None else "guest",
        "customer_name": str(name or ""),
        "address": str(address or ""),
        "items": items,
        "geo": geo if isinstance(geo, dict) else {},
        "total": sum(
            float(item.get("price", 0))
            * int(item.get("qty", 0))
            for item in items
        )
    }

    try:

        result = get_orders_collection().insert_one(
            order
        )

        if result.inserted_id:

            return str(result.inserted_id)

        return None

    except PyMongoError as e:

        st.error(
            f"Order could not be saved: {e}"
        )

        return None

    except Exception as e:

        st.error(
            f"Unexpected order error: {e}"
        )

        return None


# ============================================================
# SAVE ORDER + ORDER EVENTS
# ============================================================

def save_order_with_events(
    user,
    name,
    address,
    items,
    geo=None
):

    """
    Save the order and corresponding order events.

    The order is saved first.
    Then one event is created for every purchased product.

    Returns:
        order_id, True
        or
        None, False
    """

    geo = geo if isinstance(geo, dict) else {}

    order = {
        "timestamp": datetime.datetime.now(
            datetime.timezone.utc
        ),
        "user": str(user) if user is not None else "guest",
        "customer_name": str(name or ""),
        "address": str(address or ""),
        "items": items,
        "geo": geo,
        "total": sum(
            float(item.get("price", 0))
            * int(item.get("qty", 0))
            for item in items
        )
    }

    try:

        client = get_mongo_client()
        db = get_mongo_db()

        orders_collection = db["orders"]
        events_collection = db["events"]

        # ----------------------------------------------------
        # START TRANSACTION
        # ----------------------------------------------------

        with client.start_session() as session:

            with session.start_transaction():

                # Save order
                order_result = orders_collection.insert_one(
                    order,
                    session=session
                )

                order_id = str(
                    order_result.inserted_id
                )

                # ------------------------------------------------
                # CREATE ORDER EVENT FOR EVERY PRODUCT
                # ------------------------------------------------

                for item in items:

                    event = {
                        "timestamp": datetime.datetime.now(
                            datetime.timezone.utc
                        ),

                        "user": str(user)
                        if user is not None
                        else "guest",

                        "product_id": str(
                            item.get("id", "-")
                        ),

                        "product_name": str(
                            item.get("name", "-")
                        ),

                        "action": "order",

                        "extra": {
                            **geo,
                            "order_id": order_id,
                            "quantity": int(
                                item.get("qty", 0)
                            ),
                            "price": float(
                                item.get("price", 0)
                            ),
                        }
                    }

                    events_collection.insert_one(
                        event,
                        session=session
                    )

        return order_id, True

    except PyMongoError as e:

        st.error(
            f"Order/event transaction failed: {e}"
        )

        return None, False

    except Exception as e:

        st.error(
            f"Unexpected order/event error: {e}"
        )

        return None, False


# ============================================================
# IP ADDRESS
# ============================================================

def ensure_client_ip():

    try:

        params = st.query_params

        if "client_ip" in params:

            value = params.get(
                "client_ip"
            )

            if isinstance(value, list):

                value = value[0]

            st.session_state.client_ip = value

            st.session_state.client_ip_checked = True

            return

        if not st.session_state.client_ip_checked:

            html = """
            <script>
            (async function(){

                try {

                    let r = await fetch(
                        'https://api.ipify.org?format=json'
                    );

                    let j = await r.json();

                    let ip = j.ip;

                    const qp =
                        new URLSearchParams(
                            window.location.search
                        );

                    if(!qp.get('client_ip')){

                        qp.set(
                            'client_ip',
                            ip
                        );

                        window.location.href =
                            window.location.pathname
                            + '?'
                            + qp.toString();
                    }

                } catch(e) {

                    console.log(
                        'IP fetch failed',
                        e
                    );

                }

            })();
            </script>
            """

            st.components.v1.html(
                html,
                height=1
            )

            st.session_state.client_ip_checked = True

    except Exception:
        pass


# ============================================================
# GEO INFORMATION
# ============================================================

def get_geo(ip):

    if not ip:
        return {}

    try:

        response = requests.get(
            f"https://ipapi.co/{ip}/json/",
            timeout=5
        )

        if response.ok:

            data = response.json()

            # Keep only useful/simple values
            return {
                "ip": data.get("ip"),
                "city": data.get("city"),
                "region": data.get("region"),
                "country_name": data.get(
                    "country_name"
                ),
                "country_code": data.get(
                    "country_code"
                ),
                "latitude": data.get(
                    "latitude"
                ),
                "longitude": data.get(
                    "longitude"
                ),
                "org": data.get("org")
            }

    except Exception:
        pass

    return {
        "ip": ip
    }


# ============================================================
# LIGHTWEIGHT ML RECOMMENDER
# ============================================================

def encode_texts(texts):

    vocab = {}
    encoded = []

    for text_value in texts:

        words = str(
            text_value
        ).lower().split()

        row = []

        for word in words:

            if word not in vocab:

                vocab[word] = len(vocab)

            row.append(
                vocab[word]
            )

        encoded.append(row)

    return encoded, vocab


def vectorize(encoded, size):

    X = np.zeros(
        (
            len(encoded),
            size
        )
    )

    for i, row in enumerate(encoded):

        for idx in row:

            X[i, idx] += 1

    return X


def train_lightweight_ml():

    df = load_events()

    if df.empty:
        return None

    df = df[
        df["action"] == "view"
    ].copy()

    if df.empty:
        return None

    df["text"] = (
        df["user"].astype(str)
        + " "
        + df["product_name"].astype(str)
    )

    encoded, vocab = encode_texts(
        df["text"].tolist()
    )

    X = vectorize(
        encoded,
        len(vocab)
    )

    labels = df[
        "product_name"
    ].astype("category")

    y = labels.cat.codes

    categories = labels.cat.categories

    if len(df) < 5:
        return None

    W = np.random.randn(
        X.shape[1]
    )

    learning_rate = 0.01

    for _ in range(200):

        y_pred = 1 / (
            1 + np.exp(
                -X.dot(W)
            )
        )

        if y.max() == 0:
            break

        grad = X.T.dot(
            y_pred
            - (
                y / y.max()
            )
        )

        W -= (
            learning_rate
            * grad
        )

    return (
        W,
        vocab,
        categories
    )


def recommend(user, model):

    if not model:

        return [
            p["name"]
            for p in PRODUCTS[:3]
        ]

    W, vocab, classes = model

    if not user:
        user = "guest"

    words = user.lower().split()

    vec = np.zeros(
        len(vocab)
    )

    for word in words:

        if word in vocab:

            vec[
                vocab[word]
            ] += 1

    score = vec.dot(W)

    idx = np.argsort(
        -score
    )

    output = []

    for i in idx[:3]:

        if i < len(classes):

            output.append(
                classes[i]
            )

    if output:

        return output

    return [
        p["name"]
        for p in PRODUCTS[:3]
    ]


# ============================================================
# LOGIN
# ============================================================

def login():

    st.header("Login")

    username = st.text_input(
        "Username"
    )

    password = st.text_input(
        "Password",
        type="password"
    )

    if st.button("Login"):

        if username.strip():

            st.session_state.user = (
                username.strip()
            )

            st.success(
                "Logged in successfully."
            )

        else:

            st.warning(
                "Please enter a username."
            )


# ============================================================
# SIGNUP
# ============================================================

def signup():

    st.header("Signup")

    username = st.text_input(
        "Create Username"
    )

    password = st.text_input(
        "Create Password",
        type="password"
    )

    if st.button("Create Account"):

        if username.strip():

            st.session_state.user = (
                username.strip()
            )

            st.success(
                "Account created successfully."
            )

        else:

            st.warning(
                "Please enter a username."
            )


# ============================================================
# ADD TO CART
# ============================================================

def add_to_cart(
    product,
    qty
):

    qty = int(qty)

    found = False

    for item in st.session_state.cart:

        if item["id"] == product["id"]:

            item["qty"] += qty

            found = True

            break

    if not found:

        st.session_state.cart.append(
            {
                **product,
                "qty": qty
            }
        )

    user = (
        st.session_state.user
        or "guest"
    )

    ip = st.session_state.get(
        "client_ip"
    )

    geo = (
        get_geo(ip)
        if ip
        else {}
    )

    success = log_event(
        user=user,
        pid=product["id"],
        pname=product["name"],
        action="add_to_cart",
        extra={
            **geo,
            "quantity": qty
        }
    )

    if not success:

        st.warning(
            "Product was added to cart, "
            "but the event could not be saved."
        )


# ============================================================
# PRODUCT PAGE
# ============================================================

def product_page():

    st.header("Products")

    search = st.text_input(
        "Search"
    )

    categories = sorted(
        list(
            {
                p["category"]
                for p in PRODUCTS
            }
        )
    )

    cat_sel = st.multiselect(
        "Filter by Category",
        categories
    )

    sort = st.selectbox(
        "Sort by",
        [
            "Default",
            "Price ↑",
            "Price ↓",
            "Name A-Z",
            "Name Z-A"
        ]
    )

    prods = PRODUCTS.copy()

    # Search
    if search:

        q = search.lower()

        prods = [
            p
            for p in prods
            if q in p["name"].lower()
        ]

    # Category
    if cat_sel:

        prods = [
            p
            for p in prods
            if p["category"]
            in cat_sel
        ]

    # Sorting
    if sort == "Price ↑":

        prods = sorted(
            prods,
            key=lambda x: x["price"]
        )

    elif sort == "Price ↓":

        prods = sorted(
            prods,
            key=lambda x: -x["price"]
        )

    elif sort == "Name A-Z":

        prods = sorted(
            prods,
            key=lambda x: x["name"]
        )

    elif sort == "Name Z-A":

        prods = sorted(
            prods,
            key=lambda x: x["name"],
            reverse=True
        )

    cols = st.columns(3)

    for i, product in enumerate(prods):

        with cols[i % 3]:

            st.image(
                product["img"]
            )

            st.write(
                product["name"],
                "₹",
                product["price"]
            )

            qty = st.number_input(
                f"Qty_{product['id']}",
                min_value=1,
                value=1,
                step=1
            )

            # ---------------------------------------------
            # VIEW BUTTON
            # ---------------------------------------------

            if st.button(
                f"View {product['id']}",
                key=f"view_{product['id']}"
            ):

                user = (
                    st.session_state.user
                    or "guest"
                )

                ip = st.session_state.get(
                    "client_ip"
                )

                geo = (
                    get_geo(ip)
                    if ip
                    else {}
                )

                success = log_event(
                    user=user,
                    pid=product["id"],
                    pname=product["name"],
                    action="view",
                    extra=geo
                )

                if success:

                    st.success(
                        "Product view logged in MongoDB."
                    )

            # ---------------------------------------------
            # ADD BUTTON
            # ---------------------------------------------

            if st.button(
                f"Add {product['id']}",
                key=f"add_{product['id']}"
            ):

                add_to_cart(
                    product,
                    int(qty)
                )

                st.success(
                    f"{product['name']} added to cart."
                )


# ============================================================
# SHOW CART
# ============================================================

def show_cart():

    st.header("Cart")

    if not st.session_state.cart:

        st.info(
            "Your cart is empty."
        )

        return

    cart_df = pd.DataFrame(
        st.session_state.cart
    )

    cart_df["subtotal"] = (
        cart_df["price"]
        * cart_df["qty"]
    )

    st.dataframe(
        cart_df,
        use_container_width=True
    )

    total = cart_df[
        "subtotal"
    ].sum()

    st.subheader(
        f"Total: ₹{total:,.2f}"
    )


# ============================================================
# CHECKOUT
# ============================================================

def checkout():

    st.header("Checkout")

    if not st.session_state.cart:

        st.info(
            "Cart is empty."
        )

        return

    name = st.text_input(
        "Your Name"
    )

    address = st.text_area(
        "Address"
    )

    st.subheader("Order Summary")

    for item in st.session_state.cart:

        st.write(
            f"**{item['name']}** "
            f"× {item['qty']} "
            f"= ₹{item['price'] * item['qty']:,.2f}"
        )

    total = sum(
        item["price"]
        * item["qty"]
        for item in st.session_state.cart
    )

    st.write(
        f"### Total: ₹{total:,.2f}"
    )

    if st.button(
        "Place Order",
        type="primary"
    ):

        user = (
            st.session_state.user
            or "guest"
        )

        ip = st.session_state.get(
            "client_ip"
        )

        geo = (
            get_geo(ip)
            if ip
            else {}
        )

        # Make a copy of cart
        items = [
            dict(item)
            for item in st.session_state.cart
        ]

        # ------------------------------------------------
        # SAVE ORDER + EVENTS
        # ------------------------------------------------

        order_id, success = (
            save_order_with_events(
                user=user,
                name=name,
                address=address,
                items=items,
                geo=geo
            )
        )

        if success:

            st.success(
                f"Order placed successfully!"
            )

            st.success(
                f"Order ID: {order_id}"
            )

            st.info(
                "Order and order events "
                "have been saved to MongoDB."
            )

            # Clear cart
            st.session_state.cart = []

        else:

            st.error(
                "Order was not completed because "
                "MongoDB could not save the order/events."
            )


# ============================================================
# ADMIN PANEL
# ============================================================

def admin_panel():

    st.header("Admin")

    st.write(
        "Total Products:",
        len(PRODUCTS)
    )

    st.subheader(
        "MongoDB Atlas Status"
    )

    try:

        client = get_mongo_client()

        client.admin.command(
            "ping"
        )

        st.success(
            "MongoDB Atlas connected successfully."
        )

        st.write(
            "Database:",
            st.secrets.get(
                "MONGO_DB",
                "ecommerce_db"
            )
        )

        st.write(
            "Events collection: events"
        )

        st.write(
            "Orders collection: orders"
        )

        # -----------------------------------------------
        # COUNT EVENTS
        # -----------------------------------------------

        event_count = (
            get_events_collection()
            .count_documents({})
        )

        order_count = (
            get_orders_collection()
            .count_documents({})
        )

        col1, col2 = st.columns(2)

        col1.metric(
            "Events in MongoDB",
            event_count
        )

        col2.metric(
            "Orders in MongoDB",
            order_count
        )

    except Exception as e:

        st.error(
            "MongoDB connection failed."
        )

        st.code(
            str(e)
        )


# ============================================================
# ANALYTICS DASHBOARD
# ============================================================

def analytics():

    st.header(
        "Analytics Dashboard"
    )

    df = load_events()

    if df.empty:

        st.warning(
            "No events found in MongoDB."
        )

        return

    # --------------------------------------------------------
    # TIMESTAMP
    # --------------------------------------------------------

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce"
    )

    # --------------------------------------------------------
    # PARSE EXTRA / GEO DATA
    # --------------------------------------------------------

    def parse_extra(value):

        if not value:
            return {}

        try:

            if isinstance(
                value,
                str
            ):

                return json.loads(
                    value
                )

            if isinstance(
                value,
                dict
            ):

                return value

        except Exception:
            return {}

        return {}

    extra_parsed = df[
        "extra"
    ].apply(parse_extra)

    extra_df = pd.json_normalize(
        extra_parsed
    )

    if not extra_df.empty:

        extra_df.columns = [
            f"geo_{c}"
            for c in extra_df.columns
        ]

    analytics_df = pd.concat(
        [
            df.drop(
                columns=["extra"],
                errors="ignore"
            ).reset_index(drop=True),

            extra_df.reset_index(drop=True)
        ],
        axis=1
    )

    analytics_df = clean_df(
        analytics_df
    )

    # --------------------------------------------------------
    # RAW EVENT LOGS
    # --------------------------------------------------------

    st.subheader(
        "Raw Event Logs"
    )

    st.dataframe(
        analytics_df.sort_values(
            "timestamp",
            ascending=False
        ).head(500),
        use_container_width=True
    )

    # --------------------------------------------------------
    # FILTERS
    # --------------------------------------------------------

    st.subheader(
        "Filters"
    )

    with st.expander(
        "Filter Events",
        expanded=False
    ):

        col1, col2, col3 = st.columns(3)

        with col1:

            actions = sorted(
                analytics_df[
                    "action"
                ]
                .dropna()
                .unique()
                .tolist()
            )

            selected_actions = st.multiselect(
                "Action",
                actions,
                default=actions
            )

        with col2:

            products = sorted(
                analytics_df[
                    "product_name"
                ]
                .dropna()
                .unique()
                .tolist()
            )

            selected_products = st.multiselect(
                "Product",
                products,
                default=products
            )

        with col3:

            users = sorted(
                analytics_df[
                    "user"
                ]
                .dropna()
                .unique()
                .tolist()
            )

            selected_users = st.multiselect(
                "User",
                users,
                default=users
            )

    # --------------------------------------------------------
    # FILTER DATA
    # --------------------------------------------------------

    mask = (
        analytics_df["action"].isin(
            selected_actions
        )
        &
        analytics_df["product_name"].isin(
            selected_products
        )
        &
        analytics_df["user"].isin(
            selected_users
        )
    )

    filtered = analytics_df[
        mask
    ].copy()

    filtered = clean_df(
        filtered
    )

    if filtered.empty:

        st.info(
            "No events match the selected filters."
        )

        return

    # --------------------------------------------------------
    # EVENT SUBSETS
    # --------------------------------------------------------

    views = filtered[
        filtered["action"] == "view"
    ].copy()

    adds = filtered[
        filtered["action"] == "add_to_cart"
    ].copy()

    order_events = filtered[
        filtered["action"] == "order"
    ].copy()

    # --------------------------------------------------------
    # KPI
    # --------------------------------------------------------

    st.subheader(
        "Key Metrics"
    )

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    kpi1.metric(
        "Total Events",
        len(filtered)
    )

    kpi2.metric(
        "Unique Users",
        int(
            filtered["user"].nunique()
        )
    )

    kpi3.metric(
        "Product Views",
        len(views)
    )

    kpi4.metric(
        "Order Events",
        len(order_events)
    )

    # --------------------------------------------------------
    # ACTION COUNTS
    # --------------------------------------------------------

    st.subheader(
        "Event Counts by Action"
    )

    action_counts = (
        filtered
        .groupby("action")
        .size()
        .reset_index(
            name="count"
        )
        .sort_values(
            "count",
            ascending=False
        )
    )

    st.dataframe(
        action_counts,
        use_container_width=True
    )

    st.bar_chart(
        action_counts.set_index(
            "action"
        )["count"]
    )

    # --------------------------------------------------------
    # VIEWS BY PRODUCT
    # --------------------------------------------------------

    st.subheader(
        "Product Views"
    )

    if not views.empty:

        view_counts = (
            views
            .groupby("product_name")
            .size()
            .reset_index(
                name="views"
            )
            .sort_values(
                "views",
                ascending=False
            )
        )

        st.bar_chart(
            view_counts.set_index(
                "product_name"
            )["views"]
        )

        st.dataframe(
            view_counts,
            use_container_width=True
        )

    else:

        st.write(
            "No product view events."
        )

    # --------------------------------------------------------
    # ADD TO CART
    # --------------------------------------------------------

    st.subheader(
        "Add-to-Cart Events"
    )

    if not adds.empty:

        add_counts = (
            adds
            .groupby("product_name")
            .size()
            .reset_index(
                name="adds"
            )
            .sort_values(
                "adds",
                ascending=False
            )
        )

        st.bar_chart(
            add_counts.set_index(
                "product_name"
            )["adds"]
        )

        st.dataframe(
            add_counts,
            use_container_width=True
        )

    else:

        st.write(
            "No add-to-cart events."
        )

    # --------------------------------------------------------
    # ORDER EVENTS
    # --------------------------------------------------------

    st.subheader(
        "Order Events"
    )

    if not order_events.empty:

        order_counts = (
            order_events
            .groupby("product_name")
            .size()
            .reset_index(
                name="orders"
            )
            .sort_values(
                "orders",
                ascending=False
            )
        )

        st.bar_chart(
            order_counts.set_index(
                "product_name"
            )["orders"]
        )

        st.dataframe(
            order_counts,
            use_container_width=True
        )

    else:

        st.write(
            "No order events."
        )

    # --------------------------------------------------------
    # HOURLY TREND
    # --------------------------------------------------------

    st.subheader(
        "Hourly Product Views"
    )

    if not views.empty:

        views["hour"] = (
            views["timestamp"]
            .dt.hour
        )

        hourly = (
            views
            .groupby("hour")
            .size()
            .reindex(
                range(24),
                fill_value=0
            )
        )

        st.line_chart(
            hourly
        )

    # --------------------------------------------------------
    # DAILY TREND
    # --------------------------------------------------------

    st.subheader(
        "Daily Product Views"
    )

    if not views.empty:

        views["date"] = (
            views["timestamp"]
            .dt.date
        )

        daily = (
            views
            .groupby("date")
            .size()
        )

        st.line_chart(
            daily
        )

    # --------------------------------------------------------
    # TOP USERS
    # --------------------------------------------------------

    st.subheader(
        "Top Users by Events"
    )

    top_users = (
        filtered
        .groupby("user")
        .size()
        .reset_index(
            name="events"
        )
        .sort_values(
            "events",
            ascending=False
        )
    )

    st.dataframe(
        top_users,
        use_container_width=True
    )

    # --------------------------------------------------------
    # COUNTRY
    # --------------------------------------------------------

    st.subheader(
        "Events by Country"
    )

    if "geo_country_name" in analytics_df.columns:

        country_counts = (
            filtered[
                "geo_country_name"
            ]
            .dropna()
            .value_counts()
            .reset_index()
        )

        country_counts.columns = [
            "country",
            "count"
        ]

        if not country_counts.empty:

            st.dataframe(
                country_counts,
                use_container_width=True
            )

            st.bar_chart(
                country_counts.set_index(
                    "country"
                )["count"]
            )

    # --------------------------------------------------------
    # CITY
    # --------------------------------------------------------

    st.subheader(
        "Events by City"
    )

    if "geo_city" in analytics_df.columns:

        city_counts = (
            filtered[
                "geo_city"
            ]
            .dropna()
            .value_counts()
            .reset_index()
        )

        city_counts.columns = [
            "city",
            "count"
        ]

        if not city_counts.empty:

            st.dataframe(
                city_counts,
                use_container_width=True
            )

            st.bar_chart(
                city_counts.set_index(
                    "city"
                )["count"]
            )

    # --------------------------------------------------------
    # PRODUCT VS CITY
    # --------------------------------------------------------

    st.subheader(
        "Product vs City"
    )

    if "geo_city" in analytics_df.columns:

        pivot = filtered.pivot_table(
            index="product_name",
            columns="geo_city",
            values="action",
            aggfunc="count",
            fill_value=0
        )

        if not pivot.empty:

            st.dataframe(
                pivot,
                use_container_width=True
            )

    # --------------------------------------------------------
    # MAP
    # --------------------------------------------------------

    st.subheader(
        "Visitor Locations"
    )

    if (
        "geo_latitude"
        in analytics_df.columns
        and
        "geo_longitude"
        in analytics_df.columns
    ):

        map_df = filtered.dropna(
            subset=[
                "geo_latitude",
                "geo_longitude"
            ]
        ).copy()

        if not map_df.empty:

            map_plot = map_df[
                [
                    "geo_latitude",
                    "geo_longitude"
                ]
            ].rename(
                columns={
                    "geo_latitude": "lat",
                    "geo_longitude": "lon"
                }
            )

            st.map(
                map_plot
            )

        else:

            st.write(
                "No geographic coordinates available."
            )

    # --------------------------------------------------------
    # EXPORT
    # --------------------------------------------------------

    st.subheader(
        "Export Events"
    )

    csv_data = filtered.to_csv(
        index=False
    )

    st.download_button(
        "Download Events CSV",
        csv_data,
        file_name="analytics_events.csv",
        mime="text/csv"
    )


# ============================================================
# MAIN NAVIGATION
# ============================================================

st.sidebar.title(
    "Navigation"
)

choice = st.sidebar.radio(
    "Go to",
    [
        "Home",
        "Products",
        "Cart",
        "Admin",
        "Analytics"
    ]
)


# ============================================================
# IP COLLECTION
# ============================================================

ensure_client_ip()


current_user = (
    st.session_state.user
    or "guest"
)

current_ip = (
    st.session_state.get(
        "client_ip"
    )
)

current_geo = (
    get_geo(current_ip)
    if current_ip
    else {}
)


# ============================================================
# PAGE EVENTS
# ============================================================

if choice == "Home":

    log_event(
        current_user,
        "-",
        "-",
        "home_view",
        current_geo
    )

    st.header(
        "Welcome to the E-Commerce App"
    )

    st.write(
        "Cloud-based E-Commerce Analytics "
        "Application"
    )


elif choice == "Products":

    log_event(
        current_user,
        "-",
        "-",
        "products_view",
        current_geo
    )

    product_page()


elif choice == "Cart":

    log_event(
        current_user,
        "-",
        "-",
        "cart_view",
        current_geo
    )

    show_cart()

    st.divider()

    checkout()


elif choice == "Admin":

    log_event(
        current_user,
        "-",
        "-",
        "admin_view",
        current_geo
    )

    admin_panel()


elif choice == "Analytics":

    log_event(
        current_user,
        "-",
        "-",
        "analytics_view",
        current_geo
    )

    analytics()
