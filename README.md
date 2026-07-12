# AI Blog CMS

A production-ready Flask blog CMS with SQLAlchemy, Flask-Login, Bootstrap-inspired templates, and AI-assisted content features.

## Features
- User registration, login, logout, and remember me
- Post create/edit/delete with draft and publish state
- Categories, tags, comments, search, pagination
- SEO fields and basic sitemap/robots support
- Dashboard with counts

## Installation
1. Create and activate a Python 3.12+ virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the app:
   ```bash
   python app.py
   ```
4. Open http://127.0.0.1:5000/

## Notes
- The default database is SQLite.
- The app uses a single-file Flask implementation for a complete first iteration.
