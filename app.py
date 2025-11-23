from flask import Flask, session, render_template, redirect, url_for, request, flash
from turbo_flask import Turbo
from processing import bp_processing_api, thinker
from thread_manager import ThreadManager
from functools import wraps
import time

from forms.user import SubmitQueryForm, SubmitArticleForm, LoginUser, CreateUser
from forms.search import Search
from markupsafe import Markup
from markdown import markdown
from database.db import db, upload_file, Upload, User
from dotenv import load_dotenv
import threading
import requests
import os

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
app.config['MONGODB_HOST'] = os.getenv("MONGODB_URI")
app.config['SERVER_NAME'] = 'localhost:5000'
app.register_blueprint(bp_processing_api)
turbo = Turbo()

turbo.init_app(app)
db.init_app(app)

manager = ThreadManager()
manager.start()

def read_markdown_to_html(content:str):
    html_code = markdown(content)
    #print(html_code)
    return Markup(html_code)

def store_data(username: str, **kwargs):
    """Worker that streams the processing endpoint and stores the aggregated content per depth.

    Args:
        process_url: Full URL to call (absolute, with query params) so we don't need Flask context here.
    """
    user = User.objects(username=username).first()

    if user is None:
        print("store_data: user not found", username)
        return


    print("store_data max_depth:", kwargs.get("max_depth"))
    for i in range(int(kwargs.get("max_depth"))):
        print(f"Thread depth {i}")
        content = ""
        with app.app_context():
           process_url = url_for('bp_processing_api.process', **kwargs)

        resp = requests.get(process_url, stream=True)
        for chunk in resp.iter_content(chunk_size=1024):
            if not chunk:
                continue
            try:
                content += chunk.decode('utf-8')
            except Exception:
                # fallback: treat as str
                content += str(chunk)

        with app.app_context():
            # render only the fragment that will be appended to the page
            turbo.push(turbo.append(render_template('_response_fragment.html', content=read_markdown_to_html(content)), 'responseContent'))

        if "SOLVED" in content and "PROGRESS" not in content:
            print("store_data: problem solved, stopping further processing.")
            break


        time.sleep(4)  # allow turbo to process
        print(f"store_data: depth {i} received content length:", len(content))
            # save the aggregated content for this depth once
        try:
            with app.app_context():
                upload_file(user, kwargs.get("log_dir"), 'response.md', content.encode('utf-8'), i)
                upload_file(user, kwargs.get("log_dir"), 'context.md', thinker.context.encode('utf-8'), i)

        except Exception as e:
            print("store_data: failed to upload file:", e)

        #print(thinker.context)
        print("manager threads:", manager.threads)

def store_data_article(username:str, log_dir:str, n_iterations, **kwargs):
    """Worker that streams the article generation endpoint and stores the aggregated content.

    Args:
        article_url: Full URL to call (absolute, with query params) so we don't need Flask context here.
    """
    user = User.objects(username=username).first()
    if user is None:
        print("store_data_article: user not found", username)
        return

    for i in range(n_iterations):
        kwargs['iteration'] = i
        article_url = None
        with app.app_context():
            print(f"store_data_article iteration {i}")
            article_url = url_for('bp_processing_api.create_article', **kwargs)

        resp = requests.get(article_url, stream=True)
        content = ""

        for chunk in resp.iter_content(chunk_size=1024):
            if not chunk:
                continue
            try:
                content += chunk.decode('utf-8')
            except Exception:
                # fallback: treat as str
                content += str(chunk)

            with app.app_context():
                # render only the fragment that will be appended to the page
                turbo.push(turbo.append(render_template('_article_fragment.html', content=read_markdown_to_html(content)), 'articleContent'))

            print("store_data_article received content length:", len(content))
            time.sleep(0.1)  # allow turbo to process
        # save the aggregated content
        try:
            upload_file(user, log_dir, 'article.md', content.encode('utf-8'), i)
        except Exception as e:
            print("store_data_article: failed to upload file:", e)



def check_if_logged_in(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.route("/", methods=["GET", "POST"])
@check_if_logged_in
def home():
    if not session['logged_in']:
        return redirect(url_for('login'))
    form = Search()

    if form.validate_on_submit():
        query = form.query.data
        objs = Upload.objects(filename__contains=query)
        files = set()
        for obj in objs:
            filename = obj.filename.split("\\")

            if len(filename) == 1:
                files.add(filename[0].split("/")[0])

            else:
                files.add(filename[0])


        return render_template('search.html', query=files)
    return render_template('index.html', form=form)

@app.route("/login", methods=['GET', 'POST'])
def login():
    form = LoginUser()
    if form.validate_on_submit():
        username_or_email = form.username_or_email.data
        password = form.password.data

        users = User.objects(__raw__={'$or':[{'username':username_or_email},{'email':username_or_email}]})
        if users.first() is None:
            flash("No users matching the description", 'error')

        else:
            usr = users.first()
            if usr.check_password(password):
                flash('Sucessfully logged in')
                session['logged_in'] = True
                session['username'] = usr.username

                return redirect(url_for('home'))

            else:
                flash('Incorrect Password', 'error')

    return render_template('user_forms.html', login=True, form=form)

@app.route("/register", methods=["GET", "POST"])
def register():
    form = CreateUser()
    if form.validate_on_submit():
        username = form.username.data
        email = form.email.data
        password = form.password.data

        existing = User.objects(__raw__={'$or':[{'username':username},{'email':email}]})
        if existing.first() is not None:
            flash("Username or email already registered", 'error')

        else:
            session['logged_in'] = True
            session['username'] = username
            usr = User(id=User.objects.count()+1, username=username, email=email)
            usr.generate_password_hash(password)
            usr.save()

            return redirect(url_for('home'))
    return render_template('user_forms.html', login=False, form=form)


@app.route("/<username>/<log_dir>")
@check_if_logged_in
def view_logs_and_article(username:str, log_dir:str):
    user = User.objects(username=username).first()
    if user is None:
        flash("User not found", 'error')
        return redirect(url_for('home'))

    objs = Upload.objects(filename__contains=os.path.join(log_dir, 'response.md'), creator=user).order_by('depth')
    objs_article = Upload.objects(filename__contains=os.path.join(log_dir, 'article.md'), creator=user).order_by('depth')
    if objs.first() is None:
        flash("No logs found for this user/log_dir", 'error')
        return redirect(url_for('home'))

    elif objs_article.first() is None:
        objs_article = ""
        return render_template('response.html', showing=True, markdown_left=read_markdown_to_html(objs.first().file.read().decode('utf-8')), markdown_right=objs_article)
    return render_template('response.html', showing=True, markdown_left=read_markdown_to_html(objs.first().file.read().decode('utf-8')), markdown_right=read_markdown_to_html(objs.first().file.read().decode('utf-8')))


@app.route("/<username>/<log_dir>?query=<query>&model=<model>&max_width=<max_width>&max_depth=<max_depth>&n_tokens=<n_tokens>&api_key=<api_key>")
@check_if_logged_in
def write(username:str, log_dir:str, query:str, model:str, max_width:int, max_depth:int, n_tokens:int, api_key:str):
    process_url = url_for('bp_processing_api.process', query=query, log_dir=log_dir, model=model, max_width=max_width, max_depth=max_depth, n_tokens=n_tokens, api_key=api_key, prompt="None", _external=True)
    t = threading.Thread(target=store_data, args=(username,), kwargs={
        "query": query,
        "log_dir": log_dir,
        "model": model,
        "max_width": max_width,
        "max_depth": max_depth,
        "n_tokens": n_tokens,
        "api_key": api_key,
        "prompt": "None"

    })
    # append thread in a thread-safe way so ThreadManager can pick it up
    with manager.lock:
        manager.threads.append(t)

    print("queued thread", t)
    return render_template('response.html', showing=False)

@app.route("/<username>/<log_dir>/write_article?n_tokens=<n_tokens>&api_key=<api_key>&n_iterations=<int:n_iterations>")
@check_if_logged_in
def write_article(username:str, log_dir:str, n_tokens:int, api_key:str, n_iterations:int):
    article_url = url_for('bp_processing_api.create_article', log_dir=log_dir, model=thinker.model, max_width=thinker.max_width, max_depth=thinker.max_depth, n_tokens=n_tokens, username=username, api_key=api_key, _external=True)
    t = threading.Thread(target=store_data_article, args=(article_url, username, log_dir, n_iterations))
    # append thread in a thread-safe way so ThreadManager can pick it up
    with manager.lock:
        manager.threads.append(t)

    print("queued article thread", t)
    return render_template('response.html', showing=False)

@app.route("/<username>/<log_dir>/submit_article", methods=["GET", "POST"])
def submit_article(username:str, log_dir:str):
    form = SubmitArticleForm()
    if form.validate_on_submit() and request.method == 'POST':
        # Form validation and processing
        owner = User.objects(username=session.get('username')).first()
        if owner.username != username:
            flash("You can only create articles for your own user", 'error')
            return redirect(url_for('home'))


        return redirect(url_for('write_article', username=username, log_dir=log_dir, n_tokens=form.n_iterations.data if form.n_iterations.data is not None else 100, api_key=form.api_key.data))
    return render_template('form_article.html', form=form)

@app.route("/submit_question", methods=["GET", "POST"])
@check_if_logged_in
def submit_question():
    form = SubmitQueryForm()
    if form.validate_on_submit() and request.method == 'POST':
        # Form validation and processing
        print(User.objects(username=session.get('username')).first())

        time.sleep(1)
        obj_context = upload_file(
            user=User.objects(username=session.get('username')).first(),
            log_dir=form.log_dir.data or 'default_log',
            filename='context.md',
            raw_file=f"Initial context: {form.context.data}".encode('utf-8'),
            depth=0
        )

        upload_file(
            user=User.objects(username=session.get('username')).first(),
            log_dir=form.log_dir.data or 'default_log',
            filename='article.md',
            raw_file="".encode('utf-8'),
            depth=0
        )

        upload_file(
            user=User.objects(username=session.get('username')).first(),
            log_dir=form.log_dir.data or 'default_log',
            filename='response.md',
            raw_file="".encode('utf-8'),
            depth=0
        )
        thinker.api_key = form.api_key.data
        thinker.context = obj_context.file.read().decode('utf-8')

        return redirect(url_for('write', query=form.query.data, prompt=None, username=session.get('username'), log_dir=form.log_dir.data or 'default_log', model=form.model_name.data or "deepseek-v3.1:671b-cloud", max_width=form.max_width.data, max_depth=form.max_depth.data, n_tokens=form.n_tokens.data if form.n_tokens.data is not None else 100000, api_key=form.api_key.data))
    return render_template('form.html', form=form)


if __name__ == '__main__':
    app.run(debug=True)
