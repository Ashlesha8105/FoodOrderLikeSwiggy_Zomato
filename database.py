
import sqlite3
from werkzeug.security import generate_password_hash

DATABASE = "foodorder.db"


# --------------------------------------------------
# Database Connection
# --------------------------------------------------
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# --------------------------------------------------
# Create Tables and Update Existing Database
# --------------------------------------------------
def create_tables():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Customers
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                phone TEXT,
                address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Admin accounts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        """)

        # Food items
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS foods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                image TEXT,
                category TEXT,
                available INTEGER DEFAULT 1
            )
        """)

        # Delivery riders
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS riders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                available INTEGER DEFAULT 1
            )
        """)

        # Orders
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                total_amount REAL NOT NULL DEFAULT 0,
                payment_method TEXT NOT NULL DEFAULT 'Cash',
                payment_status TEXT DEFAULT 'Pending',
                order_status TEXT DEFAULT 'New Order',
                delivery_address TEXT NOT NULL DEFAULT '',
                rider_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers(id),
                FOREIGN KEY (rider_id) REFERENCES riders(id)
            )
        """)

        # Order items
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                food_id INTEGER,
                food_name TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (order_id) REFERENCES orders(id),
                FOREIGN KEY (food_id) REFERENCES foods(id)
            )
        """)

        # Payments
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                payment_method TEXT NOT NULL,
                amount REAL NOT NULL,
                transaction_id TEXT DEFAULT '',
                payment_status TEXT DEFAULT 'Pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(id)
            )
        """)

        # --------------------------------------------------
        # Migrate Existing Orders Table
        # Add missing columns only
        # --------------------------------------------------
        cursor.execute("PRAGMA table_info(orders)")
        order_columns = {
            row["name"] for row in cursor.fetchall()
        }

        if "total_amount" not in order_columns:
            cursor.execute("""
                ALTER TABLE orders
                ADD COLUMN total_amount REAL NOT NULL DEFAULT 0
            """)

        if "payment_method" not in order_columns:
            cursor.execute("""
                ALTER TABLE orders
                ADD COLUMN payment_method TEXT NOT NULL DEFAULT 'Cash'
            """)

        if "payment_status" not in order_columns:
            cursor.execute("""
                ALTER TABLE orders
                ADD COLUMN payment_status TEXT DEFAULT 'Pending'
            """)

        if "order_status" not in order_columns:
            cursor.execute("""
                ALTER TABLE orders
                ADD COLUMN order_status TEXT DEFAULT 'New Order'
            """)

        if "delivery_address" not in order_columns:
            cursor.execute("""
                ALTER TABLE orders
                ADD COLUMN delivery_address TEXT NOT NULL DEFAULT ''
            """)

        if "rider_id" not in order_columns:
            cursor.execute("""
                ALTER TABLE orders
                ADD COLUMN rider_id INTEGER
            """)

        # --------------------------------------------------
        # Migrate Existing Order Items Table
        # --------------------------------------------------
        cursor.execute("PRAGMA table_info(order_items)")
        item_columns = {
            row["name"] for row in cursor.fetchall()
        }

        if "food_id" not in item_columns:
            cursor.execute("""
                ALTER TABLE order_items
                ADD COLUMN food_id INTEGER
            """)

        if "food_name" not in item_columns:
            cursor.execute("""
                ALTER TABLE order_items
                ADD COLUMN food_name TEXT NOT NULL DEFAULT ''
            """)

        if "price" not in item_columns:
            cursor.execute("""
                ALTER TABLE order_items
                ADD COLUMN price REAL NOT NULL DEFAULT 0
            """)

        if "quantity" not in item_columns:
            cursor.execute("""
                ALTER TABLE order_items
                ADD COLUMN quantity INTEGER NOT NULL DEFAULT 1
            """)

        # --------------------------------------------------
        # Migrate Existing Payments Table
        # --------------------------------------------------
        cursor.execute("PRAGMA table_info(payments)")
        payment_columns = {
            row["name"] for row in cursor.fetchall()
        }

        if "transaction_id" not in payment_columns:
            cursor.execute("""
                ALTER TABLE payments
                ADD COLUMN transaction_id TEXT DEFAULT ''
            """)

        if "payment_status" not in payment_columns:
            cursor.execute("""
                ALTER TABLE payments
                ADD COLUMN payment_status TEXT DEFAULT 'Pending'
            """)

        # --------------------------------------------------
        # Indexes
        # --------------------------------------------------
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_customer
            ON orders(customer_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_status
            ON orders(order_status)
        """)

        # --------------------------------------------------
        # Default Admin Account
        # Create only if it does not already exist
        # --------------------------------------------------
        cursor.execute(
            "SELECT id FROM admins WHERE username = ?",
            ("admin",)
        )

        if cursor.fetchone() is None:
            cursor.execute("""
                INSERT INTO admins (username, password)
                VALUES (?, ?)
            """, (
                "admin",
                generate_password_hash("ChangeMe123!")
            ))

        conn.commit()
        print("Database tables and migrations completed successfully!")

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# --------------------------------------------------
# Add Sample Food Items
# --------------------------------------------------
def seed_foods():
    conn = get_db_connection()
    cursor = conn.cursor()

    new_foods = [
        # Indian
        (
            "Veg Biryani",
            "Aromatic vegetable biryani",
            149,
            "https://images.unsplash.com/photo-1589302168068-964664d93dc0",
            "Indian",
            1
        ),

        # Chinese
        (
            "Veg Hakka Noodles",
            "Stir-fried noodles with fresh vegetables",
            160,
            "https://images.unsplash.com/photo-1585032226651-759b368d7246",
            "Chinese",
            1
        ),
        (
            "Veg Manchurian",
            "Vegetable balls in Manchurian sauce",
            180,
            "https://images.unsplash.com/photo-1512058564366-18510be2db19",
            "Chinese",
            1
        ),

        # Sandwiches
        (
            "Grilled Sandwich",
            "Grilled sandwich with vegetables and cheese",
            120,
            "https://images.unsplash.com/photo-1528735602780-2552fd46c7af",
            "Sandwiches",
            1
        ),
        (
            "Cheese Sandwich",
            "Toasted sandwich with melted cheese",
            140,
            "https://images.unsplash.com/photo-1528735602780-2552fd46c7af",
            "Sandwiches",
            1
        ),

        # Pasta
        (
            "White Sauce Pasta",
            "Creamy pasta with white sauce",
            220,
            "https://images.unsplash.com/photo-1473093295043-cdd812d0e601",
            "Pasta",
            1
        ),
        (
            "Red Sauce Pasta",
            "Pasta tossed in tangy tomato sauce",
            200,
            "https://images.unsplash.com/photo-1473093295043-cdd812d0e601",
            "Pasta",
            1
        ),

        # Thalis
        (
            "Punjabi Thali",
            "Indian meal with roti, vegetables and rice",
            250,
            "https://images.unsplash.com/photo-1546833999-b9f581a1996d",
            "Thalis",
            1
        ),
        (
            "Veg Thali",
            "Traditional vegetarian Indian meal",
            180,
            "https://images.unsplash.com/photo-1546833999-b9f581a1996d",
            "Thalis",
            1
        ),

        # Beverages
        (
            "Cold Coffee",
            "Chilled coffee drink",
            100,
            "https://images.unsplash.com/photo-1461023058943-07fcbe16d735",
            "Beverages",
            1
        ),
        (
            "Chocolate Milkshake",
            "Creamy chocolate milkshake",
            140,
            "https://images.unsplash.com/photo-1572490122747-3968b75cc699",
            "Beverages",
            1
        ),

        # Ice Cream
        (
            "Chocolate Ice Cream",
            "Rich chocolate ice cream",
            90,
            "https://images.unsplash.com/photo-1563805042-7684c019e1cb",
            "Ice Cream",
            1
        ),
        (
            "Vanilla Ice Cream",
            "Classic vanilla ice cream",
            80,
            "https://images.unsplash.com/photo-1563805042-7684c019e1cb",
            "Ice Cream",
            1
        ),
    ]

    try:
        for food in new_foods:
            exists = cursor.execute("""
                SELECT id
                FROM foods
                WHERE name = ? AND category = ?
                LIMIT 1
            """, (food[0], food[4])).fetchone()

            if exists is None:
                cursor.execute("""
                    INSERT INTO foods (
                        name,
                        description,
                        price,
                        image,
                        category,
                        available
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """, food)

            elif food[0] == "Veg Biryani":
                # Update the image of the existing Veg Biryani
                cursor.execute("""
                    UPDATE foods
                    SET image = ?
                    WHERE name = ? AND category = ?
                """, (food[3], food[0], food[4]))

        conn.commit()
        print("Food items added or updated successfully!")

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()




# --------------------------------------------------
# Run Database Setup
# --------------------------------------------------
if __name__ == "__main__":
    create_tables()
    seed_foods()
    print("Database setup is complete!")
