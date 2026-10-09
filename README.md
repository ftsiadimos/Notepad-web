# Notepad Web

Notepad Web is a lightweight Flask application for writing, organizing, and exporting notes in a clean browser-based interface. It stores notes in SQLite, supports rich text editing, exports notes to PDF, and can optionally use Ollama to rewrite or improve note content.

## Features

- Rich-text editing with a WYSIWYG-style editor
- Create, update, and delete notes
- Search notes by title and content
- PDF export for a single note or the full notebook
- Persistent storage with SQLite
- Theme and app settings managed in the UI
- Optional AI writing assistance via Ollama
- Responsive layout for desktop and smaller screens
- Docker support for easy local deployment

## Tech stack

- Flask
- Flask-SQLAlchemy
- Flask-Migrate
- SQLite
- ReportLab for PDF generation
- HTML, CSS, and vanilla JavaScript for the frontend

## Requirements

- Python 3.10+
- pip
- Optional: an Ollama instance running locally for AI features

## Docker

### Pull the image

```bash
docker pull ghcr.io/ftsiadimos/notepad-web:latest
```

### Run the container

```bash
docker run -d \
  --name notepad-web \
  -p 5223:5223 \
  -v notepad-data:/app/instance \
  -e SECRET_KEY=change-me-in-production \
  ghcr.io/ftsiadimos/notepad-web:latest
```

The application will be available at:

```text
http://localhost:5223
```

**Volume mount:** `-v notepad-data:/app/instance` persists your SQLite database and settings across container restarts. Replace with a bind mount (e.g., `-v ./instance:/app/instance`) if you prefer host-mounted files.

### Build and run from source

```bash
docker compose up --build
```

Then open:

```text
http://localhost:5223
```

To stop it:

```bash
docker compose down
```

## Quick start

### 1. Clone the repository

```bash
git clone <repository-url>
cd notepad-web
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows:

```powershell
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Start the app

```bash
python run.py
```

The application runs by default on:

```text
http://localhost:5223
```

## Configuration

The app reads a few runtime settings from environment variables, and some app preferences are stored in the SQLite database through the Settings page.

### Environment variables

```bash
export FLASK_RUN_HOST=0.0.0.0
export FLASK_RUN_PORT=5223
export FLASK_DEBUG=False
export SECRET_KEY=change-me-in-production
export DATABASE_URL=sqlite:///notepad.db
```

You can also put these in a `.env` file if your workflow loads it automatically.

### Ollama settings

The app includes a Settings screen where you can configure:

- Ollama API URL
- Ollama model name
- Theme preference

If you are running Ollama locally, the default URL is usually:

```text
http://localhost:11434
```

## Usage

### Create a note

- Open the app in your browser
- Click the new note action in the interface
- Enter a title and note content
- Save the note

### Edit and delete notes

- Open an existing note from the list
- Update the title or content
- Save changes, or delete the note from the interface

### Search notes

- Use the search box from the main page to filter notes by title or content

### Export to PDF

- Export a single note from its card or edit view
- Export all notes from the main page

### Use the AI assistant

- Open the Settings page
- Point the app to your Ollama API
- Pick a model
- Open a note and use the AI helper to rewrite, expand, summarize, or improve the content

## Project structure

```text
notepad-web/
├── app.py
├── models.py
├── run.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── README.md
├── VERSION
├── instance/
├── routes/
│   ├── __init__.py
│   ├── ai.py
│   ├── api.py
│   ├── exports.py
│   ├── notes.py
│   └── settings.py
├── static/
│   └── style.css
├── templates/
│   ├── 404.html
│   ├── 500.html
│   ├── about.html
│   ├── index.html
│   ├── note_form.html
│   └── settings.html
└── utils/
    ├── __init__.py
    ├── helpers.py
    └── pdf.py
```

## Troubleshooting

### Port already in use

Check whether another service is using port 5223:

```bash
lsof -i :5223
```

If needed, stop the conflicting process or change the port with `FLASK_RUN_PORT`.

### Ollama connection errors

Confirm the Ollama API is reachable:

```bash
curl http://localhost:11434/api/tags
```

If this fails, make sure Ollama is running before using the AI assistant.

### Database issues

The database is created automatically in `instance/notepad.db` when the app starts. If you need a clean reset:

```bash
rm -f instance/notepad.db
python run.py
```

## Development notes

This project is intentionally simple and easy to extend:

- Note logic lives in `models.py`
- Routes are organized in the `routes/` directory (`notes.py`, `ai.py`, `api.py`, `exports.py`, `settings.py`)
- Utility functions live in `utils/` (`helpers.py`, `pdf.py`)
- App configuration is created in `app.py`
- The entry point is `run.py`

## License

This project is provided as-is for personal and educational use. If you want to add a license, it is recommended to use one appropriate for your deployment and distribution requirements.

