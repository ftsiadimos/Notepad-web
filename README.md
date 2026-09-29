# Notepad Web

A modern, feature-rich web-based note-taking application built with Flask and SQLAlchemy. Create, edit, search, and export your notes with ease.

## ✨ Features

- **Rich Text Editing**: Full-featured WYSIWYG editor with formatting options (bold, italic, lists, headings, etc.)
- **Format Stripping**: One-click button to remove all HTML formatting and get clean plain text
- **Search & Filter**: Real-time search across all your notes by title and content
- **Multiple Views**: Toggle between grid and list view layouts (preference saved locally)
- **PDF Export**: 
  - Export individual notes as PDF
  - Export all notes as a single PDF with proper formatting
  - Automatically strips HTML tags from rich text
- **AI Writing Assistant**:
  - Configure your Ollama API URL in Settings
  - Ask AI to summarize, rewrite, or expand note content
  - Insert generated suggestions directly into your note editor
- **Responsive Design**: Beautiful UI that works seamlessly on desktop, tablet, and mobile
- **Fast & Lightweight**: Built with Flask and SQLite for optimal performance
- **Error Handling**: Comprehensive error handling with user-friendly error pages
- **Data Validation**: Input validation and sanitization for security

## 🛠️ Technical Stack

- **Backend**: Flask 3.1+
- **Database**: SQLAlchemy 3.1+ with SQLite
- **Rich Text Editor**: Quill 2.0.3
- **PDF Generation**: ReportLab 4.4+
- **Frontend**: HTML5, CSS3, Vanilla JavaScript

## 📋 Requirements

- Python 3.8 or higher
- pip (Python package manager)

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone <repository-url>
cd notepad-web
```

### 2. Create Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
# On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Application
```bash
python run.py
```

Visit `http://127.0.0.1:5000` in your browser.

## ⚙️ Configuration

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

**Available configuration options:**

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask session secret key | `dev-secret-key-change-in-production` |
| `DATABASE_URL` | Database URI | `sqlite:///notepad.db` |
| `OLLAMA_API_URL` | Default Ollama API base URL | `http://localhost:11434` |
| `OLLAMA_MODEL` | Default Ollama model name | `llama3.2` |
| `FLASK_DEBUG` | Enable debug mode | `True` |
| `PORT` | Server port | `5000` |

⚠️ **Important**: Change `SECRET_KEY` in production!

## 📖 Usage Guide

### Creating a Note
1. Click **+ New Note** in the header
2. Enter a title in the title field
3. Write your content in the rich text editor
4. Use the toolbar for formatting:
   - Headers (H1-H6)
   - Text styling (Bold, Italic, Underline, Strike)
   - Colors and backgrounds
   - Lists (ordered/unordered)
   - Blockquotes and code blocks
   - Links and images
5. Click **💾 Save Note**

### Editing a Note
1. Click **✏️ Edit** on any note card
2. Modify the title or content
3. Use **AI Note Assistant** below the editor for writing help
4. Click **💾 Save Note**
5. Use **Strip All Formatting** button to remove HTML tags

### AI Assistant Setup
1. Open **⚙ Settings** from the main page
2. Set your Ollama API URL (for local Ollama this is usually `http://localhost:11434`)
3. Optionally set a model name available in your Ollama instance
4. Open a note and use **AI Note Assistant** under the content editor

### Searching Notes
1. Type in the **Search notes...** box in the header
2. Results filter in real-time by title and content
3. Clear the search to see all notes again

### Exporting to PDF
- **Single Note**: Click **📄 PDF** button on a note card
- **All Notes**: Click **📄 Export All as PDF** to download all notes in one file

### Switching Views
- Click the **☰** toggle button to switch between:
  - **Grid View**: Card layout (default)
  - **List View**: Compact list layout
- Your preference is saved automatically

### Removing Formatting
1. Open a note for editing
2. Select the text you want to strip formatting from
3. Click the **Strip All Formatting** button in the toolbar
4. All HTML tags will be removed, leaving plain text

## 📁 Project Structure

```
notepad-web/
├── app.py                 # Flask app factory & configuration
├── models.py              # Database models (Note)
├── routes.py              # Route handlers & business logic
├── run.py                 # Application entry point
├── requirements.txt       # Python dependencies
├── .env.example           # Environment variables template
├── README.md              # This file
├── instance/
│   └── notepad.db         # SQLite database (auto-created)
├── static/
│   └── style.css          # Application stylesheet
└── templates/
    ├── index.html         # Main notes list page
    ├── note_form.html     # Note creation/editing page
    ├── 404.html           # 404 error page
    └── 500.html           # 500 error page
```

## 🔧 Advanced Usage

### Database Migrations
```bash
flask db init
flask db migrate -m "Description of changes"
flask db upgrade
```

### Running in Production
```bash
export FLASK_DEBUG=False
export SECRET_KEY="your-production-secret-key"
gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
```

### Resetting the Database
```bash
rm instance/notepad.db
python run.py
```

## 🐛 Troubleshooting

### "Port 5000 already in use"
**Linux/Mac:**
```bash
lsof -i :5000
kill -9 <PID>
```

**Windows:**
```cmd
netstat -ano | findstr :5000
taskkill /PID <PID> /F
```

### "ModuleNotFoundError: No module named 'X'"
```bash
pip install -r requirements.txt
```

### "Database is corrupted"
```bash
rm instance/notepad.db
python run.py  # Database will be recreated
```

## 📝 Recent Improvements (v1.1)

- ✅ Enhanced error handling with try-catch blocks in all routes
- ✅ HTML stripping for PDF exports (properly handles rich text)
- ✅ Input validation (title length limits, content validation)
- ✅ Improved configuration with environment variables
- ✅ Content preview truncation for notes list
- ✅ Better database initialization and recovery
- ✅ Custom 404 and 500 error pages
- ✅ Enhanced security (content length limits, secure SECRET_KEY handling)
- ✅ Better logging and debugging information

## 📖 API Reference

### Note Model
```python
class Note(db.Model):
    id: int
    title: str (max 200 chars)
    content: str (rich HTML text)
    created_at: datetime
    updated_at: datetime
    
    # Methods
    to_dict() -> dict
    get_preview(length=150) -> str
```

### Routes

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List all notes |
| GET | `/settings` | Show settings form |
| POST | `/settings` | Save app settings |
| GET | `/note/new` | Show create note form |
| POST | `/note/new` | Create new note |
| GET | `/note/<id>` | Show edit note form |
| POST | `/note/<id>` | Update note |
| POST | `/note/<id>/delete` | Delete note |
| POST | `/ai/chat` | Generate note-writing help from Ollama |
| GET | `/export/pdf` | Export all notes as PDF |
| GET | `/export/pdf/<id>` | Export single note as PDF |

## 🤝 Contributing

Contributions are welcome! Here's how to contribute:

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is open source and available under the MIT License. See LICENSE file for details.

## 🙋 Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check existing issues for solutions
- Review the troubleshooting section above

## 🎯 Future Enhancements

Potential features for future versions:
- User authentication and multi-user support
- Cloud synchronization
- Tags and categories
- Note sharing
- Dark mode
- Rich text preview
- Note versioning/history
- Markdown support
- Mobile app
