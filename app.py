from flask import Flask, session, render_template, redirect, url_for, request, flash, send_file
from turbo_flask import Turbo
from thread_manager import ThreadManager
from functools import wraps
from datetime import timedelta
from api.model.reasoning import Reasoning

from forms.user import SubmitQueryForm, CreateArticle, LoginUser, CreateUser
from forms.search import Search
from markupsafe import Markup
from markdown import markdown
from database.db import db, upload_file, Upload, User
from dotenv import load_dotenv
import threading
import re
import os

load_dotenv()

# Configurações do Flask e do Turbo-Flask
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
app.config['MONGODB_HOST'] = os.getenv("MONGODB_URI")
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)
turbo = Turbo()

# Inicializar extensões
turbo.init_app(app)
db.init_app(app)
thinker = Reasoning('', max_width=5, max_depth=20)

# Inicializar ThreadManager
manager = ThreadManager()
manager.start()

def read_markdown_to_html(content:str):
    # apply replacements once (don't concatenate results) then convert to HTML
    s = re.sub(r"\\\(|\\\)", "$", content)
    s = re.sub(r"\\\[|\\\]", "$$", s)
    html_code = markdown(s)
    #print(html_code)
    return Markup(html_code)

def check_if_logged_in(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# A duas próximas funções executam o armazenamento de artigos e respostas em threads separadas,
# o store_article e store_response são chamados em threads gerenciadas pelo ThreadManager,
# onde o sistema pode lidar com múltiplas requisições simultaneamente sem bloquear a aplicação principal.
# Elas também atualizam o conteúdo na interface do usuário em tempo real usando Turbo-Flask.

def store_article(username: str, log_dir: str, model: str = None, iterations: str = "1", api_key: str = None, n_tokens: int = 65000):
    iterations_int = 0
    user = User.objects(username=username).first()
    if user is None:
        print("User not found, cannot store article.")
        return

    try:
        iterations_int = int(iterations)
    except Exception:
        iterations_int = 1

    # configure thinker parameters for this run
    if api_key is not None:
        thinker.api_key = api_key
    if model:
        thinker.model = model

    article_content = ""
    # Run the article generator directly to preserve the session/username
    with app.app_context():
        gen = thinker.write_article(username=username, log_dir=log_dir, iterations=iterations_int, n_tokens=n_tokens)
        for chunk in gen:
            if chunk:
                article_content += chunk
                turbo.push(turbo.update(render_template('_article_fragment.html', article=read_markdown_to_html(article_content)), 'articleContent'))


def store_response(query: str, username: str, log_dir: str, model: str = None, max_width: str = None, max_depth: str = None, n_tokens: str = None, api_key: str = None, prompt: str = None):
    user = User.objects(username=username).first()
    if user is None:
        print("User not found, cannot store response.")
        return

    # configure thinker parameters for this run
    if api_key is not None:
        thinker.api_key = api_key
    if model:
        thinker.model = model
    try:
        if max_width is not None:
            thinker.max_width = int(max_width)
    except Exception:
        pass
    try:
        if max_depth is not None:
            thinker.max_depth = int(max_depth)
    except Exception:
        pass
    try:
        if n_tokens is not None:
            thinker.n_tokens_default = int(n_tokens)
    except Exception:
        pass

    response_content = ""

    # Run the reasoning generator directly to preserve session/username
    with app.app_context():
        gen, response = thinker.reasoning_step(username=username, log_dir=log_dir, query=query or "", init=False, prompt=None if prompt == 'None' else prompt)
        for chunk in gen:
            if chunk == "Solved the problem":
                break
            
            if chunk:
                response_content += chunk
                turbo.push(turbo.update(render_template('_response_fragment.html', content=read_markdown_to_html(response_content)), 'responseContent'))

# Aqui ficam as rotas do Flask para a aplicação web
# Elas lidam com o login, registro, busca e visualização de logs,
# além de iniciar o armazenamento de respostas e artigos em threads separadas.
# Anteriormente, essas operações eram genrenciadas por um blueprint bp_processing_api,
# mas foram movidas para o arquivo principal app.py para simplificar a estrutura do projeto.

@app.route("/", methods=["GET", "POST"])
@check_if_logged_in
def home():
    """
    Página inicial com formulário de busca.
    """
    # use session.get to avoid KeyError when key doesn't exist
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    form = Search()

    if form.validate_on_submit():
        query = form.query.data
        objs = Upload.objects(filename__contains=query)
        files = set()
        files_objs = []
        for obj in objs:
            filename = obj.filename.split("\\")
            files_objs.append(filename[0])

            if len(filename) == 1:
                files.add(obj.creator.username+'/'+filename[0].split("/")[0])

            else:
                files.add(obj.creator.username+'/'+filename[0])

        return redirect(url_for('view_logs', username=session.get('username'), log_dir=query))
    return render_template('index.html', form=form)

@app.route("/login", methods=['GET', 'POST'])
def login():
    """Rota de login de usuário.
    Verifica as credenciais do usuário e inicia a sessão.
    Note no código abaixo a utilização de flask_wtf e WTForms para validação de formulários.
    """
    form = LoginUser()
    if form.validate_on_submit():
        username_or_email = form.username_or_email.data
        password = form.password.data

        session.permanent = True
        users = User.objects(__raw__={'$or':[{'username':username_or_email},{'email':username_or_email}]})
        if users.first() is None:
            flash("No users matching the description", 'error')

        else:
            usr = users.first()
            if usr.check_password(password):
                flash('Sucessfully logged in')
                session['logged_in'] = True
                session['username'] = usr.username

                # Ensure session changes are persisted immediately
                session.modified = True

                return redirect(url_for('home'))

            else:
                flash('Incorrect Password', 'error')

    return render_template('user_forms.html', login=True, form=form)

@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Mesma coisa que a rota de login, mas para registro de novos usuários.
    """
    form = CreateUser()       
    if form.validate_on_submit():
        username = form.username.data
        email = form.email.data
        password = form.password.data

        session.permanent = True
        existing = User.objects(__raw__={'$or':[{'username':username},{'email':email}]})
        if existing.first() is not None:
            flash("Username or email already registered", 'error')

        else:
            print(username)
            session['logged_in'] = True
            session['username'] = username
            usr = User(id=User.objects.count()+1, username=username, email=email)
            usr.generate_password_hash(password)
            usr.save()

            # Ensure session changes are persisted immediately
            session.modified = True

            return redirect(url_for('home'))
    return render_template('user_forms.html', login=False, form=form)


@app.route("/<username>")
def view_logs_links(username:str):
    """Aqui seria a página de perfil do usuário, mostrando os logs disponíveis."""
    user = User.objects(username=username).first()
    
    if user is None:
        flash("User not found", 'error')
        return redirect(url_for('home'))

    responses = Upload.objects(filename__contains="response.md", creator=user)
    log_dirs_responses =  map(lambda x:user.username+'/'+x.filename.split("/")[0], responses)
    
    if responses.first() is None:
        flash("No logs found for this user/log_dir", 'error')
        return redirect(url_for('home'))
      
    return render_template('search.html', query=log_dirs_responses, read_markdown_to_html=read_markdown_to_html)

@app.route("/<username>/<log_dir>")
def view_logs(username:str, log_dir:str):
    """
    Página para visualizar os log específico de um usuário.
    """
    user = User.objects(username=username).first()
    
    if user is None:
        flash("User not found", 'error')
        return redirect(url_for('home'))

    response = Upload.objects(filename__contains=f"{log_dir}/response.md", creator=user).first()
    article = Upload.objects(filename__contains=f"{log_dir}/article.md", creator=user).first()
    if response is None:
        flash("No logs found for this user/log_dir", 'error')
        return redirect(url_for('home'))
    
    return render_template('response.html', response=response, article=article, read_markdown_to_html=read_markdown_to_html)

@app.route("/<username>/<log_dir>/write_logs")
@check_if_logged_in
def write(username:str, log_dir:str):
    if username != session.get("username"):
        return redirect(url_for("home"))
    
    query = request.args.get('query')
    model = request.args.get('model')
    max_width = request.args.get('max_width')
    max_depth = request.args.get('max_depth')
    n_tokens = request.args.get('n_tokens')
    api_key = request.args.get('api_key')
    prompt = request.args.get('prompt')

    t = threading.Thread(target=store_response, args=(query, username, log_dir, model, max_width, max_depth, n_tokens, api_key, prompt))
    # append thread in a thread-safe way so ThreadManager can pick it up
    with manager.lock:
        manager.threads.append(t)

    return render_template('response.html', reponse=False, article=False, read_markdown_to_html=read_markdown_to_html)

@app.route("/<username>/<log_dir>/write_article", methods=["GET", "POST"])
@check_if_logged_in
def write_article(username:str, log_dir:str):
    
    model = request.args.get("model")
    iterations = request.args.get('iterations')
    api_key = request.args.get('api_key')

    t = threading.Thread(target=store_article, args=(username, log_dir, model, iterations, api_key))
    # append thread in a thread-safe way so ThreadManager can pick it up
    response = Upload.objects(filename__contains=os.path.join(log_dir, "response.md"), creator=User.objects(username=username).first()).first()
    
    with manager.lock:
        manager.threads.append(t)
    
    print("queued thread", t)
    return render_template('response.html', response=response, article=False, read_markdown_to_html=read_markdown_to_html)

@app.route("/submit_question", methods=["GET", "POST"])
@check_if_logged_in
def submit_question():
    form = SubmitQueryForm()
    if form.validate_on_submit() and request.method == 'POST':
        # Form validation and processing
        usr = User.objects(username=session.get('username')).first()
        upload_file(
            user=usr,
            log_dir=form.log_dir.data or 'default_log',
            filename='context.md',
            raw_file=f"Initial context: {form.context.data}".encode('utf-8'),
            initial=True
        )

        upload_file(
            user=usr,
            log_dir=form.log_dir.data or 'default_log',
            filename='response.md',
            raw_file=" ".encode('utf-8'),
            initial=True
        )

        upload_file(
            user=usr,
            log_dir=form.log_dir.data or 'default_log',
            filename='article.md',
            raw_file=" ".encode('utf-8'),
            initial=True
        )

        return redirect(url_for('write', query=form.query.data, prompt=None, username=session.get('username'), log_dir=form.log_dir.data or 'default_log', model=form.model_name.data or "deepseek-v3.1:671b-cloud", max_width=form.max_width.data, max_depth=form.max_depth.data, n_tokens=form.n_tokens.data if form.n_tokens.data is not None else 100000, api_key=form.api_key.data))
    return render_template('form.html', form=form)

@app.route("/submit_article", methods=["GET", "POST"])
@check_if_logged_in
def submit_article():
    form = CreateArticle()
    if form.validate_on_submit():
        log_dir = form.log_dir.data
        iterations = form.n_iterations.data
        api_key = form.api_key.data
        model = form.model.data if form.model.data else thinker.model

        return redirect(url_for("write_article", username=session.get("username"), log_dir=log_dir, model=model, n_iterations=iterations, api_key=api_key))
    return render_template("create_article.html", form=form)
                        



if __name__ == '__main__':
    # Enable threading so worker threads can make HTTP requests back to this server
    # (use a production WSGI server for real deployments)
    app.run(debug=True, threaded=True)
