
import os
import sqlite3
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    abort
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from database import (
    get_db_connection,
    create_tables,
    seed_foods
)


# ==================================================
# APPLICATION CONFIGURATION
# ==================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "change-this-development-secret"
)

ORDER_STATUSES = [
    "New Order",
    "Preparing",
    "Ready for Pickup",
    "Out for Delivery",
    "Delivered",
    "Cancelled"
]


# ==================================================
# DATABASE SETUP
# ==================================================

def setup_database():
    create_tables()
    seed_foods()

    conn = get_db_connection()

    try:
        admin = conn.execute(
            "SELECT id FROM admins WHERE username = ?",
            ("admin",)
        ).fetchone()

        if admin is None:
            conn.execute("""
                INSERT INTO admins (username, password)
                VALUES (?, ?)
            """, (
                "admin",
                generate_password_hash("ChangeMe123!")
            ))

            conn.commit()

    finally:
        conn.close()


# ==================================================
# AUTHENTICATION DECORATORS
# ==================================================

def customer_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "customer_id" not in session:
            flash("Please login to continue.", "warning")
            return redirect(url_for("login"))

        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "admin_id" not in session:
            flash("Please login as admin.", "warning")
            return redirect(url_for("admin_login"))

        return view(*args, **kwargs)

    return wrapped


# ==================================================
# CUSTOMER HOME
# ==================================================

@app.route("/")
def home():
    conn = get_db_connection()

    try:
        foods = conn.execute("""
            SELECT *
            FROM foods
            WHERE available = 1
            ORDER BY id DESC
            LIMIT 8
        """).fetchall()

        return render_template("home.html", foods=foods)

    finally:
        conn.close()


# ==================================================
# MENU
# ==================================================

@app.route("/menu")
def menu():
    search_query = request.args.get("q", "").strip()
    selected_category = request.args.get(
        "category", ""
    ).strip()

    conn = get_db_connection()

    try:
        category_rows = conn.execute("""
            SELECT DISTINCT category
            FROM foods
            WHERE available = 1
              AND category IS NOT NULL
              AND TRIM(category) != ''
            ORDER BY category
        """).fetchall()

        categories = [
            row["category"] for row in category_rows
        ]

        sql = """
            SELECT id, name, description, price,
                   image, category
            FROM foods
            WHERE available = 1
        """

        params = []

        if selected_category:
            sql += " AND category = ?"
            params.append(selected_category)

        if search_query:
            sql += """
                AND (
                    name LIKE ?
                    OR description LIKE ?
                    OR category LIKE ?
                )
            """

            term = f"%{search_query}%"
            params.extend([term, term, term])

        sql += " ORDER BY name"

        foods = conn.execute(
            sql, params
        ).fetchall()

        return render_template(
            "menu.html",
            foods=foods,
            categories=categories,
            selected_category=selected_category,
            search_query=search_query
        )

    finally:
        conn.close()


# ==================================================
# CUSTOMER REGISTRATION
# ==================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        phone = request.form.get("phone", "").strip()

        if not name or not email or len(password) < 8:
            flash(
                "Enter your name, email and a password "
                "of at least 8 characters.",
                "danger"
            )
            return redirect(url_for("register"))

        conn = get_db_connection()

        try:
            conn.execute("""
                INSERT INTO customers (
                    name, email, password, phone
                )
                VALUES (?, ?, ?, ?)
            """, (
                name,
                email,
                generate_password_hash(password),
                phone
            ))

            conn.commit()

            flash(
                "Registration successful. Please login.",
                "success"
            )

            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            flash(
                "This email is already registered.",
                "danger"
            )

        finally:
            conn.close()

    return render_template("register.html")


# ==================================================
# CUSTOMER LOGIN
# ==================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get(
            "email", ""
        ).strip().lower()

        password = request.form.get("password", "")

        conn = get_db_connection()

        try:
            customer = conn.execute("""
                SELECT *
                FROM customers
                WHERE email = ?
            """, (email,)).fetchone()

        finally:
            conn.close()

        if (
            customer
            and check_password_hash(
                customer["password"], password
            )
        ):
            session.clear()
            session["customer_id"] = customer["id"]
            session["customer_name"] = customer["name"]

            flash("Welcome back!", "success")
            return redirect(url_for("menu"))

        flash("Invalid email or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


# ==================================================
# CART HELPERS
# ==================================================

def get_cart_items():
    cart_data = session.get("cart", {})

    if not isinstance(cart_data, dict):
        return [], 0.0

    items = []
    total = 0.0

    conn = get_db_connection()

    try:
        for food_id, quantity in cart_data.items():
            try:
                food_id = int(food_id)
                quantity = int(quantity)
            except (ValueError, TypeError):
                continue

            if quantity < 1:
                continue

            food = conn.execute("""
                SELECT *
                FROM foods
                WHERE id = ? AND available = 1
            """, (food_id,)).fetchone()

            if food:
                price = float(food["price"])
                subtotal = price * quantity

                items.append({
                    "id": food["id"],
                    "name": food["name"],
                    "price": price,
                    "image": food["image"],
                    "quantity": quantity,
                    "subtotal": subtotal
                })

                total += subtotal

    finally:
        conn.close()

    return items, round(total, 2)


# ==================================================
# CART ROUTES
# ==================================================

@app.route("/add_to_cart/<int:food_id>", methods=["POST"])
def add_to_cart(food_id):
    conn = get_db_connection()

    try:
        food = conn.execute("""
            SELECT id
            FROM foods
            WHERE id = ? AND available = 1
        """, (food_id,)).fetchone()

    finally:
        conn.close()

    if not food:
        flash("This food item is not available.", "danger")
        return redirect(url_for("menu"))

    cart_data = session.get("cart", {})

    if not isinstance(cart_data, dict):
        cart_data = {}

    key = str(food_id)
    cart_data[key] = min(int(cart_data.get(key, 0)) + 1, 99)

    session["cart"] = cart_data
    session.modified = True

    flash("Food added to your cart.", "success")

    return redirect(request.referrer or url_for("menu"))


@app.route("/cart")
def cart():
    items, total = get_cart_items()

    return render_template(
        "cart.html",
        items=items,
        total=total
    )


@app.route("/update_cart/<int:food_id>", methods=["POST"])
def update_cart(food_id):
    try:
        quantity = int(request.form.get("quantity", "1"))
    except (ValueError, TypeError):
        quantity = 1

    cart_data = session.get("cart", {})

    if not isinstance(cart_data, dict):
        cart_data = {}

    key = str(food_id)

    if quantity <= 0:
        cart_data.pop(key, None)

    elif key in cart_data:
        cart_data[key] = min(quantity, 99)

    session["cart"] = cart_data
    session.modified = True

    return redirect(url_for("cart"))


@app.route("/remove_from_cart/<int:food_id>", methods=["POST"])
def remove_from_cart(food_id):
    cart_data = session.get("cart", {})

    if not isinstance(cart_data, dict):
        cart_data = {}

    cart_data.pop(str(food_id), None)

    session["cart"] = cart_data
    session.modified = True

    flash("Item removed from cart.", "success")

    return redirect(url_for("cart"))


# ==================================================
# CHECKOUT
# ==================================================

@app.route("/checkout", methods=["GET", "POST"])
@customer_required
def checkout():
    items, total = get_cart_items()

    if not items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("menu"))

    conn = get_db_connection()

    try:
        customer = conn.execute("""
            SELECT *
            FROM customers
            WHERE id = ?
        """, (session["customer_id"],)).fetchone()

    finally:
        conn.close()

    if request.method == "POST":
        address = request.form.get(
            "delivery_address", ""
        ).strip()

        payment_method = request.form.get(
            "payment_method", ""
        ).strip()

        if not address:
            flash("Please enter your delivery address.", "danger")
            return redirect(url_for("checkout"))

        if payment_method not in ("UPI", "COD"):
            flash(
                "Please select UPI QR or Cash on Delivery.",
                "danger"
            )
            return redirect(url_for("checkout"))

        conn = get_db_connection()

        try:
            conn.execute("BEGIN")

            verified_items = []
            verified_total = 0.0

            # Recheck prices and availability in the database.
            for item in items:
                food = conn.execute("""
                    SELECT *
                    FROM foods
                    WHERE id = ? AND available = 1
                """, (item["id"],)).fetchone()

                if not food:
                    raise ValueError(
                        "A food item is no longer available."
                    )

                quantity = item["quantity"]
                subtotal = float(food["price"]) * quantity

                verified_items.append(
                    (food, quantity, subtotal)
                )

                verified_total += subtotal

            verified_total = round(verified_total, 2)

            payment_status = (
                "Pending"
                if payment_method == "UPI"
                else "Cash on Delivery"
            )

            cursor = conn.execute("""
                INSERT INTO orders (
                    customer_id,
                    total_amount,
                    payment_method,
                    payment_status,
                    order_status,
                    delivery_address
                )
                VALUES (?, ?, ?, ?, 'New Order', ?)
            """, (
                session["customer_id"],
                verified_total,
                payment_method,
                payment_status,
                address
            ))

            order_id = cursor.lastrowid

            for food, quantity, subtotal in verified_items:
                conn.execute("""
                    INSERT INTO order_items (
                        order_id,
                        food_id,
                        food_name,
                        price,
                        quantity
                    )
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    order_id,
                    food["id"],
                    food["name"],
                    food["price"],
                    quantity
                ))

            conn.execute("""
                INSERT INTO payments (
                    order_id,
                    payment_method,
                    amount,
                    payment_status
                )
                VALUES (?, ?, ?, ?)
            """, (
                order_id,
                payment_method,
                verified_total,
                payment_status
            ))

            conn.commit()

            session["cart"] = {}
            session.modified = True

            if payment_method == "UPI":
                return redirect(
                    url_for("payment", order_id=order_id)
                )

            flash(
                "Order placed! Pay cash when your food "
                "is delivered.",
                "success"
            )

            return redirect(
                url_for(
                    "order_tracking",
                    order_id=order_id
                )
            )

        except (sqlite3.Error, ValueError) as error:
            conn.rollback()
            flash(
                str(error) or "Unable to place your order.",
                "danger"
            )

        finally:
            conn.close()

        return redirect(url_for("checkout"))

    return render_template(
        "checkout.html",
        customer=customer,
        items=items,
        total=total
    )


# ==================================================
# PAYMENT
# ==================================================

@app.route("/payment/<int:order_id>", methods=["GET", "POST"])
@customer_required
def payment(order_id):
    conn = get_db_connection()

    try:
        order = conn.execute("""
            SELECT *
            FROM orders
            WHERE id = ? AND customer_id = ?
        """, (
            order_id,
            session["customer_id"]
        )).fetchone()

        if not order:
            abort(404)

        if order["payment_method"] != "UPI":
            return redirect(
                url_for(
                    "order_tracking",
                    order_id=order_id
                )
            )

        if request.method == "POST":
            transaction_id = request.form.get(
                "transaction_id", ""
            ).strip()

            if not transaction_id:
                flash(
                    "Enter your UPI transaction reference.",
                    "danger"
                )

                return redirect(
                    url_for("payment", order_id=order_id)
                )

            if order["payment_status"] == "Pending":
                conn.execute("""
                    UPDATE payments
                    SET transaction_id = ?,
                        payment_status = ?
                    WHERE order_id = ?
                """, (
                    transaction_id,
                    "Submitted for Verification",
                    order_id
                ))

                conn.execute("""
                    UPDATE orders
                    SET payment_status = ?
                    WHERE id = ?
                """, (
                    "Submitted for Verification",
                    order_id
                ))

                conn.commit()

                flash(
                    "Payment reference submitted. "
                    "Payment is not confirmed until verified "
                    "by the admin.",
                    "info"
                )

            return redirect(
                url_for(
                    "order_tracking",
                    order_id=order_id
                )
            )

        return render_template(
            "payment.html",
            order=order
        )

    finally:
        conn.close()


# ==================================================
# CUSTOMER ORDERS
# ==================================================

@app.route("/orders")
@customer_required
def orders():
    conn = get_db_connection()

    try:
        customer_orders = conn.execute("""
            SELECT *
            FROM orders
            WHERE customer_id = ?
            ORDER BY id DESC
        """, (session["customer_id"],)).fetchall()

        return render_template(
            "orders.html",
            orders=customer_orders
        )

    finally:
        conn.close()


@app.route("/track_order/<int:order_id>")
@customer_required
def order_tracking(order_id):
    conn = get_db_connection()

    try:
        order = conn.execute("""
            SELECT *
            FROM orders
            WHERE id = ? AND customer_id = ?
        """, (
            order_id,
            session["customer_id"]
        )).fetchone()

        if not order:
            abort(404)

        items = conn.execute("""
            SELECT *
            FROM order_items
            WHERE order_id = ?
        """, (order_id,)).fetchall()

        rider = None

        if order["rider_id"]:
            rider = conn.execute("""
                SELECT *
                FROM riders
                WHERE id = ?
            """, (order["rider_id"],)).fetchone()

        return render_template(
            "order_tracking.html",
            order=order,
            items=items,
            rider=rider,
            statuses=ORDER_STATUSES
        )

    finally:
        conn.close()


# Compatibility alias for templates using url_for('track_order').
app.add_url_rule(
    "/track_order/<int:order_id>",
    endpoint="track_order",
    view_func=order_tracking
)


# ==================================================
# ADMIN LOGIN AND LOGOUT
# ==================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get(
            "username", ""
        ).strip()

        password = request.form.get("password", "")

        conn = get_db_connection()

        try:
            admin = conn.execute("""
                SELECT *
                FROM admins
                WHERE username = ?
            """, (username,)).fetchone()

        finally:
            conn.close()

        if (
            admin
            and check_password_hash(
                admin["password"], password
            )
        ):
            session.clear()
            session["admin_id"] = admin["id"]
            session["admin_username"] = admin["username"]

            return redirect(url_for("admin_dashboard"))

        flash(
            "Invalid admin username or password.",
            "danger"
        )

    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_id", None)
    session.pop("admin_username", None)

    return redirect(url_for("admin_login"))


# ==================================================
# ADMIN DASHBOARD
# ==================================================

@app.route("/admin")
@admin_required
def admin_dashboard():
    conn = get_db_connection()

    try:
        stats = {
            "orders": conn.execute(
                "SELECT COUNT(*) FROM orders"
            ).fetchone()[0],

            "customers": conn.execute(
                "SELECT COUNT(*) FROM customers"
            ).fetchone()[0],

            "foods": conn.execute(
                "SELECT COUNT(*) FROM foods"
            ).fetchone()[0],

            "pending": conn.execute("""
                SELECT COUNT(*)
                FROM orders
                WHERE order_status IN (
                    'New Order', 'Preparing'
                )
            """).fetchone()[0]
        }

        recent_orders = conn.execute("""
            SELECT orders.*,
                   customers.name AS customer_name
            FROM orders
            JOIN customers
              ON customers.id = orders.customer_id
            ORDER BY orders.id DESC
            LIMIT 10
        """).fetchall()

        return render_template(
            "dashboard.html",
            stats=stats,
            orders=recent_orders
        )

    finally:
        conn.close()


# ==================================================
# ADMIN ORDER MANAGEMENT
# ==================================================


@app.route("/admin/orders")
@admin_required
def admin_orders():
    conn = get_db_connection()

    try:

        all_orders = conn.execute("""
            SELECT
                orders.*,
                customers.name AS customer_name,
                customers.email AS customer_email,
                customers.phone AS customer_phone
            FROM orders
            LEFT JOIN customers
                ON customers.id = orders.customer_id
            ORDER BY orders.id DESC
        """).fetchall()


        riders = conn.execute("""
            SELECT id, name, phone
            FROM riders
            WHERE available = 1
            ORDER BY name
        """).fetchall()

        return render_template(
            "admin_orders.html",
            orders=all_orders,
            riders=riders,
            statuses=ORDER_STATUSES
        )
    finally:
        conn.close()



@app.route(
    "/admin/order/<int:order_id>/status",
    methods=["POST"]
)
@admin_required
def update_order_status(order_id):
    status = request.form.get("order_status", "")

    if status not in ORDER_STATUSES:
        abort(400)

    conn = get_db_connection()

    try:
        order = conn.execute(
            "SELECT id FROM orders WHERE id = ?",
            (order_id,)
        ).fetchone()

        if not order:
            abort(404)

        conn.execute("""
            UPDATE orders
            SET order_status = ?
            WHERE id = ?
        """, (status, order_id))

        conn.commit()

        flash(
            f"Order #{order_id} updated to {status}.",
            "success"
        )

    finally:
        conn.close()

    return redirect(url_for("admin_orders"))


@app.route(
    "/admin/order/<int:order_id>/payment",
    methods=["POST"]
)
@admin_required
def update_payment_status(order_id):
    payment_status = request.form.get(
        "payment_status", ""
    )

    allowed = (
        "Paid",
        "Pending",
        "Rejected"
    )

    if payment_status not in allowed:
        abort(400)

    conn = get_db_connection()

    try:
        order = conn.execute(
            "SELECT id FROM orders WHERE id = ?",
            (order_id,)
        ).fetchone()

        if not order:
            abort(404)

        conn.execute("""
            UPDATE orders
            SET payment_status = ?
            WHERE id = ?
        """, (payment_status, order_id))

        conn.execute("""
            UPDATE payments
            SET payment_status = ?
            WHERE order_id = ?
        """, (payment_status, order_id))

        conn.commit()

        flash("Payment status updated.", "success")

    finally:
        conn.close()

    return redirect(url_for("admin_orders"))


# ==================================================
# ADMIN FOOD MANAGEMENT
# ==================================================

@app.route(
    "/admin/foods/add",
    methods=["GET", "POST"]
)
@admin_required
def add_food():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get(
            "description", ""
        ).strip()

        category = request.form.get(
            "category", "Other"
        ).strip()

        image = request.form.get("image", "").strip()

        try:
            price = float(request.form.get("price", "0"))
        except (ValueError, TypeError):
            price = -1

        if not name or price < 0:
            flash(
                "Enter a valid food name and price.",
                "danger"
            )
            return redirect(url_for("add_food"))

        conn = get_db_connection()

        try:
            conn.execute("""
                INSERT INTO foods (
                    name,
                    description,
                    price,
                    image,
                    category,
                    available
                )
                VALUES (?, ?, ?, ?, ?, 1)
            """, (
                name,
                description,
                price,
                image,
                category or "Other"
            ))

            conn.commit()

            flash("Food item added.", "success")

        finally:
            conn.close()

        return redirect(url_for("food_management"))

    return render_template("add_food.html")


# Compatibility alias for templates using url_for('admin_add_food').
app.add_url_rule(
    "/admin/foods/add",
    endpoint="admin_add_food",
    view_func=add_food,
    methods=["GET", "POST"]
)


@app.route("/admin/foods")
@admin_required
def food_management():
    conn = get_db_connection()

    try:
        foods = conn.execute("""
            SELECT *
            FROM foods
            ORDER BY id DESC
        """).fetchall()

        return render_template(
            "food_list.html",
            foods=foods,
            admin_view=True
        )

    finally:
        conn.close()


# Compatibility alias for templates using url_for('admin_foods').
app.add_url_rule(
    "/admin/foods",
    endpoint="admin_foods",
    view_func=food_management
)



@app.route(
    "/admin/foods/<int:food_id>/edit",
    methods=["GET", "POST"],
    endpoint="admin_edit_food"
)
@admin_required
def edit_food(food_id):
    conn = get_db_connection()

    try:
        food = conn.execute(
            "SELECT * FROM foods WHERE id = ?",
            (food_id,)
        ).fetchone()

        if not food:
            abort(404)

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            description = request.form.get("description", "").strip()
            category = request.form.get("category", "Other").strip()
            image = request.form.get("image", "").strip()

            try:
                price = float(request.form.get("price", "0"))
            except (ValueError, TypeError):
                price = -1

            if not name or price <= 0:
                flash(
                    "Enter a valid food name and price.",
                    "danger"
                )
                return redirect(
                    url_for("admin_edit_food", food_id=food_id)
                )

            available = (
                1 if request.form.get("available") == "on" else 0
            )

            conn.execute("""
                UPDATE foods
                SET name = ?,
                    description = ?,
                    price = ?,
                    image = ?,
                    category = ?,
                    available = ?
                WHERE id = ?
            """, (
                name,
                description,
                price,
                image,
                category or "Other",
                available,
                food_id
            ))

            conn.commit()

            flash("Food item updated successfully.", "success")
            return redirect(url_for("admin_foods"))

        return render_template("edit_food.html", food=food)

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()



@app.route(
    "/admin/foods/<int:food_id>/delete",
    methods=["POST"],
    endpoint="admin_delete_food"
)
@admin_required
def delete_food(food_id):
    conn = get_db_connection()

    try:
        food = conn.execute(
            "SELECT id FROM foods WHERE id = ?",
            (food_id,)
        ).fetchone()

        if not food:
            abort(404)

        # Keep order history; remove food from availability.
        conn.execute("""
            UPDATE foods
            SET available = 0
            WHERE id = ?
        """, (food_id,))

        conn.commit()

        flash(
            "Food item removed from the menu.",
            "success"
        )

    finally:
        conn.close()

    return redirect(url_for("admin_foods"))



# ==================================================
# ADMIN CUSTOMER MANAGEMENT
# ==================================================


@app.route("/admin/customers")
@admin_required
def customers():
    conn = get_db_connection()

    try:
        customer_list = conn.execute("""
            SELECT id, name, email, phone, address
            FROM customers
            ORDER BY id DESC
        """).fetchall()

        return render_template(
            "customers.html",
            customers=customer_list
        )

    finally:
        conn.close()



# ==================================================
# RIDER MANAGEMENT
# ==================================================

@app.route("/admin/riders", methods=["GET", "POST"])
@admin_required
def rider_management():
    conn = get_db_connection()

    try:
        if request.method == "POST":
            name = request.form.get(
                "name", ""
            ).strip()

            phone = request.form.get(
                "phone", ""
            ).strip()

            if not name:
                flash("Enter the rider's name.", "danger")
                return redirect(
                    url_for("rider_management")
                )

            conn.execute("""
                INSERT INTO riders (name, phone)
                VALUES (?, ?)
            """, (name, phone))

            conn.commit()

            flash("Rider added.", "success")

            return redirect(
                url_for("rider_management")
            )

        riders = conn.execute("""
            SELECT *
            FROM riders
            ORDER BY id DESC
        """).fetchall()

        return render_template(
            "rider_dashboard.html",
            riders=riders
        )

    finally:
        conn.close()



@app.route("/admin/order/<int:order_id>/assign-rider", methods=["POST"])
@admin_required
def assign_rider(order_id):
    rider_id = request.form.get("rider_id")

    if not rider_id:
        flash("Please select a rider.", "warning")
        return redirect(url_for("admin_orders"))

    conn = get_db_connection()

    try:
        rider = conn.execute(
            "SELECT id FROM riders WHERE id = ?",
            (rider_id,)
        ).fetchone()

        order = conn.execute(
            "SELECT id FROM orders WHERE id = ?",
            (order_id,)
        ).fetchone()

        if not rider or not order:
            flash("Order or rider not found.", "danger")
            return redirect(url_for("admin_orders"))

        conn.execute("""
            UPDATE orders
            SET rider_id = ?
            WHERE id = ?
        """, (rider_id, order_id))

        conn.commit()

        flash("Rider assigned to order.", "success")

    except Exception:
        conn.rollback()
        flash("Unable to assign rider. Please try again.", "danger")

    finally:
        conn.close()

    return redirect(url_for("admin_orders"))


@app.route("/rider")
@admin_required
def rider_dashboard():
    conn = get_db_connection()

    try:
        rider_orders = conn.execute("""
            SELECT orders.*,
                   customers.name AS customer_name,
                   riders.name AS rider_name
            FROM orders
            JOIN customers
              ON customers.id = orders.customer_id
            LEFT JOIN riders
              ON riders.id = orders.rider_id
            WHERE orders.rider_id IS NOT NULL
            ORDER BY orders.id DESC
        """).fetchall()

        return render_template(
            "rider_dashboard.html",
            orders=rider_orders,
            rider_view=True,
            statuses=ORDER_STATUSES
        )

    finally:
        conn.close()


# ==================================================
# START APPLICATION
# ==================================================

if __name__ == "__main__":
    setup_database()
    app.run(debug=True)
