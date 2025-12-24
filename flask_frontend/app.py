import sys
import os

# Add the project root directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, redirect, url_for, session, request
from functools import wraps
import requests

app = Flask(__name__)
app.secret_key = os.urandom(24)

def get_api_base_url():
    # Use 127.0.0.1 for local development to ensure consistency
    return "http://127.0.0.1:8000"

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/', methods=['GET', 'POST'])
def login():
    api_base_url = get_api_base_url()
    if 'user' in session:
        # Redirect based on roll
        roll = session.get('roll')
        if roll in ('1', '3'):
            return redirect(url_for('desk'))
        elif roll == '2':
            return redirect(url_for('cliente'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        backend_login_url = f"{api_base_url}/api/token"
        
        try:
            # The backend expects form data for OAuth2PasswordRequestForm
            response = requests.post(backend_login_url, data={"username": email, "password": password})
            
            if response.status_code == 401:
                return render_template('login.html', error="Invalid credentials", api_base_url=api_base_url)
            
            response.raise_for_status()  # Raise an exception for other bad responses (4xx or 5xx)
            
            token_data = response.json()
            user_info = token_data.get('user_info', {})

            session['user'] = user_info.get('username')
            session['roll'] = user_info.get('roll')
            session['access_token'] = token_data.get('access_token')

            # Now that we are logged in, get user details including customer_code
            try:
                headers = {"Authorization": f"Bearer {session['access_token']}"}
                user_me_url = f"{api_base_url}/api/users/me"
                user_response = requests.get(user_me_url, headers=headers)
                user_response.raise_for_status()
                me_data = user_response.json()
                
                if me_data.get('customer_code'):
                    session['customer_code'] = me_data['customer_code']
                
                # Also, ensure the user is verified before proceeding
                if not me_data.get('is_verified'):
                    # Clear session and redirect to unverified page
                    session.clear()
                    return redirect(url_for('unverified'))

                # Check if the user has been activated by an admin (status == 1)
                # This check should only apply to non-admin users (e.g., roll '2' or others)
                if me_data.get('roll') != '1':
                    if me_data.get('status') != 1:
                        session.clear()
                        return redirect(url_for('pending_activation'))

            except requests.exceptions.RequestException as e:
                # Log out user if we can't get their details
                session.clear()
                return render_template('login.html', error="Could not retrieve user profile.", api_base_url=api_base_url)

            roll = user_info.get('roll')
            if roll in ('1', '3'):
                return redirect(url_for('desk'))
            elif roll == '2':
                return redirect(url_for('cliente'))
            else:
                # Fallback for users with no specific roll
                return redirect(url_for('desk'))

        except requests.exceptions.RequestException as e:
            print(f"Error connecting to authentication service: {e}")
            return render_template('login.html', error="Could not connect to authentication service.", api_base_url=api_base_url)

    return render_template('login.html', api_base_url=api_base_url)


@app.route('/desk')
@login_required
def desk():
    # Redirect to gallery view for Admins/Devs to select a client first
    return redirect(url_for('gallery'))

@app.route('/actividad')
@login_required
def actividad():
    ticket_id = request.args.get('id')
    logged_in_user = session.get('user', 'user_def') # Get logged in user from session
    if ticket_id:
        # We are viewing a ticket
        return render_template('detalle_ticket.html', ticket_id=ticket_id, logged_in_user=logged_in_user, api_base_url=get_api_base_url(), access_token=session.get('access_token'), user_roll=session.get('roll'))
    else:
        # We are creating a new ticket
        customer_code = session.get('customer_code', None)
        access_token = session.get('access_token')
        api_base_url = get_api_base_url()
        user_roll = session.get('roll', '2')
        return render_template('actividad.html', customer_code=customer_code, api_base_url=api_base_url, access_token=access_token, user_roll=user_roll)

@app.route('/editar_ticket')
@login_required
def editar_ticket():
    ticket_id = request.args.get('id')
    access_token = session.get('access_token')
    api_base_url = get_api_base_url()
    return render_template('editar_ticket.html', ticket_id=ticket_id, access_token=access_token, api_base_url=api_base_url)


@app.route('/cliente')
@login_required
def cliente():
    access_token = session.get('access_token')
    api_base_url = get_api_base_url()
    return render_template('cliente.html', access_token=access_token, api_base_url=api_base_url)

@app.route('/ticket_cliente')
@login_required
def ticket_cliente():
    cliente_code = request.args.get('cliente_code')
    access_token = session.get('access_token')
    api_base_url = get_api_base_url()
    # Render Kanban board filtered by client
    return render_template('kanban.html', cliente_code=cliente_code, access_token=access_token, api_base_url=api_base_url)

@app.route('/register', methods=['GET', 'POST'])
def register():
    api_base_url = get_api_base_url()
    if request.method == 'POST':
        user = request.form.get('user')
        gmail = request.form.get('gmail')
        password = request.form.get('password')

        registration_data = {
            "user": user,
            "gmail": gmail,
            "password": password
        }
        
        try:
            response = requests.post(f"{api_base_url}/api/register", json=registration_data)
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
            
            # If registration is successful, redirect to login with a success message
            return redirect(url_for('login', success="Registro exitoso. Por favor, verifica tu correo."))
        except requests.exceptions.RequestException as e:
            error_message = "Error en el registro."
            if response and response.json() and "detail" in response.json():
                error_message = response.json()["detail"]
            print(f"Error during registration: {e} - {error_message}")
            return render_template('register.html', error=error_message, api_base_url=api_base_url)

    return render_template('register.html', api_base_url=api_base_url)

@app.route('/verify')
def verify():
    return render_template('verify.html')

@app.route('/forgot_password')
def forgot_password():
    return render_template('forgot_password.html', api_base_url=get_api_base_url())

@app.route('/reset_password')
def reset_password():
    return render_template('reset_password.html', api_base_url=get_api_base_url())

@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('roll', None)
    session.pop('access_token', None)
    return redirect(url_for('login'))

@app.route('/unverified')
def unverified():
    return render_template('unverified.html')

@app.route('/pending-activation')
def pending_activation():
    return render_template('pending_activation.html')

@app.route('/clientes_new')
@login_required
def clientes_new():
    access_token = session.get('access_token')
    if not access_token:
        return redirect(url_for('login'))
    return render_template('clientes_new.html', access_token=access_token, api_base_url=get_api_base_url())

@app.route('/empresas')
@login_required
def empresas():
    access_token = session.get('access_token')
    if not access_token:
        return redirect(url_for('login'))
    return render_template('empresas.html', access_token=access_token, api_base_url=get_api_base_url())

@app.route('/crear_actividad')
@login_required
def crear_actividad():
    access_token = session.get('access_token')
    if not access_token:
        return redirect(url_for('login'))
    return render_template('crear_actividad.html', access_token=access_token, api_base_url=get_api_base_url())

@app.route('/mis_actividades')
@login_required
def mis_actividades():
    access_token = session.get('access_token')
    if not access_token:
        return redirect(url_for('login'))
    return render_template('mis_actividades.html', access_token=access_token, api_base_url=get_api_base_url())

@app.route('/actividad_detalle')
@login_required
def actividad_detalle():
    access_token = session.get('access_token')
    if not access_token:
        return redirect(url_for('login'))
    return render_template('actividad_detalle.html', access_token=access_token, api_base_url=get_api_base_url())

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    # Ensure the user is an administrator
    if session.get('roll') != '1':
        return redirect(url_for('desk')) # Or render a custom unauthorized template

    api_base_url = get_api_base_url()
    smtp_settings = None
    error = None
    success = None
    
    # Prepare headers for authenticated requests
    access_token = session.get('access_token')
    if not access_token:
        return redirect(url_for('login')) # Should not happen if @login_required works
    headers = {"Authorization": f"Bearer {access_token}"}

    if request.method == 'POST':
        # Handle form submission to update/create settings
        settings_data = {
            "host": request.form['host'],
            "port": int(request.form['port']),
            "username": request.form['username'],
            "password": request.form['password'],
            "use_tls": 'use_tls' in request.form,
            "use_ssl": 'use_ssl' in request.form
        }
        try:
            # Try to update first
            response = requests.put(f"{api_base_url}/settings/smtp", json=settings_data, headers=headers)
            if response.status_code == 404: # Not found, so create
                response = requests.post(f"{api_base_url}/settings/smtp", json=settings_data, headers=headers)
            
            # Handle auth errors specifically
            if response.status_code in [401, 403]:
                error = "Error de autorización. No tienes permiso para realizar esta acción."
            else:
                response.raise_for_status()
                success = "Configuración SMTP guardada con éxito."

        except requests.exceptions.RequestException as e:
            error = f"Error al guardar la configuración SMTP: {e}"
            if response and response.json():
                error += f" - {response.json().get('detail', '')}"

    # Fetch current settings for GET request or after POST
    try:
        response = requests.get(f"{api_base_url}/settings/smtp", headers=headers)
        
        if response.status_code in [401, 403]:
            error = "Error de autorización. No tienes permiso para ver esta configuración."
        elif response.status_code == 404:
            # Settings not found, which is fine for initial setup
            pass
        else:
            response.raise_for_status()
            smtp_settings = response.json()

    except requests.exceptions.RequestException as e:
        # Avoid overwriting more specific errors from the POST block
        if not error:
            error = f"Error al cargar la configuración SMTP: {e}"
            if response and response.json():
                error += f" - {response.json().get('detail', '')}"

    return render_template('settings.html', smtp_settings=smtp_settings, error=error, success=success, api_base_url=api_base_url, access_token=access_token)

@app.route('/gallery')
@login_required
def gallery():
    access_token = session.get('access_token')
    api_base_url = get_api_base_url()
    return render_template('gallery.html', access_token=access_token, api_base_url=api_base_url)

@app.route('/reports')
@login_required
def reports():
    access_token = session.get('access_token')
    api_base_url = get_api_base_url()
    return render_template('reports.html', access_token=access_token, api_base_url=api_base_url)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)