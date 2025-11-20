# -------------------------
# MAIN NAVIGATION MENU (FIXED)
# -------------------------
st.sidebar.title("Navigation")
choice = st.sidebar.radio("Go to", ["Home", "Products", "Cart", "Admin", "Analytics"])

# Capture IP
ensure_client_ip()
current_user = st.session_state.user or "guest"
current_ip = st.session_state.get("client_ip")
current_geo = get_geo(current_ip) if current_ip else {}

# Log page visits for visitor analytics
def log_page(page_name):
    log_event(
        current_user,
        "-", "-",
        page_name,
        current_geo
    )

if choice == "Home":
    log_page("home_view")
    st.header("Welcome to the E-Commerce App")

elif choice == "Products":
    log_page("products_view")
    product_page()

elif choice == "Cart":
    log_page("cart_view")
    show_cart()
    checkout()

elif choice == "Admin":
    log_page("admin_view")
    admin_panel()

elif choice == "Analytics":
    log_page("analytics_view")
    analytics()



