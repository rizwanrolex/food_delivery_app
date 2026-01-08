import streamlit as st
import mysql.connector
import pandas as pd
import time


# 1. DATABASE CONNECTION & FUNCTIONS

def get_db_connection():
    """Connect to the MySQL Database"""
    return mysql.connector.connect(
            host = "gateway01.ap-southeast-1.prod.aws.tidbcloud.com",
            port = 4000,
            user = "F4JuMzeYACTctmz.root",
            password = "mEL49H4HoMpHJE19",
            database = "food_delivery_db",
            use_pure=True
        # Note: Maine ssl_ca wali line hata di hai taake 'File Not Found' ka error na aye.
        # TiDB usually iske baghair connect ho jata hai.
    )

def check_login(email, password):
    """Verify email and password against the Users table"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    sql = "SELECT user_id, full_name, user_type FROM Users WHERE email = %s AND password = %s"
    cursor.execute(sql, (email, password))
    user = cursor.fetchone()
    
    cursor.close()
    conn.close()
    return user

def get_active_resturant():
    """Fetch all active restaurants"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    sql = "SELECT restaurant_id, name, address, is_active FROM Restaurants WHERE is_active = 1"
    cursor.execute(sql)
    result = cursor.fetchall()
    cursor.close()
    conn.close()
    return result

def get_menu(restaurant_id):
    """Fetch menu items for a specific restaurant"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    sql = "SELECT item_id, name, price, category FROM MenuItems WHERE restaurant_id = %s"
    cursor.execute(sql, (restaurant_id,))
    result = cursor.fetchall()
    cursor.close()
    conn.close()
    return result

def place_order(user_id, restaurant_id, cart_item):
    """Insert order into DB and return the new Order ID"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Calculate Total Amount
    total_amount = 0
    for item in cart_item:
        qty = item[1]
        price = item[2]
        total_amount += (qty * price)

    # 2. Create the Order Record
    sql_for_order = "INSERT INTO orders(customer_id, restaurant_id, total_amount, order_status) VALUES(%s, %s, %s, 'pending')"
    val_for_order = (user_id, restaurant_id, total_amount)
    cursor.execute(sql_for_order, val_for_order)
    new_order_id = cursor.lastrowid

    # 3. Insert Order Items
    sql_for_order_item = "INSERT INTO orderitems(order_id, item_id, quantity, price_at_purchase) VALUES(%s, %s, %s, %s)"
    for item in cart_item:
        item_id = item[0]
        qty = item[1]
        price = item[2]
        cursor.execute(sql_for_order_item, (new_order_id, item_id, qty, price))

    conn.commit()
    cursor.close()
    conn.close()
    return new_order_id

def get_order_history(user_id):
    """Fetch past orders for a specific customer"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    sql = """
        SELECT o.order_id, o.total_amount, o.order_status, r.name as restaurant_name
        FROM Orders o
        JOIN Restaurants r ON o.restaurant_id = r.restaurant_id
        WHERE o.customer_id = %s
        ORDER BY o.created_at DESC
    """
    cursor.execute(sql, (user_id,))
    result = cursor.fetchall()
    cursor.close()
    conn.close()
    return result

# --- KITCHEN / ADMIN FUNCTIONS ---
def get_pending_orders():
    """Fetch orders for the kitchen view"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    sql = """
        SELECT o.order_id, o.total_amount, o.order_status, o.created_at, u.full_name, r.name as restaurant_name
        FROM Orders o
        JOIN Users u ON o.customer_id = u.user_id
        JOIN Restaurants r ON o.restaurant_id = r.restaurant_id
        WHERE o.order_status IN ('pending', 'cooking', 'ready')
        ORDER BY o.created_at ASC
    """
    cursor.execute(sql)
    result = cursor.fetchall()
    cursor.close()
    conn.close()
    return result

def update_order_status(order_id, new_status):
    """Update status of an order"""
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = "UPDATE Orders SET order_status = %s WHERE order_id = %s"
    cursor.execute(sql, (new_status, order_id))
    conn.commit()
    cursor.close()
    conn.close()


# 2. APP CONFIGURATION & SESSION STATE

st.set_page_config(page_title="Food Delivery App", page_icon="🍔", layout="wide")

# Initialize Cart
if 'cart' not in st.session_state:
    st.session_state['cart'] = []

# Initialize Role (None = Not Logged In)
if 'role' not in st.session_state:
    st.session_state['role'] = None 


# 3. LOGIN SCREEN

if st.session_state['role'] is None:
    st.title("🍔 Welcome to Foodie Express")
    
    col1, col2 = st.columns([1, 1], gap="large")
    
    with col1:
        st.image("https://cdn-icons-png.flaticon.com/512/295/295128.png", width=150)
        st.subheader("Login Required")
        st.write("Please sign in to access your account.")
        st.info("Test Accounts:\n- Customer: ali@gmail.com / 1234\n- Restaurant: chef@gmail.com / 1234")

    with col2:
        with st.container(border=True):
            st.subheader("🔐 Sign In")
            
            email = st.text_input("Email Address", placeholder="name@example.com")
            password = st.text_input("Password", type="password", placeholder="****")
            st.write("")
            
            if st.button("Login", use_container_width=True):
                if email and password:
                    # Check credentials against DB
                    user = check_login(email, password)
                    
                    if user:
                        # SET SESSION VARIABLES
                        st.session_state['role'] = user['user_type']
                        st.session_state['user_id'] = user['user_id']
                        st.session_state['user_name'] = user['full_name']
                        
                        st.success(f"Welcome back, {user['full_name']}!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Invalid email or password.")
                else:
                    st.warning("Please fill in all fields.")
    
    st.stop() # 🛑 STOP HERE if not logged in


# 4. SIDEBAR NAVIGATION

st.sidebar.title("🍔 Foodie Express")

if st.session_state['role'] == 'customer':
    st.sidebar.write(f"👤 **{st.session_state['user_name']}**")
    page = st.sidebar.radio("Go to:", ["Home", "Cart", "My Orders"])
    
    st.sidebar.markdown("---")
    # Live Cart Counter
    cart_count = len(st.session_state['cart'])
    st.sidebar.metric("🛒 Cart Items", f"{cart_count}")

elif st.session_state['role'] == 'restaurant':
    st.sidebar.write(f"👨‍🍳 **{st.session_state['user_name']}** (Admin)")
    page = st.sidebar.radio("Go to:", ["Kitchen Dashboard"])

st.sidebar.markdown("---")
if st.sidebar.button("🚪 Logout"):
    st.session_state['role'] = None
    st.session_state['user_id'] = None
    st.session_state['cart'] = [] # Clear cart on logout
    st.rerun()


# 5. PAGE LOGIC (CUSTOMER VIEW)

if st.session_state['role'] == 'customer':
    
    # --- HOME PAGE ---
    if page == "Home":
        # Check if a restaurant is already selected
        if 'selected_restaurant' in st.session_state:
            rest_id = st.session_state['selected_restaurant']
            rest_name = st.session_state.get('restaurant_name', 'Unknown')

            st.title(f"Menu: {rest_name}")
            if st.button("⬅ Back to Restaurants"):
                del st.session_state['selected_restaurant']
                st.rerun()

            menu_items = get_menu(rest_id)
            
            if menu_items:
                # Display Menu Table
                df = pd.DataFrame(menu_items)
                df_display = df[['name', 'price', 'category']]
                df_display.columns = ['Name', 'Price(RS)', 'Category']
                st.table(df_display)

                st.markdown("---")
                st.subheader("👇 Select Item to Add")

                # Add to Cart Logic
                item_options = {item['name']: item for item in menu_items}

                with st.container(border=True):
                    # Vertical alignment ensures buttons line up with inputs
                    col_item, col_qty, col_btn = st.columns([2, 1, 1], vertical_alignment="bottom")

                    with col_item:
                        selected_name = st.selectbox("Choose Item:", list(item_options.keys()))
                    with col_qty:
                        qty = st.number_input("Qty:", min_value=1, max_value=20, value=1)
                    with col_btn:
                        if st.button("Add", use_container_width=True):
                            selected_item = item_options[selected_name]
                            # Create Cart Entry
                            cart_entry = (selected_item['item_id'], qty, selected_item['price'], selected_name)
                            st.session_state['cart'].append(cart_entry)
                            
                            st.toast(f"Added {qty} x {selected_name}!", icon="✅")
                            time.sleep(0.5) 
                            st.rerun()      
            else:
                st.info("No menu items found.")

        else:
            # Show list of restaurants with Images
            st.title("📍 Available Restaurants")
            restaurants = get_active_resturant()
            
            for r in restaurants:
                with st.container(border=True):
                    col_img, col_info, col_btn = st.columns([1, 4, 2], vertical_alignment="center")
                    
                    # 1. Image
                    with col_img:
                        st.image("https://cdn-icons-png.flaticon.com/512/4287/4287725.png", width=80)
                    
                    # 2. Info
                    with col_info:
                        st.subheader(r['name'])
                        st.write(f"📍 {r['address']}")
                    
                    # 3. Button
                    with col_btn:
                        if st.button("View Menu ➡", key=r['restaurant_id'], use_container_width=True):
                            st.session_state['selected_restaurant'] = r['restaurant_id']
                            st.session_state['restaurant_name'] = r['name']
                            st.rerun()

    # --- CART PAGE ---
    elif page == "Cart":
        st.title("🛒 Your Cart")
        
        if not st.session_state['cart']:
            st.info("Your cart is empty. Go to Home to add items!")
        else:
            # Display Cart Table
            cart_df = pd.DataFrame(st.session_state['cart'], columns=['Item ID', 'Qty', 'Price', 'Name'])
            cart_df['Total'] = cart_df['Qty'] * cart_df['Price']
            st.table(cart_df[['Name', 'Qty', 'Price', 'Total']])
            
            total_amount = cart_df['Total'].sum()
            
            st.markdown("---")
            col_total, col_btn = st.columns([3, 1])
            with col_total:
                st.subheader(f"Total Bill: RS {total_amount}")
            
            with col_btn:
                if st.button("✅ Place Order", use_container_width=True):
                    # Use the logged-in User ID
                    user_id = st.session_state['user_id']
                    rest_id = st.session_state.get('selected_restaurant', 1)
                    
                    try:
                        new_order_id = place_order(user_id, rest_id, st.session_state['cart'])
                        
                        if new_order_id:
                            st.session_state['cart'] = [] # Clear Cart
                            st.success(f"Order #{new_order_id} placed successfully!")
                            st.balloons()
                            time.sleep(2)
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

    # --- MY ORDERS PAGE ---
    elif page == "My Orders":
        st.title("🧾 Order History")
        user_id = st.session_state['user_id']
        orders = get_order_history(user_id)
        
        if orders:
            df_orders = pd.DataFrame(orders)
            st.table(df_orders[['order_id', 'restaurant_name', 'total_amount', 'order_status']])
        else:
            st.info("You haven't placed any orders yet.")


# 6. PAGE LOGIC (RESTAURANT VIEW)

elif st.session_state['role'] == 'restaurant':
    
    if page == "Kitchen Dashboard":
        st.title("👨‍🍳 Kitchen Dashboard")
        st.write("Manage incoming active orders.")
        
        pending_orders = get_pending_orders()
        
        if not pending_orders:
            st.success("✅ No active orders. Kitchen is clear!")
        else:
            for order in pending_orders:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 1.5, 1])
                    
                    # Order Info
                    with c1:
                        st.subheader(f"Order #{order['order_id']}")
                        st.write(f"**{order['restaurant_name']}** | {order['full_name']}")
                        st.caption(f"Status: {order['order_status']}")
                    
                    # Status Selectbox
                    with c2:
                        current_stat = order['order_status']
                        opts = ["pending", "cooking", "ready", "delivered"]
                        # Find correct index for dropdown
                        idx = opts.index(current_stat) if current_stat in opts else 0
                        
                        new_stat = st.selectbox(
                            "Update Status", 
                            opts, 
                            index=idx, 
                            key=f"s_{order['order_id']}", 
                            label_visibility="collapsed"
                        )
                    
                    # Update Button
                    with c3:
                        if st.button("Update", key=f"b_{order['order_id']}", use_container_width=True):
                            update_order_status(order['order_id'], new_stat)
                            st.toast(f"Order #{order['order_id']} updated!")
                            time.sleep(1)
                            st.rerun()


# 7. FOOTER

st.sidebar.markdown("---")
if st.session_state['role'] == 'customer':
    st.sidebar.caption("© 2025 Foodie Express | Customer App")
elif st.session_state['role'] == 'restaurant':
    st.sidebar.caption("© 2025 Foodie Express | Partner App")
else:

    st.sidebar.caption("© 2025 Foodie Express")
