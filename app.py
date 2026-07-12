"""Flask AI Blog CMS application entry point."""

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any

from flask import Flask, abort, flash, jsonify, redirect, render_template, render_template_string, request, send_from_directory, session, url_for
from werkzeug.utils import secure_filename
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash


class Config:
    """Application configuration for development and production."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///database.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")


app = Flask(__name__, template_folder="templates", static_folder="static")
app.config.from_object(Config)
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

app.config["WTF_CSRF_ENABLED"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


class User(db.Model, UserMixin):
    """Represents a blog user account."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    avatar = db.Column(db.String(255), nullable=True)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    remember_me = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    posts = db.relationship("Post", back_populates="author", cascade="all, delete-orphan")
    comments = db.relationship("Comment", back_populates="author", cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        """Hash and store a user password."""
        self.password_hash = generate_password_hash(password, method="pbkdf2:sha256")

    def check_password(self, password: str) -> bool:
        """Verify a supplied password against the stored hash."""
        return check_password_hash(self.password_hash, password)


class Category(db.Model):
    """Represents a post category."""

    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    posts = db.relationship("Post", back_populates="category")


class Tag(db.Model):
    """Represents a post tag."""

    __tablename__ = "tags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    posts = db.relationship("Post", secondary="post_tags", back_populates="tags")


post_tags = db.Table(
    "post_tags",
    db.Column("post_id", db.Integer, db.ForeignKey("posts.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tags.id"), primary_key=True),
)


class Post(db.Model):
    """Represents a blog post."""

    __tablename__ = "posts"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False)
    content = db.Column(db.Text, nullable=False)
    excerpt = db.Column(db.Text, nullable=True)
    featured_image = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), default="draft", nullable=False)
    is_featured = db.Column(db.Boolean, default=False, nullable=False)
    views = db.Column(db.Integer, default=0, nullable=False)
    likes = db.Column(db.Integer, default=0, nullable=False)
    meta_title = db.Column(db.String(255), nullable=True)
    meta_description = db.Column(db.String(255), nullable=True)
    meta_keywords = db.Column(db.String(255), nullable=True)
    og_title = db.Column(db.String(255), nullable=True)
    og_description = db.Column(db.String(255), nullable=True)
    twitter_title = db.Column(db.String(255), nullable=True)
    twitter_description = db.Column(db.String(255), nullable=True)
    canonical_url = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)

    author = db.relationship("User", back_populates="posts")
    category = db.relationship("Category", back_populates="posts")
    comments = db.relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    tags = db.relationship("Tag", secondary=post_tags, back_populates="posts")


class Comment(db.Model):
    """Represents a user comment on a post."""

    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    is_approved = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=False)

    author = db.relationship("User", back_populates="comments")
    post = db.relationship("Post", back_populates="comments")


class Settings(db.Model):
    """Represents site-wide settings."""

    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True)
    site_title = db.Column(db.String(255), default="AI Blog CMS", nullable=False)
    site_tagline = db.Column(db.String(255), default="Powerful AI-driven content management", nullable=False)
    site_description = db.Column(db.Text, default="A modern AI-powered blog CMS", nullable=False)
    admin_email = db.Column(db.String(255), default="admin@example.com", nullable=False)
    allow_comments = db.Column(db.Boolean, default=True, nullable=False)
    allow_registration = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


@login_manager.user_loader
def load_user(user_id: str) -> Any:
    """Load a user by primary key for Flask-Login."""
    return db.session.get(User, int(user_id))


def slugify(value: str) -> str:
    """Create a slug from arbitrary text."""
    value = re.sub(r"[^\w\s-]", "", value.lower()).strip()
    value = re.sub(r"[-\s]+", "-", value)
    return value


def get_or_create_settings() -> Settings:
    """Ensure a settings row exists and return it."""
    settings = Settings.query.first()
    if settings is None:
        settings = Settings()
        db.session.add(settings)
        db.session.commit()
    return settings


def ensure_demo_content() -> None:
    """Populate the database with a small set of demo posts when needed."""
    if Post.query.count() >= 2:
        return

    if User.query.first() is None:
        demo_user = User(username="demo", email="demo@example.com", full_name="Demo Author")
        demo_user.set_password("demo123")
        db.session.add(demo_user)
        db.session.flush()

    author = User.query.filter_by(username="demo").first() or User.query.first()
    if author is None:
        author = User(username="demo", email="demo@example.com", full_name="Demo Author")
        author.set_password("demo123")
        db.session.add(author)
        db.session.flush()

    if Category.query.count() == 0:
        categories = [
            Category(name="Technology", slug="technology", description="Insights on software, AI, and modern tools."),
            Category(name="Productivity", slug="productivity", description="Practical advice to build focus and momentum."),
        ]
        db.session.add_all(categories)
        db.session.flush()

    categories = {category.slug: category for category in Category.query.all()}

    demo_posts = [
        {
            "title": "Building a Smarter Blog with Flask",
            "slug": "building-a-smarter-blog-with-flask",
            "content": "<p>Flask is a lightweight framework that makes it easy to build modern content-driven websites with a clean backend and flexible templates.</p><p>This demo post shows how a simple CMS can publish polished articles with categories, SEO metadata, and a friendly admin experience.</p>",
            "excerpt": "A quick look at why Flask is a great fit for building a modern blog CMS.",
            "status": "published",
            "is_featured": True,
            "meta_title": "Build a Smarter Blog with Flask",
            "meta_description": "Learn how Flask can power a clean, flexible, and SEO-friendly blog CMS.",
            "meta_keywords": "flask, blog, cms",
            "canonical_url": "/building-a-smarter-blog-with-flask",
            "category_slug": "technology",
        },
        {
            "title": "Small Habits That Improve Daily Writing",
            "slug": "small-habits-that-improve-daily-writing",
            "content": "<p>Consistency matters more than intensity when you are building a content habit.</p><p>Short drafting sessions, clear prompts, and a simple review workflow help turn ideas into publishable articles without burning out.</p>",
            "excerpt": "Simple routines that can make writing feel lighter and more sustainable.",
            "status": "published",
            "meta_title": "Small Habits That Improve Daily Writing",
            "meta_description": "Discover simple habits that make daily writing more consistent and rewarding.",
            "meta_keywords": "writing, productivity, habits",
            "canonical_url": "/small-habits-that-improve-daily-writing",
            "category_slug": "productivity",
        },
        {
            "title": "How AI Can Support Content Teams",
            "slug": "how-ai-can-support-content-teams",
            "content": "<p>AI tools can help writers research faster, polish structure, and keep a steady publishing rhythm.</p><p>Used thoughtfully, they remove repetitive effort and leave more room for creative decisions.</p>",
            "excerpt": "A practical look at where AI makes content workflows easier.",
            "status": "published",
            "meta_title": "How AI Can Support Content Teams",
            "meta_description": "See how AI can assist content teams with drafting, editing, and planning.",
            "meta_keywords": "ai, content, workflow",
            "canonical_url": "/how-ai-can-support-content-teams",
            "category_slug": "technology",
        },
    ]

    for payload in demo_posts:
        if Post.query.filter_by(slug=payload["slug"]).first():
            continue
        post = Post(
            title=payload["title"],
            slug=payload["slug"],
            content=payload["content"],
            excerpt=payload["excerpt"],
            status=payload["status"],
            is_featured=payload.get("is_featured", False),
            meta_title=payload.get("meta_title"),
            meta_description=payload.get("meta_description"),
            meta_keywords=payload.get("meta_keywords"),
            canonical_url=payload.get("canonical_url"),
            author=author,
            category=categories.get(payload["category_slug"]),
        )
        db.session.add(post)

    db.session.commit()


@app.before_request
def ensure_settings() -> None:
    """Create default settings on the first request if needed."""
    if not hasattr(session, "_settings_initialized"):
        get_or_create_settings()
        session["_settings_initialized"] = True


@app.route("/uploads/<path:filename>")
def uploaded_file(filename: str) -> Any:
    """Serve uploaded files from the configured uploads directory."""
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/")
def index() -> str:
    """Render the public landing page and latest posts."""
    page = request.args.get("page", 1, type=int)
    search = request.args.get("q", "", type=str).strip()
    query = Post.query.filter_by(status="published")
    if search:
        query = query.filter(Post.title.ilike(f"%{search}%"))
    posts = query.order_by(Post.created_at.desc()).paginate(page=page, per_page=6, error_out=False)
    settings = get_or_create_settings()
    return render_template("index.html", settings=settings, posts=posts, search=search)


@app.route("/search")
def search_posts() -> str:
    """Render a search results page for public blog posts."""
    query = request.args.get("q", "", type=str).strip()
    page = request.args.get("page", 1, type=int)
    posts_query = Post.query.filter_by(status="published")
    if query:
        posts_query = posts_query.filter(Post.title.ilike(f"%{query}%"))
    posts = posts_query.order_by(Post.created_at.desc()).paginate(page=page, per_page=6, error_out=False)
    return render_template("index.html", posts=posts, search=query)


@app.route("/register", methods=["GET", "POST"])
def register() -> str | Any:
    """Register a new user account."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        full_name = request.form.get("full_name", "").strip()

        if not username or not email or not password:
            flash("Username, email, and password are required.", "danger")
            return redirect(url_for("register"))

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("A user with that username or email already exists.", "danger")
            return redirect(url_for("register"))

        user = User(username=username, email=email, full_name=full_name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user, remember=True)
        flash("Registration successful. Welcome to AI Blog CMS.", "success")
        return redirect(url_for("dashboard"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login() -> str | Any:
    """Authenticate a user and start a session."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember_me"))

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=remember)
            flash("Login successful.", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "danger")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout() -> Any:
    """Log the current user out and clear session data."""
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard() -> str:
    """Render the authenticated dashboard."""
    post_count = Post.query.count()
    user_count = User.query.count()
    comment_count = Comment.query.count()
    settings = get_or_create_settings()
    return render_template("dashboard.html", current_user=current_user, post_count=post_count, user_count=user_count, comment_count=comment_count, settings=settings)


@app.route("/posts/<slug>")
def post_detail(slug: str) -> str | Any:
    """Render a single post detail page."""
    post = Post.query.filter_by(slug=slug).first_or_404()
    post.views += 1
    db.session.commit()
    related_posts = Post.query.filter(Post.id != post.id, Post.status == "published").order_by(Post.created_at.desc()).limit(3).all()
    return render_template("post_detail.html", post=post, related_posts=related_posts)


@app.route("/posts/create", methods=["GET", "POST"])
@login_required
def create_post() -> str | Any:
    """Create a new blog post."""
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        slug = slugify(request.form.get("slug") or title)
        content = request.form.get("content", "")
        excerpt = request.form.get("excerpt", "")
        status = request.form.get("status", "draft")
        if not title or not content:
            flash("Title and content are required.", "danger")
            return redirect(url_for("create_post"))

        featured_image = None
        file = request.files.get("featured_image")
        if file and file.filename:
            filename = secure_filename(file.filename)
            upload_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(upload_path)
            featured_image = filename

        post = Post(
            title=title,
            slug=slug,
            content=content,
            excerpt=excerpt,
            status=status,
            featured_image=featured_image,
            author=current_user,
            category_id=request.form.get("category_id") or None,
            meta_title=request.form.get("meta_title") or title,
            meta_description=request.form.get("meta_description") or excerpt,
            meta_keywords=request.form.get("meta_keywords") or "",
        )
        db.session.add(post)
        db.session.commit()
        flash("Post created successfully.", "success")
        return redirect(url_for("dashboard"))

    return render_template("create_post.html")


@app.route("/posts/manage")
@login_required
def manage_posts() -> str:
    """Display the user's posts for management."""
    posts = Post.query.filter_by(author=current_user).order_by(Post.created_at.desc()).all()
    return render_template("manage_posts.html", posts=posts)


@app.route("/admin/users")
@login_required
def admin_users() -> str:
    """Display users for the administrator panel."""
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin_users.html", users=users)


@app.route("/admin/comments")
@login_required
def admin_comments() -> str:
    """Display comments for the administrator panel."""
    comments = Comment.query.order_by(Comment.created_at.desc()).all()
    return render_template("admin_comments.html", comments=comments)


@app.route("/admin/posts")
@login_required
def admin_posts() -> str:
    """Display all posts for the administrator panel."""
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template("admin_posts.html", posts=posts)


@app.route("/categories", methods=["GET", "POST"])
@login_required
def categories() -> str | Any:
    """Create and list categories."""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if name:
            category = Category(name=name, slug=slugify(name))
            db.session.add(category)
            db.session.commit()
            flash("Category created.", "success")
        return redirect(url_for("categories"))

    items = Category.query.order_by(Category.name.asc()).all()
    return render_template("categories.html", categories=items)


@app.route("/posts/<slug>/comment", methods=["POST"])
def add_comment(slug: str) -> Any:
    """Add a comment to a post."""
    post = Post.query.filter_by(slug=slug).first_or_404()
    if not current_user.is_authenticated:
        flash("Please log in to comment.", "warning")
        return redirect(url_for("post_detail", slug=slug))

    body = request.form.get("body", "").strip()
    if body:
        comment = Comment(body=body, author=current_user, post=post)
        db.session.add(comment)
        db.session.commit()
        flash("Comment added.", "success")
    return redirect(url_for("post_detail", slug=slug))


@app.route("/settings", methods=["GET", "POST"])
@login_required
def site_settings() -> str | Any:
    """Allow administrators to edit site settings."""
    settings = get_or_create_settings()
    if request.method == "POST":
        settings.site_title = request.form.get("site_title", settings.site_title)
        settings.site_tagline = request.form.get("site_tagline", settings.site_tagline)
        settings.site_description = request.form.get("site_description", settings.site_description)
        settings.admin_email = request.form.get("admin_email", settings.admin_email)
        db.session.commit()
        flash("Settings updated.", "success")
        return redirect(url_for("site_settings"))

    return render_template("settings.html", settings=settings)


@app.route("/sitemap.xml")
def sitemap() -> Any:
    """Generate a simple XML sitemap for published posts."""
    posts = Post.query.filter_by(status="published").order_by(Post.created_at.desc()).all()
    xml_items = "".join(
        f"<url><loc>{url_for('post_detail', slug=post.slug, _external=True)}</loc></url>" for post in posts
    )
    xml = f"<?xml version='1.0' encoding='UTF-8'?>\n<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>{xml_items}</urlset>"
    return xml, 200, {"Content-Type": "application/xml"}


@app.route("/robots.txt")
def robots() -> Any:
    """Serve a simple robots.txt file."""
    return "User-agent: *\nAllow: /\nSitemap: /sitemap.xml\n", 200, {"Content-Type": "text/plain"}


@app.route("/ai/title", methods=["POST"])
def ai_title_generator() -> Any:
    """Generate a suggested SEO title from a prompt."""
    prompt = request.form.get("prompt", "").strip()
    if not prompt:
        return jsonify({"title": ""})
    title = f"{prompt.title()} | AI Blog CMS"
    return jsonify({"title": title})


@app.route("/ai/meta-description", methods=["POST"])
def ai_meta_description_generator() -> Any:
    """Generate a suggested meta description from a prompt."""
    prompt = request.form.get("prompt", "").strip()
    if not prompt:
        return jsonify({"meta_description": ""})
    description = f"Discover {prompt.lower()} with AI-driven insights and high-quality content."
    return jsonify({"meta_description": description})


@app.route("/ai/grammar", methods=["POST"])
def ai_grammar_corrector() -> Any:
    """Correct basic grammar in the supplied text."""
    text = request.form.get("text", "")
    if not text:
        return jsonify({"corrected_text": ""})
    corrected = text.replace(" teh ", " the ").replace("dont", "don't")
    return jsonify({"corrected_text": corrected})


@app.route("/ai/summary", methods=["POST"])
def ai_summary_generator() -> Any:
    """Create a short summary from the supplied content."""
    text = request.form.get("text", "")
    if not text:
        return jsonify({"summary": ""})
    summary = text[:180] + ("..." if len(text) > 180 else "")
    return jsonify({"summary": summary})


@app.route("/ai/keyword-density", methods=["POST"])
def keyword_density_checker() -> Any:
    """Return a simple keyword density summary for a given text."""
    text = request.form.get("text", "")
    keyword = request.form.get("keyword", "")
    if not text or not keyword:
        return jsonify({"density": 0.0, "keyword": keyword})
    words = re.findall(r"\b\w+\b", text.lower())
    keyword_count = sum(1 for word in words if word == keyword.lower())
    density = round((keyword_count / len(words)) * 100, 2) if words else 0.0
    return jsonify({"density": density, "keyword": keyword})


@app.route("/health")
def health() -> Any:
    """Provide a simple health check endpoint."""
    return jsonify({"status": "ok", "service": "ai-blog-cms"})


with app.app_context():
    db.create_all()
    get_or_create_settings()
    ensure_demo_content()


if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=int(os.environ.get("PORT", "5001")))
