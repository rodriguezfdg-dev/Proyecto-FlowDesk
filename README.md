# FlowDesk - Sistema de Gestión de Tickets

Sistema de gestión de tickets y actividades desarrollado con FastAPI (backend) y Flask (frontend).

## 🚀 Características

- Sistema de autenticación con JWT
- Gestión de tickets y actividades
- Panel de administración
- Sistema de notificaciones por email
- Tablero Kanban
- Reportes y estadísticas

## 📋 Requisitos Previos

- Python 3.13+
- MySQL/MariaDB
- pip (gestor de paquetes de Python)

## ⚙️ Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/rodriguezfdg-dev/Proyecto-FlowDesk.git
cd Proyecto-FlowDesk
```

### 2. Crear entorno virtual

```bash
python -m venv venv
```

### 3. Activar el entorno virtual

**Windows:**
```bash
venv\Scripts\activate
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### 4. Instalar dependencias

```bash
# Backend
pip install -r backend/requirements.txt

# Frontend
pip install -r flask_frontend/requirements.txt
```

### 5. Configurar variables de entorno

Copia el archivo de ejemplo y configura tus credenciales:

```bash
copy .env.example .env.local
```

Edita `.env.local` con tus configuraciones:

```env
# Configuración de Base de Datos
DB_USER=tu_usuario_mysql
DB_PASS=tu_contraseña_mysql
DB_HOST=localhost
DB_PORT=3306
DB_NAME=flowdesk

# Clave secreta para JWT (genera una segura)
SECRET_KEY=tu_clave_super_secreta_aqui
```

**⚠️ IMPORTANTE:** Genera una clave secreta segura con:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 6. Crear la base de datos

```sql
CREATE DATABASE flowdesk CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 7. Ejecutar la aplicación

**Backend (FastAPI):**
```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend (Flask):**
```bash
cd flask_frontend
python app.py
```

## 🌐 Acceso

- **Frontend:** http://localhost:5000
- **Backend API:** http://localhost:8000
- **Documentación API:** http://localhost:8000/docs

## 📁 Estructura del Proyecto

```
flowdesk/
├── backend/              # API FastAPI
│   ├── api/             # Endpoints de la API
│   ├── core/            # Funcionalidades core
│   ├── database.py      # Configuración de BD
│   ├── models.py        # Modelos SQLAlchemy
│   └── main.py          # Punto de entrada
├── flask_frontend/      # Aplicación Flask
│   ├── static/          # Archivos estáticos
│   ├── templates/       # Plantillas HTML
│   └── app.py           # Aplicación Flask
├── .env.example         # Ejemplo de configuración
└── .gitignore          # Archivos ignorados por Git
```

## 🔒 Seguridad

- **NUNCA** subas el archivo `.env.local` al repositorio
- Cambia la `SECRET_KEY` por defecto en producción
- Usa contraseñas seguras para la base de datos
- Mantén las dependencias actualizadas

## 👥 Roles de Usuario

- **Roll 1:** Administrador
- **Roll 2:** Cliente
- **Roll 3:** Desarrollador

## 📝 Licencia

Este proyecto es privado y de uso interno.

## 👨‍💻 Desarrollador

Francisco Rodriguez - [@rodriguezfdg-dev](https://github.com/rodriguezfdg-dev)
