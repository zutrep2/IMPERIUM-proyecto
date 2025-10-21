from flask import Flask, render_template, request, redirect, url_for, session, send_file
import mysql.connector

# --- Configuración de Flask y Sesiones ---
app = Flask(__name__)
app.secret_key = 'una_clave_secreta_muy_fuerte' 

# --- Configuración de la Base de Datos (ajusta tus credenciales) ---
DB_CONFIG = {
    'host': 'localhost',             #  <-- Generalmente 'localhost'
    'user': 'root',         #  <-- **TU USUARIO DE MYSQL** (Ej: 'root')
    'password': 'billete10mil',  #  <-- **TU CONTRASEÑA DE MYSQL**
    'database': 'login'    #  <-- **EL NOMBRE DE LA BASE DE DATOS QUE CREASTE**
}

def get_db_connection():
    """Función para establecer la conexión a la DB."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"Error al conectar a la base de datos: {err}")
        return None
    
def get_dashboard_data_from_db(conn):
        
    "Obtiene datos REALES de la base de datos para llenar los widgets."
    
    cursor = conn.cursor(dictionary=True)
    
    # 1. Ventas del Día
    # Calcula la suma de las ventas de hoy
    query_sales = "SELECT SUM(amount) AS total_sales FROM sales WHERE DATE(sale_date) = CURDATE()"
    cursor.execute(query_sales)
    sales_result = cursor.fetchone()
    total_sales = sales_result['total_sales'] if sales_result['total_sales'] else 0.00 # Maneja si no hay ventas

    # 2. Usuarios Activos (Simulado, ya que "activos" puede ser complejo)
    # Aquí podríamos contar usuarios con alguna actividad reciente o simplemente el total de usuarios.
    # Para este ejemplo, contaremos el total de usuarios registrados en la tabla 'users'.
    query_active_users = "SELECT COUNT(*) AS active_users FROM users"
    cursor.execute(query_active_users)
    active_users_result = cursor.fetchone()
    active_users = active_users_result['active_users'] if active_users_result['active_users'] else 0


    # 3. Productos en Stock (Bajo Inventario)
    # Contará productos con stock menor o igual a un umbral (ej. 10)
    query_low_stock = "SELECT COUNT(*) AS low_stock_count FROM products WHERE stock <= 10"
    cursor.execute(query_low_stock)
    low_stock_result = cursor.fetchone()
    low_stock_count = low_stock_result['low_stock_count'] if low_stock_result['low_stock_count'] else 0

    cursor.close()
    
    return {
        'total_sales': f"${total_sales:,.2f}", # Formato de moneda
        'active_users': active_users,
        'low_stock_count': low_stock_count
 }

# 
@app.route('/dashboard')
def dashboard():
    """Página de acceso restringido y obtención de datos dinámicos."""
    if 'loggedin' not in session:
        return redirect(url_for('home')) # Proteger la ruta
    
    conn = get_db_connection()
    if not conn:
        return "Error de conexión a la base de datos.", 500

    try:
        # Obtener datos reales de los widgets de la DB
        dashboard_data = get_dashboard_data_from_db(conn)
    finally:
        conn.close() # Asegurarse de cerrar la conexión
        
    # Pasar el nombre de usuario y los datos del dashboard a la plantilla
    return render_template(
        'dashboard.html', 
        username=session['username'],
        sales=dashboard_data['total_sales'],
        active=dashboard_data['active_users'],
        stock=dashboard_data['low_stock_count']
    )

 # Para traer las imagenes
@app.route('/img/<filename>', methods=['GET', 'POST'])
def image(filename):
    return send_file('templates\\img\\'+filename, as_attachment=True)

# Para traer cualquier archivo
@app.route('/data/<uri_path>', methods=['GET', 'POST'])
def uri_path(uri_path):
    return render_template(uri_path)

    
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """Ruta para registrar nuevos usuarios en la base de datos."""
    message = None
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            
            # 1. Verificar si el usuario ya existe
            query_check = "SELECT * FROM users WHERE username = %s"
            cursor.execute(query_check, (username,))
            user_exists = cursor.fetchone()
            
            if user_exists:
                message = 'El nombre de usuario ya está registrado.'
            else:
                # 2. Insertar el nuevo usuario
                # ¡ADVERTENCIA DE SEGURIDAD! La contraseña se inserta en texto plano (como en tu SQL).
                # Para producción, usa HASHING (ej: bcrypt).
                query_insert = "INSERT INTO users (username, password) VALUES (%s, %s)"
                try:
                    cursor.execute(query_insert, (username, password))
                    conn.commit()
                    message = 'Registro exitoso. ¡Ahora puedes iniciar sesión!'
                    
                    # Opcional: Redirigir directamente al login después del éxito.
                    # return redirect(url_for('login')) 

                except mysql.connector.Error as err:
                    message = f"Error al registrar: {err}"
            
            cursor.close()
            conn.close()

    # Muestra el formulario de registro, con un mensaje si aplica.
    return render_template('signup.html', message=message)


@app.route('/edit_product', methods=['GET', 'POST'])
def edit_product():
    """Permite buscar un producto por ID, modificarlo, insertar uno nuevo y listar todos los productos."""
    if 'loggedin' not in session:
        return redirect(url_for('home')) 

    message = None
    product_data = None
    all_products = [] 
    
    # 1. Establecer conexión con la base de datos
    conn = get_db_connection()
    if not conn:
        # Aquí es mejor usar una plantilla de error o un mensaje más amigable
        message = "Error de conexión a la base de datos."
        return render_template('edit_product.html', message=message, product=None, products_list=[])

    cursor = conn.cursor(dictionary=True)
    
    # --- Lógica de POST (Buscar/Guardar/Insertar) ---
    if request.method == 'POST':
        action = request.form.get('action') 
        
        # --------------------------------------------------
        # LÓGICA: INSERTAR NUEVO PRODUCTO
        # --------------------------------------------------
        if action == 'Insertar':
            try:
                new_name = request.form.get('insert_name')
                new_price = request.form.get('insert_price')
                new_stock = request.form.get("insert_stock")
                
                # Validar campos básicos antes de insertar
                if not new_name or not new_price or not new_stock:
                    message = "Error: Todos los campos (Nombre, Precio, Stock) son obligatorios para la inserción."
                else:
                    # Consulta SQL para insertar datos
                    insert_query = "INSERT INTO products (name, price, stock) VALUES (%s, %s, %s)" 
                    cursor.execute(insert_query, (new_name, new_price, new_stock,))
                    conn.commit()
                    message = f"Producto '{new_name}' insertado con éxito."
            except mysql.connector.Error as err:
                message = f"Error al insertar el producto: {err}"
                conn.rollback()
            except Exception as e:
                message = f"Ocurrió un error inesperado durante la inserción: {e}"

        # --------------------------------------------------
        # LÓGICA: BUSCAR PRODUCTO
        # --------------------------------------------------
        elif action == 'Buscar':
            product_id = request.form.get('product_id_search')
            query = "SELECT * FROM products WHERE id = %s"
            cursor.execute(query, (product_id,))
            product_data = cursor.fetchone()
            if not product_data:
                message = f"Producto con ID {product_id} no encontrado."

        # --------------------------------------------------
        # LÓGICA: GUARDAR CAMBIOS (ACTUALIZAR)
        # --------------------------------------------------
        elif action == 'Guardar Cambios':
            product_id = request.form.get('product_id_edit')
            new_name = request.form.get('name')
            new_price = request.form.get('price')
            new_stock = request.form.get("stock")
            
            query = "UPDATE products SET name = %s, price = %s, stock = %s WHERE id = %s" 
            try:
                cursor.execute(query, (new_name, new_price, new_stock, product_id,))
                conn.commit()
                message = f"Producto ID {product_id} actualizado con éxito."
            except mysql.connector.Error as err:
                message = f"Error al actualizar: {err}"
                conn.rollback()
                
            # Re-buscar el producto para actualizar la vista (mantiene el formulario de edición abierto)
            query = "SELECT * FROM products WHERE id = %s"
            cursor.execute(query, (product_id,))
            product_data = cursor.fetchone()


    # --- Lógica GET y Consulta de Listado (SE EJECUTA SIEMPRE) ---
    
    # Consulta para obtener TODOS los productos
    query_all = "SELECT id, name, price, stock FROM products ORDER BY id DESC"
    cursor.execute(query_all)
    all_products = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    # 2. Renderiza la plantilla
    return render_template(
        'edit_product.html', 
        message=message, 
        product=product_data, 
        products_list=all_products
    )
    
@app.route('/products')
def products():
    """Muestra la lista de productos disponibles para el usuario común."""
    
    conn = get_db_connection()
    all_products = []
    
    if conn:
        cursor = conn.cursor(dictionary=True)
        # Asegúrate de que tu tabla products tenga estas columnas: id, name, price, stock
        query = "SELECT id, name, price, stock FROM products WHERE stock > 0 ORDER BY name ASC"
        
        try:
            cursor.execute(query)
            all_products = cursor.fetchall()
        except mysql.connector.Error as err:
            print(f"Error al obtener productos: {err}")
            # Puedes manejar el error aquí si es crítico
            
        cursor.close()
        conn.close()
    
    # Renderiza la nueva plantilla, pasando la lista de productos
    return render_template('products_new.html', products_list=all_products)



@app.route('/')
def home():
    """Ruta principal: Muestra la página de bienvenida (index.html)."""
    if 'loggedin' in session:
        # Si ya está logeado, va al dashboard
        return redirect(url_for('dashboard'))
        
    # Si no, muestra la página con los dos botones
    return render_template('index.html')

@app.route('/about')
def about():
    """Ruta principal: Muestra la página de bienvenida (index.html)."""
    if 'loggedin' in session:
        # Si ya está logeado, va al dashboard
        return redirect(url_for('dashboard'))
        
    # Si no, muestra la página con los dos botones
    return render_template('about.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Ruta del login: Muestra el formulario y procesa las credenciales."""
    error = None
    if request.method == 'POST':
        # 1. Obtener datos del formulario
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            
            # 2. Buscar el usuario en la base de datos (¡Recuerda usar hash en producción!)
            query = "SELECT * FROM users WHERE username = %s AND password = %s"
            cursor.execute(query, (username, password))
            user = cursor.fetchone()
            
            cursor.close()
            conn.close()

            # 3. Reacción: Éxito o Fracaso
            if user:
                session['loggedin'] = True
                session['id'] = user['id']
                session['username'] = user['username']
                return redirect(url_for('dashboard'))
            else:
                error = 'Usuario o contraseña incorrectos.'
        else:
             error = 'Error de conexión a la base de datos.'

    # Muestra el formulario de login.
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    """Cierra la sesión y redirige a la página principal."""
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('username', None)
    return redirect(url_for('home')) # Redirige a la página principal

if __name__ == '__main__':
    app.run(debug=True)

