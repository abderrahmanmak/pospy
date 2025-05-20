import tkinter as tk
from tkinter import ttk, messagebox
import psycopg2
from psycopg2 import sql
from decimal import Decimal
import os
from PIL import Image, ImageTk
import io

# --- Database Configuration ---
# IMPORTANT: Replace with your actual PostgreSQL connection details
DB_NAME = "pos_db"
DB_USER = "_pos_user"
DB_PASSWORD = "123"
DB_HOST = "localhost"  # Or your DB host
DB_PORT = "5432"      # Default PostgreSQL port

# Example mapping: filename (without extension) to (stock, price, barcode)
product_info = {
    "espresso": (50, 2.50, "1234567890123"),
    "latte macchiato": (30, 3.00, "1234567890124"),
    "cappucino": (20, 3.50, "1234567890125"),
    "espresso macchiato": (40, 2.00, "1234567890126"),
    "mocha": (25, 3.75, "1234567890127"),
    "macchiato": (15, 3.25, "1234567890128"),
    "caffe late": (10, 4.00, "1234567890129"),
    "cortado": (5, 4.50, "1234567890130"),
    "flat white": (8, 3.50, "1234567890131"),
    
}

pics_dir = os.path.join(os.path.dirname(__file__), "pics")

conn = psycopg2.connect(
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT
)
cur = conn.cursor()

for filename in os.listdir(pics_dir):
    if filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
        name = os.path.splitext(filename)[0]
        if name not in product_info:
            print(f"Skipping {filename}: no info in mapping.")
            continue
        stock, price, barcode = product_info[name]
        with open(os.path.join(pics_dir, filename), "rb") as f:
            photo_bytes = f.read()
        cur.execute(
            "INSERT INTO products (name, photo, stock, price, barcode) VALUES (%s, %s, %s, %s, %s)",
            (name, psycopg2.Binary(photo_bytes), stock, price, barcode)
        )
        print(f"Inserted {name}")

conn.commit()
cur.close()
conn.close()

class POSApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Python POS System")
        self.root.geometry("1000x700") # Adjusted size

        self.db_conn = None
        self.db_cursor = None
        self.connect_db()

        self.cart = [] # To store items added to the current sale {product_id, name, price, quantity}
        self.products_data = {} # To store product details fetched from DB {product_id: {name, price, stock}}
        self.current_user = None  # Store the currently logged-in user

        self._setup_styles()
        self._setup_ui()
        self.load_products()

    def _setup_styles(self, dark_mode=True):
        """Sets up modern dark styles for ttk widgets."""
        style = ttk.Style()
        style.theme_use('clam')

        # Dark mode palette (now the only mode)
        beige = "#232323"
        navbar_bg = "#2d2d2d"
        accent = "#3399ff"
        success = "#28a745"
        danger = "#dc3545"
        card_bg = "#282828"
        entry_bg = "#333333"
        nav_active_bg = "#444444"
        nav_active_border = "#3399ff"
        fg = "#f5f5dc"
        heading_fg = "#ffffff"

        # General backgrounds
        style.configure("TFrame", background=beige)
        style.configure("TLabel", background=beige, foreground=fg, font=("Segoe UI", 12))
        style.configure("TButton", font=("Segoe UI", 12, "bold"), padding=10, borderwidth=0, relief="flat", background=card_bg, foreground=fg)
        style.configure("Accent.TButton", foreground="white", background=accent)
        style.configure("Success.TButton", foreground="white", background=success)
        style.configure("Danger.TButton", foreground="white", background=danger)
        style.configure("TEntry", fieldbackground=entry_bg, background=entry_bg, relief="flat", foreground=fg)
        style.configure("Treeview.Heading", font=("Segoe UI", 12, "bold"), background=accent, foreground=heading_fg)
        style.configure("Treeview", font=("Segoe UI", 11), rowheight=28, background=card_bg, fieldbackground=card_bg, borderwidth=0, foreground=fg)
        # Navbar
        style.configure("Navbar.TFrame", background=navbar_bg)
        style.configure("Navbar.TButton", background=navbar_bg, foreground=fg, font=("Segoe UI", 12, "bold"), borderwidth=0, relief="flat")
        style.map("Navbar.TButton", background=[("active", nav_active_bg)])
        style.configure("Navbar.Active.TButton",
                        background=nav_active_bg,
                        foreground=fg,
                        borderwidth=2,
                        relief="solid",
                        bordercolor=nav_active_border)
        self.root.configure(bg=beige)

    def toggle_theme(self):
        """No-op: Only dark mode is available."""
        pass

    def connect_db(self):
        """Establishes connection to the PostgreSQL database."""
        try:
            self.db_conn = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                port=DB_PORT
            )
            self.db_cursor = self.db_conn.cursor()
            print("Successfully connected to PostgreSQL database.")
        except psycopg2.Error as e:
            messagebox.showerror("Database Connection Error", f"Could not connect to database: {e}\nPlease check your connection details and ensure PostgreSQL is running.")
            self.root.quit() # Exit if DB connection fails

    def _setup_ui(self):
        """Creates the main UI layout."""

        # Main frame
        main_frame = ttk.Frame(self.root, padding="10 10 10 10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Navbar (Right Side) ---
        self.navbar = ttk.Frame(main_frame, padding="20 30 20 30", style="Navbar.TFrame")
        self.navbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

        # Store nav button references for later show/hide
        self.nav_buttons = {}

        nav_buttons = [
            ("Menu", self.show_menu_page),
            ("Order", self.show_order_page),
            ("Stock", self.show_stock_page),
            ("Login", self.show_settings_page),
            ("Logout", self.logout),
        ]
        for text, command in nav_buttons:
            btn = ttk.Button(self.navbar, text=text, command=command, style="Navbar.TButton")
            if text == "Logout":
                self.nav_buttons[text] = btn
            else:
                btn.pack(fill=tk.X, pady=12, ipadx=10, ipady=12)
                self.nav_buttons[text] = btn

        # Hide Menu, Order, Stock buttons initially
        for key in ("Menu", "Order", "Stock"):
            self.nav_buttons[key].pack_forget()

        # Add user label at the bottom of the navbar
        self.user_label = ttk.Label(self.navbar, text="", font=("Segoe UI", 11, "italic"), style="TLabel")
        self.user_label.pack(side=tk.BOTTOM, pady=(30, 0), anchor="s")

        # --- Content Area (Pages) ---
        self.pages = {}
        self.content_frame = ttk.Frame(main_frame)
        self.content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Menu Page
        menu_page = ttk.Frame(self.content_frame)
        self.pages["menu"] = menu_page
        self._setup_menu_page(menu_page)

        # Order Page (Cart and Checkout only)
        order_page = ttk.Frame(self.content_frame)
        self.pages["order"] = order_page
        # --- Right Panel: Cart and Checkout ---
        right_panel = ttk.Frame(order_page, padding="10")
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)

        ttk.Label(right_panel, text="Current Sale", font=("Arial", 16, "bold")).pack(pady=(0,10))

        cart_cols = ("name", "size", "state", "sugar", "price", "quantity", "subtotal")
        self.cart_tree = ttk.Treeview(right_panel, columns=cart_cols, show="headings")
        for col in cart_cols:
            self.cart_tree.heading(col, text=col.capitalize())
            if col == "name":
                self.cart_tree.column(col, width=150, anchor=tk.W)
            elif col in ("size", "state", "sugar"):
                self.cart_tree.column(col, width=80, anchor=tk.CENTER)
            else:
                self.cart_tree.column(col, width=100, anchor=tk.CENTER)
        self.cart_tree.pack(fill=tk.BOTH, expand=True, pady=5)

        remove_button = ttk.Button(right_panel, text="Remove Selected", command=self.remove_from_cart, style="Danger.TButton")
        remove_button.pack(pady=5, fill=tk.X)

        total_frame = ttk.Frame(right_panel, padding="5")
        total_frame.pack(fill=tk.X, pady=10)
        ttk.Label(total_frame, text="Total:", font=("Arial", 14, "bold")).pack(side=tk.LEFT)
        self.total_amount_var = tk.StringVar(value="0.00")
        ttk.Label(total_frame, textvariable=self.total_amount_var, font=("Arial", 14, "bold")).pack(side=tk.RIGHT)

        checkout_button = ttk.Button(right_panel, text="Checkout", command=self.checkout, style="Success.TButton")
        checkout_button.pack(fill=tk.X, pady=10, ipady=5)

        # Stock Page (move Available Products here)
        stock_page = ttk.Frame(self.content_frame)
        self.pages["stock"] = stock_page

        ttk.Label(stock_page, text="Available Products", font=("Arial", 16, "bold")).pack(pady=(0,10))

        # --- Refresh Button ---
        refresh_btn = ttk.Button(stock_page, text="Refresh", command=lambda: self.load_products(self.search_var.get()))
        refresh_btn.pack(pady=(0, 5), anchor="e", padx=10)

        search_frame = ttk.Frame(stock_page)
        search_frame.pack(fill=tk.X, pady=5)
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0,5))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.filter_products)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)

        # Only show name and price columns in the stock page
        cols = ("name", "price")
        self.product_tree = ttk.Treeview(stock_page, columns=cols, show="headings", selectmode="browse")
        for col in cols:
            self.product_tree.heading(col, text=col.capitalize())
            self.product_tree.column(col, width=200 if col == "name" else 100, anchor=tk.W if col == "name" else tk.CENTER)
        self.product_tree.pack(fill=tk.BOTH, expand=True, pady=5)
        self.product_tree.bind("<<TreeviewSelect>>", self.on_product_select)

        # History Page
        history_page = ttk.Frame(self.content_frame)
        self.pages["history"] = history_page
        self._setup_history_page(history_page)

        # Settings Page
        settings_page = ttk.Frame(self.content_frame)
        self.pages["settings"] = settings_page
        self._setup_settings_page(settings_page)

        # Show Login page by default
        self.show_page("settings")

    def show_history_page(self):
        self.show_page("history")

    def _setup_history_page(self, parent):
        """Sets up the history page to display past checkouts."""
        for widget in parent.winfo_children():
            widget.destroy()

        ttk.Label(parent, text="Checkout History", font=("Segoe UI", 18, "bold")).pack(pady=20)

        cols = ("date", "items", "total")
        history_tree = ttk.Treeview(parent, columns=cols, show="headings", selectmode="browse")
        for col in cols:
            history_tree.heading(col, text=col.capitalize())
            history_tree.column(col, width=200 if col == "items" else 120, anchor=tk.W if col == "items" else tk.CENTER)
        history_tree.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)

        # Load history from the database
        try:
            self.db_cursor.execute("""
                SELECT date, items, total FROM history
                ORDER BY date DESC
            """)
            for row in self.db_cursor.fetchall():
                date, items, total = row
                history_tree.insert("", tk.END, values=(date.strftime("%Y-%m-%d %H:%M"), items, f"{total:.2f}"))
        except Exception as e:
            ttk.Label(parent, text=f"Could not load history: {e}", foreground="red").pack(pady=10)

    def logout(self):
        """Logs out the user and returns to the login page."""
        # Hide Menu, Order, Stock, and Logout buttons
        for key in ("Menu", "Order", "Stock", "Logout"):
            self.nav_buttons[key].pack_forget()
        # Show Login button
        self.nav_buttons["Login"].pack(fill=tk.X, pady=8, ipadx=10, ipady=8)
        # Clear login fields
        if hasattr(self, "user_id_var"):
            self.user_id_var.set("")
        if hasattr(self, "password_var"):
            self.password_var.set("")
        # Clear current user and update label
        self.current_user = None
        self.update_user_label()
        # Go back to login page
        self.show_settings_page()

    def update_user_label(self):
        """Updates the user label at the bottom of the navbar."""
        if self.current_user:
            self.user_label.config(text=f"User: {self.current_user}")
        else:
            self.user_label.config(text="")

    def _setup_menu_page(self, parent):
        # Fetch products with images from the database, removing duplicates by name
        self.db_cursor.execute("SELECT id, name, photo FROM products WHERE stock > 0 ORDER BY name ASC")
        products = self.db_cursor.fetchall()

        # Remove duplicates by name (keep first occurrence)
        seen_names = set()
        unique_products = []
        for prod in products:
            if prod[1] not in seen_names:
                unique_products.append(prod)
                seen_names.add(prod[1])

        if not unique_products:
            ttk.Label(parent, text="No products found.", font=("Arial", 16)).pack(pady=30)
            return

        grid_frame = ttk.Frame(parent)
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=20)

        row = 0
        col = 0
        max_cols = 4
        self.menu_images_refs = []

        for product_id, name, photo_bytes in unique_products:
            try:
                image = Image.open(io.BytesIO(photo_bytes)).resize((130, 130), Image.LANCZOS)
                photo = ImageTk.PhotoImage(image)
                self.menu_images_refs.append(photo)

                frame = ttk.Frame(grid_frame, padding=10)
                frame.grid(row=row, column=col, padx=20, pady=20, sticky="nsew")

                label = ttk.Label(frame, image=photo)
                label.pack()
                ttk.Label(frame, text=name).pack()

                btn = ttk.Button(frame, text="Select", command=lambda pid=product_id: self.menu_image_selected(pid))
                btn.pack(pady=8)

                grid_frame.grid_columnconfigure(col, weight=1)

                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1
            except Exception as e:
                print(f"Error loading image for {name}: {e}")

    def menu_image_selected(self, product_id):
        # Fetch product info from DB
        self.db_cursor.execute("SELECT name, price, stock, photo FROM products WHERE id = %s", (product_id,))
        result = self.db_cursor.fetchone()
        if not result:
            messagebox.showerror("Error", "Product not found.")
            return
        name, price, stock, photo_bytes = result

        # Create popup window
        popup = tk.Toplevel(self.root)
        popup.title(f"Customize {name}")
        popup.geometry("370x850")  # Increased height for better visibility
        popup.transient(self.root)
        popup.grab_set()
        popup.configure(bg="#232323")  # Dark mode background

        # Card-like frame for modern look
        card = ttk.Frame(popup, style="TFrame", padding="30 20 30 20")
        card.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)

        # Show product image
        try:
            image = Image.open(io.BytesIO(photo_bytes)).resize((130, 130), Image.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            label_img = ttk.Label(card, image=photo, background="#232323")
            label_img.image = photo  # Keep reference
            label_img.pack(pady=(0, 15))
        except Exception as e:
            ttk.Label(card, text="Image not available", background="#232323", foreground="#f5f5dc").pack(pady=(0, 15))

        # Show product name and price together
        ttk.Label(card, text=f"{name}   {price:.2f} €", font=("Segoe UI", 16, "bold"), background="#232323", foreground="#f5f5dc").pack(pady=(0, 18))

        # Size selection
        size_frame = ttk.LabelFrame(card, text="Size", padding=10, style="TFrame")
        size_frame.pack(fill=tk.X, padx=5, pady=7)
        size_var = tk.StringVar(value="Medium")
        for size in ["Small", "Medium", "Large"]:
            ttk.Radiobutton(size_frame, text=size, variable=size_var, value=size, style="TRadiobutton").pack(anchor=tk.W, padx=5, pady=2)

        # State selection
        state_frame = ttk.LabelFrame(card, text="State", padding=10, style="TFrame")
        state_frame.pack(fill=tk.X, padx=5, pady=7)
        state_var = tk.StringVar(value="Hot")
        for state in ["Hot", "Cold"]:
            ttk.Radiobutton(state_frame, text=state, variable=state_var, value=state, style="TRadiobutton").pack(anchor=tk.W, padx=5, pady=2)

        # Sugar selection
        sugar_frame = ttk.LabelFrame(card, text="Sugar", padding=10, style="TFrame")
        sugar_frame.pack(fill=tk.X, padx=5, pady=7)
        sugar_var = tk.StringVar(value="Normal")
        for sugar in ["No Sugar", "Less", "Normal", "Extra"]:
            ttk.Radiobutton(sugar_frame, text=sugar, variable=sugar_var, value=sugar, style="TRadiobutton").pack(anchor=tk.W, padx=5, pady=2)

        # Spacer to push the button to the bottom (make it dark)
        spacer = tk.Label(card, bg="#232323")
        spacer.pack(expand=True, fill=tk.BOTH)

        # Confirm button at the bottom
        def confirm_and_add_to_cart():
            # Compose a unique name for the customized product
            custom_name = name
            custom_size = size_var.get()
            custom_state = state_var.get()
            custom_sugar = sugar_var.get()
            # Check if already in cart (by all custom fields)
            for item in self.cart:
                if (
                    item["product_id"] == product_id and
                    item.get("size") == custom_size and
                    item.get("state") == custom_state and
                    item.get("sugar") == custom_sugar
                ):
                    item["quantity"] += 1
                    break
            else:
                self.cart.append({
                    "product_id": product_id,
                    "name": custom_name,
                    "size": custom_size,
                    "state": custom_state,
                    "sugar": custom_sugar,
                    "price": price,
                    "quantity": 1
                })
            self.update_cart_display()
            self.update_total_amount()
            popup.destroy()

        confirm_btn = ttk.Button(card, text="Confirm", command=confirm_and_add_to_cart, style="Accent.TButton")
        confirm_btn.pack(pady=20, side=tk.BOTTOM, fill=tk.X)

    def show_page(self, page_name):
        """Show the requested page and hide others. Also highlight the active navbar button."""
        self.current_page = page_name
        for name, frame in self.pages.items():
            frame.pack_forget()
        self.pages[page_name].pack(fill=tk.BOTH, expand=True)
        nav_map = {
            "menu": "Menu",
            "order": "Order",
            "stock": "Stock",
            "settings": "Login"
        }
        for key, btn in self.nav_buttons.items():
            if key == nav_map.get(page_name, ""):
                btn.configure(style="Navbar.Active.TButton")
            else:
                btn.configure(style="Navbar.TButton")

    def show_menu_page(self):
        self.show_page("menu")

    def show_order_page(self):
        self.show_page("order")

    def show_stock_page(self):
        self.show_page("stock")

    def show_settings_page(self):
        self.show_page("settings")

    def load_products(self, search_term=""):
        """Loads products from the database into the product_tree, removing duplicates by name."""
        if not self.db_cursor:
            messagebox.showerror("Error", "Database not connected.")
            return

        for i in self.product_tree.get_children():
            self.product_tree.delete(i)
        
        self.products_data.clear()

        try:
            query = "SELECT id, name, price, stock FROM products"
            params = []
            if search_term:
                query += " WHERE name ILIKE %s"
                params.append(f"%{search_term}%")
            query += " ORDER BY name ASC"
            
            self.db_cursor.execute(query, tuple(params))
            products = self.db_cursor.fetchall()

            # Remove duplicates by name (keep first occurrence)
            seen_names = set()
            unique_products = []
            for prod in products:
                if prod[1] not in seen_names:
                    unique_products.append(prod)
                    seen_names.add(prod[1])
            
            for prod in unique_products:
                product_id, name, price, stock = prod
                self.product_tree.insert("", tk.END, values=(name, f"{price:.2f}"))
                self.products_data[product_id] = {"name": name, "price": Decimal(str(price)), "stock": stock}
        except psycopg2.Error as e:
            messagebox.showerror("Database Error", f"Failed to load products: {e}")

    def filter_products(self, *args):
        """Filters products in the treeview based on search_var content."""
        search_term = self.search_var.get()
        self.load_products(search_term)

    def on_product_select(self, event):
        """Handles selection of a product in the product_tree (optional)."""
        selected_item = self.product_tree.focus() # Get selected item
        if selected_item:
            item_values = self.product_tree.item(selected_item, "values")
            # You could auto-fill quantity or display more product info here if needed
            # print(f"Selected product: {item_values}")
            pass

    def add_to_cart(self):
        """Adds the selected product to the cart."""
        selected_item_iid = self.product_tree.focus()
        if not selected_item_iid:
            messagebox.showwarning("No Selection", "Please select a product to add.")
            return

        item_values = self.product_tree.item(selected_item_iid, "values")
        product_id = int(item_values[0])
        
        if product_id not in self.products_data:
            messagebox.showerror("Error", "Selected product data not found.")
            return
            
        product = self.products_data[product_id]
        quantity_to_add = self.quantity_var.get()

        if quantity_to_add <= 0:
            messagebox.showwarning("Invalid Quantity", "Quantity must be greater than zero.")
            return

        if quantity_to_add > product["stock"]:
            messagebox.showwarning("Insufficient Stock", f"Only {product['stock']} units of {product['name']} available.")
            return

        # Check if product already in cart, if so, update quantity
        existing_cart_item = None
        for item in self.cart:
            # Also check for size, state, sugar for uniqueness if present
            if (
                item["product_id"] == product_id and
                item.get("size") is None and
                item.get("state") is None and
                item.get("sugar") is None
            ):
                existing_cart_item = item
                break
        
        if existing_cart_item:
            if existing_cart_item["quantity"] + quantity_to_add > product["stock"]:
                 messagebox.showwarning("Insufficient Stock", f"Cannot add {quantity_to_add} more. Total would exceed stock for {product['name']}.")
                 return
            existing_cart_item["quantity"] += quantity_to_add
        else:
            self.cart.append({
                "product_id": product_id,
                "name": product["name"],
                "size": None,
                "state": None,
                "sugar": None,
                "price": product["price"],
                "quantity": quantity_to_add
            })
        
        self.quantity_var.set(1) # Reset quantity spinbox
        self.update_cart_display()
        self.update_total_amount()

    def update_cart_display(self):
        """Updates the cart_tree display with current cart items, including size, state, sugar."""
        for i in self.cart_tree.get_children():
            self.cart_tree.delete(i)
        
        for item in self.cart:
            subtotal = item["price"] * item["quantity"]
            self.cart_tree.insert(
                "", tk.END,
                values=(
                    item['name'],
                    item.get('size', ''),
                    item.get('state', ''),
                    item.get('sugar', ''),
                    f"{item['price']:.2f}",
                    item["quantity"],
                    f"{subtotal:.2f}"
                )
            )

    def remove_from_cart(self):
        """Removes the selected item from the cart."""
        selected_item_iid = self.cart_tree.focus()
        if not selected_item_iid:
            messagebox.showwarning("No Selection", "Please select an item from the cart to remove.")
            return

        # Find the item in the self.cart list based on selection in treeview
        # This is a bit indirect; a better way would be to store cart item IDs or indices
        selected_values = self.cart_tree.item(selected_item_iid, "values")
        if not selected_values: return

        item_name_to_remove = selected_values[0]
        item_quantity_to_remove = int(selected_values[5]) # Assuming name and quantity make it unique enough for this example

        item_to_remove = None
        for item in self.cart:
            if item["name"] == item_name_to_remove and item["quantity"] == item_quantity_to_remove:
                # For simplicity, removing the first match. For identical items with different entries, this might need refinement.
                item_to_remove = item
                break
        
        if item_to_remove:
            self.cart.remove(item_to_remove)
            self.update_cart_display()
            self.update_total_amount()
        else:
            messagebox.showerror("Error", "Could not find the selected item in the cart data.")

    def update_total_amount(self):
        """Calculates and updates the total amount for the cart."""
        total = sum(item["price"] * item["quantity"] for item in self.cart)
        self.total_amount_var.set(f"{total:.2f}")

    def checkout(self):
        """Handles checkout: show a message, clear the cart, and update stock in the database and stock page."""
        if not self.cart:
            messagebox.showinfo("Empty Cart", "Cannot checkout with an empty cart.")
            return

        # Update stock in the database for each product in the cart
        for item in self.cart:
            product_id = item["product_id"]
            quantity = item["quantity"]
            if product_id in self.products_data and self.products_data[product_id]["stock"] is not None:
                self.db_cursor.execute(
                    "UPDATE products SET stock = GREATEST(stock - %s, 0) WHERE id = %s",
                    (quantity, product_id)
                )
                self.db_conn.commit()

        # Save checkout to history table
        try:
            import datetime
            items_str = "; ".join(
                f"{item['name']} x{item['quantity']}" +
                (f" [{item.get('size','')}/{item.get('state','')}/{item.get('sugar','')}]" if item.get('size') else "")
                for item in self.cart
            )
            total = sum(item["price"] * item["quantity"] for item in self.cart)
            self.db_cursor.execute(
                "INSERT INTO history (date, items, total) VALUES (%s, %s, %s)",
                (datetime.datetime.now(), items_str, total)
            )
            self.db_conn.commit()
        except Exception as e:
            messagebox.showerror("History Error", f"Could not save checkout history: {e}")

        # Refresh the stock page display (this reloads from DB)
        self.load_products(self.search_var.get())

        # Clear the cart and update UI
        self.cart.clear()
        self.update_cart_display()
        self.update_total_amount()
        messagebox.showinfo("Checkout Complete", "Checkout complete!")

    def on_closing(self):
        """Handles window close event."""
        if self.db_conn:
            self.db_conn.close()
            print("Database connection closed.")
        self.root.destroy()

    def _setup_settings_page(self, parent):
        """Sets up the login form in the settings page."""
        for widget in parent.winfo_children():
            widget.destroy()

        # Center the login card
        card = ttk.Frame(parent, style="TFrame", padding="40 30 40 30")
        card.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        ttk.Label(card, text="Login", font=("Segoe UI", 22, "bold")).pack(pady=(0, 25))

        form_frame = ttk.Frame(card, style="TFrame")
        form_frame.pack(pady=10)

        ttk.Label(form_frame, text="User ID:").grid(row=0, column=0, sticky=tk.E, padx=5, pady=10)
        self.user_id_var = tk.StringVar()
        user_id_entry = ttk.Entry(form_frame, textvariable=self.user_id_var, font=("Segoe UI", 12), width=22)
        user_id_entry.grid(row=0, column=1, padx=5, pady=10)

        ttk.Label(form_frame, text="Password:").grid(row=1, column=0, sticky=tk.E, padx=5, pady=10)
        self.password_var = tk.StringVar()
        password_entry = ttk.Entry(form_frame, textvariable=self.password_var, show="*", font=("Segoe UI", 12), width=22)
        password_entry.grid(row=1, column=1, padx=5, pady=10)

        user_id_entry.bind("<Return>", lambda event: attempt_login())
        password_entry.bind("<Return>", lambda event: attempt_login())

        def attempt_login():
            user_id = self.user_id_var.get()
            password = self.password_var.get()
            if not user_id or not password:
                messagebox.showwarning("Input Error", "Please enter both User ID and Password.")
                return
            try:
                self.db_cursor.execute(
                    "SELECT id FROM users WHERE id = %s AND password = %s",
                    (user_id, password)
                )
                result = self.db_cursor.fetchone()
                if result:
                    self.current_user = user_id  # Set current user
                    self.update_user_label()     # Update label in navbar
                    for key in ("Menu", "Order", "Stock"):
                        self.nav_buttons[key].pack(fill=tk.X, pady=12, ipadx=10, ipady=12)
                    self.nav_buttons["Login"].pack_forget()
                    self.nav_buttons["Logout"].pack(fill=tk.X, pady=12, ipadx=10, ipady=12)
                    self.show_menu_page()
                else:
                    messagebox.showerror("Login Failed", "Invalid User ID or Password.")
            except psycopg2.Error as e:
                messagebox.showerror("Database Error", f"Login failed: {e}")

        login_btn = ttk.Button(card, text="Login", command=attempt_login, style="Accent.TButton")
        login_btn.pack(pady=20, fill=tk.X)

if __name__ == "__main__":
    root = tk.Tk()
    try:
        root.state('zoomed')  # Works on Windows, some Linux
    except tk.TclError:
        root.attributes('-zoomed', True)  # Works on some Linux (like GNOME)
    app = POSApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing) # Handle window close gracefully
    root.mainloop()
