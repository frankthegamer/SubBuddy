# SubBuddy

A full-stack subscription management web application built with FastAPI and MySQL.

---

## Prerequisites

- [Python 3.12+](https://www.python.org/downloads/)
- [MySQL](https://dev.mysql.com/downloads/) (running locally)
- [Visual Studio Code](https://code.visualstudio.com/) (recommended)
- Windows with PowerShell

---

## Setup

### 1. Clone or Download the Repository

Download the repository as a ZIP from [https://github.com/frankthegamer/SubBuddy/](https://github.com/frankthegamer/SubBuddy/) via **Code > Download ZIP**, then extract it to your preferred location.

### 2. Configure Environment Variables

In the project root, open `.env.example` and set the `DB_PASS` field to your MySQL password:

```env
DB_PASS=your_mysql_password_here
```

Save the file as `.env` (remove the `.example` extension).

### 3. Run the Setup Script

Open the project folder in VS Code (**right-click > Open with Code**), then open a terminal (**Terminal > New Terminal**) and run:

```powershell
.\environment_setup_script.ps1
```

If prompted with a PowerShell execution policy warning, enter `r` to run once. When prompted whether your `.env` file is configured, enter `y`.

The script will:
- Create a Python virtual environment (`venv/`)
- Install all dependencies from `requirements.txt`
- Initialize the MySQL database via `setup.py`

### 4. Activate the Virtual Environment

```powershell
.\venv\Scripts\Activate.ps1
```

### 5. Start the Development Server

```powershell
uvicorn main:app --reload
```

The application will be available at [http://127.0.0.1:8000](http://127.0.0.1:8000).

---

## Default Credentials

A seeded admin account is available on first run:

| Field    | Value               |
|----------|---------------------|
| Email    | admin@subbuddy.com  |
| Password | admin123            |

Non-admin accounts can be registered through the UI.

---

## Project Structure

```
SubBuddy/
├── app/
│   ├── database/
│   │   └── setup.py              # DB initialization, table creation, and admin seeding
│   └── main.py                   # App entry point, all FastAPI route definitions
├── static/
│   ├── css/
│   │   └── shared.css            # Global styles shared across all pages
│   └── js/
│       ├── admin.js              # Modal logic and actions for system admin page
│       ├── dashboard.js          # Subscription card interactions and dashboard logic
│       └── login.js              # Login/register form handling
├── templates/
│   ├── admin.html                # System admin UI (user search, family management)
│   ├── dashboard.html            # Main user dashboard (subscriptions, payments)
│   ├── family.html               # Family manager UI (members, spending limit)
│   └── login.html                # Login and registration page
├── venv/                         # Virtual environment (excluded from submission)
├── .env                          # DB credentials — do not commit
├── .gitignore
├── environment_setup_script.ps1  # PowerShell setup script for Windows
└── requirements.txt              # Python package dependencies
```

---

## Tech Stack

| Layer    | Technology                        |
|----------|-----------------------------------|
| Backend  | FastAPI, Python 3.12, Uvicorn     |
| Database | MySQL                             |
| Frontend | Jinja2 templates, Vanilla JS/CSS  |
| Other    | `python-dateutil`, `python-dotenv`|
