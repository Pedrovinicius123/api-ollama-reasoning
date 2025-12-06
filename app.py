"""
API Ollama Reasoning - Aplicação Flask para Raciocínio Matemático com IA

Este módulo principal gerencia a aplicação web que permite aos usuários:
- Criar contas e fazer login
- Submeter perguntas para processamento com raciocínio em profundidade
- Gerar artigos estruturados sobre os tópicos investigados
- Visualizar historicamente os logs de processamento

Dependências principais:
- Flask: Framework web
- Turbo-Flask: Atualizações em tempo real usando WebSockets
- MongoEngine: ORM para MongoDB
- WTForms: Validação de formulários
- Markdown: Conversão de conteúdo para HTML
"""

from flask import Flask, session, render_template, redirect, url_for, request, flash, copy_current_request_context
from turbo_flask import Turbo
from flask_caching import Cache
from functools import wraps
from datetime import timedelta
import time # for debugging

from forms.user import SubmitQueryForm, CreateArticle, LoginUser, CreateUser
from forms.search import Search
from backend.database.db import db, upload_file, Upload, User
from backend.ollama_thread_manager import read_markdown_to_html, ollama_queue
from dotenv import load_dotenv
import os

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# ============================================================================
# CONFIGURAÇÕES DO FLASK E EXTENSÕES
# ============================================================================

# Inicializa a aplicação Flask
app = Flask(__name__)

# Definir chave secreta para sessões e tokens CSRF (a partir de .env)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

# Configuração do MongoDB - URI obtida do arquivo .env
app.config['MONGODB_HOST'] = os.getenv("MONGODB_URI")

# Tempo de vida da sessão do usuário (1 hora)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)

# Inicializa o Turbo-Flask para atualizações em tempo real
turbo = Turbo()
cache = Cache(config = {
    "DEBUG": True,          # some Flask specific configs
    "CACHE_TYPE": "SimpleCache",  # Flask-Caching related configs
    "CACHE_DEFAULT_TIMEOUT": 300
})

# ============================================================================
# INICIALIZAÇÃO DAS EXTENSÕES
# ============================================================================

# Ativa o Turbo-Flask na aplicação
turbo.init_app(app)

# Inicializa o MongoEngine para acesso ao banco de dados
db.init_app(app)

# Inicializa o cache
cache.init_app(app)

# Inicializa o ThreadManager que gerencia threads de processamento

# ============================================================================
# FUNÇÕES UTILITÁRIAS
# ============================================================================

def check_if_logged_in(f):
    """
    Decorator que verifica se o usuário está autenticado.
    
    Se o usuário não estiver logado (session['logged_in'] não existir ou ser False),
    redireciona para a página de login. Caso contrário, permite o acesso à rota.
    
    Args:
        f: Função de rota a ser protegida
        
    Returns:
        function: Função decorada com verificação de autenticação
        
    Exemplo:
        @app.route("/dashboard")
        @check_if_logged_in
        def dashboard():
            return "Página protegida"
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ============================================================================
# ROTAS DA APLICAÇÃO - AUTENTICAÇÃO
# ============================================================================

@app.route("/", methods=["GET", "POST"])
@check_if_logged_in
def home():
    """
    Página inicial (dashboard) do usuário autenticado.
    
    Exibe um formulário de busca que permite pesquisar logs do usuário.
    Requer autenticação (redireciona para login se não autenticado).
    
    GET: Retorna o formulário de busca
    POST: Processa a busca e redireciona para os logs do usuário
    
    Returns:
        str: HTML renderizado da página inicial ou redirecionamento
        
    Variables de Template:
        - form: Instância do formulário Search
    """
    # Verifica se o usuário está autenticado (dupla verificação)
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    form = Search()

    if form.validate_on_submit():
        query = form.query.data
        return redirect(url_for('view_logs_links', username=query, log_dir=query))
       
    return render_template('index.html', form=form, Upload=Upload, users=User, current_user=session.get('username'))


@app.route("/login", methods=['GET', 'POST'])
def login():
    """
    Rota de login de usuário.
    
    Permite que usuários se autentiquem usando nome de usuário ou email + senha.
    Valida as credenciais contra o banco de dados MongoDB.
    
    GET: Exibe o formulário de login
    POST: Processa as credenciais e cria uma sessão autenticada
    
    Validações:
    - Verifica se usuário/email existe no banco de dados
    - Valida a senha usando hash bcrypt
    - Inicia uma sessão permanente (1 hora de duração)
    
    Returns:
        str: HTML do formulário de login ou redirecionamento para home
        
    Flash Messages:
        - "No users matching the description" (erro): Usuário não encontrado
        - "Sucessfully logged in": Login bem-sucedido
        - "Incorrect Password" (erro): Senha incorreta
    """
    form = LoginUser()
    
    if form.validate_on_submit():
        username_or_email = form.username_or_email.data
        password = form.password.data

        # Define a sessão como permanente (com expiração)
        session.permanent = True
        
        # Busca por usuário usando username OU email
        users = User.objects(__raw__={'$or':[{'username':username_or_email},{'email':username_or_email}]})
        
        if users.first() is None:
            flash("No users matching the description", 'error')
        else:
            usr = users.first()
            print(usr.username)
            # Valida a senha contra o hash armazenado
            if usr.check_password(password):
                flash('Sucessfully logged in')
                session['logged_in'] = True
                session['username'] = usr.username

                # Garante que as mudanças na sessão sejam persistidas
                session.modified = True

                return redirect(url_for('home'))
            else:
                flash('Incorrect Password', 'error')

    return render_template('user_forms.html', login=True, form=form)


@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Rota de registro de novo usuário.
    
    Permite que novos usuários criem uma conta com:
    - Nome de usuário único
    - Email válido e único
    - Senha com confirmação
    
    Validações:
    - Nome de usuário não pode estar duplicado
    - Email não pode estar duplicado
    - Emails são validados pelo WTForms
    - Senhas devem corresponder
    
    GET: Exibe formulário de registro
    POST: Cria novo usuário e inicia sessão autenticada
    
    Returns:
        str: HTML do formulário de registro ou redirecionamento para home
        
    Flash Messages:
        - "Username or email already registered" (erro): Duplicação de dados
    
    Database:
        - Cria novo documento User no MongoDB
        - Hash de senha gerado automaticamente
    """
    form = CreateUser()       
    
    if form.validate_on_submit():
        username = form.username.data
        email = form.email.data
        password = form.password.data

        session.permanent = True
        
        # Verifica se username ou email já estão registrados
        existing = User.objects(__raw__={'$or':[{'username':username},{'email':email}]})
        
        if existing.first() is not None:
            flash("Username or email already registered", 'error')
        else:
            print(username)
            session['logged_in'] = True
            session['username'] = username
            
            # Cria novo usuário com ID sequencial
            usr = User(username=username, email=email)
            
            # Gera hash bcrypt da senha
            usr.generate_password_hash(password)
            
            # Persiste no banco de dados
            usr.save()

            # Garante que as mudanças na sessão sejam persistidas
            session.modified = True

            return redirect(url_for('home'))
    
    return render_template('user_forms.html', login=False, form=form)


# ============================================================================
# ROTAS DE VISUALIZAÇÃO DE LOGS
# ============================================================================


@app.route("/search?<log_dir>")
def view_logs_links(log_dir:str):
    """
    Lista todos os diretórios de logs (runs) para um usuário específico.
    
    Exibe os links para acessar cada run individual (contendo response.md e/ou article.md).
    
    Args:
        username (str): Nome de usuário para listar logs
    
    Returns:
        str: HTML com lista de links para logs ou redirecionamento em caso de erro
        
    Flash Messages:
        - "User not found" (erro): Usuário não existe
        - "No logs found for this user/log_dir" (erro): Usuário tem nenhum log
        
    Variables de Template:
        - query: Iterável de strings formatadas como 'username/log_dir'
        - read_markdown_to_html: Função para renderizar Markdown em templates
    """

    # Busca todos os uploads contendo 'response.md' do usuário
    responses = Upload.objects(filename__contains=log_dir)
    
    # Extrai os diretórios de log formatados como 'username/log_dir'
    print([response for response in responses])
    log_dirs_responses = list(map(lambda x: x.creator.username+'/'+x.filename.split("/")[0] if x.creator else x.creator, responses))
    while None in log_dirs_responses:
        log_dirs_responses.remove(None)

    if responses.first() is None:
        flash("No logs found for this user/log_dir", 'error')
        return redirect(url_for('home'))
      
    return render_template('search.html', query=log_dirs_responses, read_markdown_to_html=read_markdown_to_html)


@app.route("/<username>/<log_dir>")
@cache.cached(timeout=1000)
def view_logs(username: str, log_dir: str):
    """
    Exibe um log específico (run) completo de um usuário.
    
    Mostra:
    - Resposta ao problema (response.md)
    - Artigo gerado (article.md) - se disponível
    - Contexto original (context.md) - armazenado para referência
    
    Args:
        username (str): Nome do proprietário do log
        log_dir (str): Nome do diretório do log
    
    Returns:
        str: HTML com conteúdo do log renderizado ou redirecionamento em erro
        
    Flash Messages:
        - "User not found" (erro): Usuário não existe
        - "No logs found for this user/log_dir" (erro): Log não encontrado
        
    Variables de Template:
        - response: Objeto Upload do response.md
        - article: Objeto Upload do article.md (pode ser None)
        - read_markdown_to_html: Função para renderizar Markdown
    """
    user = User.objects(username=username).first()
    
    if user is None:
        flash("User not found", 'error')
        return redirect(url_for('home'))

    # Busca o arquivo de resposta para este log
    response = Upload.objects(filename__contains=f"{log_dir}/response.md", creator=user).first()
    
    # Busca o arquivo de artigo (pode não existir)
    article = Upload.objects(filename__contains=f"{log_dir}/article.md", creator=user).first()
    
    if response is None:
        flash("No logs found for this user/log_dir", 'error')
        return redirect(url_for('home'))
    
    return render_template('response.html', response=response, article=article, read_markdown_to_html=read_markdown_to_html)


# ============================================================================
# ROTAS DE PROCESSAMENTO - RACIOCÍNIO E GERAÇÃO DE ARTIGOS
# ============================================================================

@app.route("/<username>/<log_dir>/write_logs")
@check_if_logged_in
@cache.cached(timeout=1000)
def write(username: str, log_dir: str):
    """
    Inicia o processamento de raciocínio em profundidade para uma pergunta.
    
    Esta rota:
    1. Valida que o usuário autenticado é o proprietário do log
    2. Extrai os parâmetros de raciocínio da query string
    3. Cria uma nova thread para executar o raciocínio
    4. Adiciona a thread ao ThreadManager para ser iniciada
    5. Retorna a página de resposta para receber atualizações em tempo real
    
    Parâmetros de Query String:
        - query (str): Pergunta/problema a ser resolvido
        - model (str): Nome do modelo Ollama a usar
        - max_width (int): Número de alternativas por nível (2-10)
        - max_depth (int): Profundidade máxima de raciocínio (2-20)
        - n_tokens (int): Número máximo de tokens a gerar
        - api_key (str): Chave de API para autenticação Ollama
        - prompt (str): Prompt customizado do sistema
    
    Args:
        username (str): Proprietário do log (deve ser o usuário autenticado)
        log_dir (str): Diretório para armazenar logs do processamento
    
    Returns:
        str: HTML da página de resposta com WebSocket conectado para updates
        
    Segurança:
        - Verifica que username == session['username']
        - Redireciona para home se não autorizado
    
    Processing:
        - Cria thread gerenciada pelo ThreadManager
        - Não bloqueia a requisição principal
        - Atualizações enviadas via Turbo-Flask WebSocket
    """
    # Verifica autorização: usuário só pode processar seus próprios logs
    if username != session.get("username"):
        return redirect(url_for("home"))

    print(username)

    params = {
        "log_dir":log_dir,
        "username": username,
        "turbo":turbo,
        **request.args
    }
    
    _ , session_id = ollama_queue.submit_request_response(app, **params)
    session[log_dir] = {"response":session_id}

    # Retorna página para receber atualizações em tempo real
    return render_template('response.html', reponse=False, article=False, read_markdown_to_html=read_markdown_to_html, response_id=session_id)


@app.route("/<username>/<log_dir>/write_article", methods=["GET", "POST"])
@check_if_logged_in
@cache.cached(timeout=1000)
def write_article(username: str, log_dir: str):
    """
    Inicia a geração de um artigo estruturado baseado no log de raciocínio.
    
    Esta rota:
    1. Valida autorização do usuário
    2. Extrai parâmetros de configuração (modelo, iterações, API key)
    3. Cria thread para gerar o artigo
    4. Adiciona ao ThreadManager para execução
    5. Retorna página com WebSocket conectado para atualizações em tempo real
    
    Parâmetros de Query String:
        - model (str): Nome do modelo Ollama a usar
        - iterations (int): Número de iterações (páginas) do artigo
        - api_key (str): Chave de API Ollama
    
    Args:
        username (str): Proprietário do log (deve ser o usuário autenticado)
        log_dir (str): Diretório contendo o response.md base
    
    Returns:
        str: HTML da página com conteúdo sendo gerado em tempo real
        
    Processing:
        - Busca o response.md existente para contexto
        - Cria e enfileira thread no ThreadManager
        - Inicializa article.md vazio ou existente
    
    Threading:
        - Não bloqueia requisição principal
        - Atualizações via WebSocket Turbo-Flask
    """
    # Extrai parâmetros de configuração

    params = {
        "username":username,
        "log_dir": log_dir,
        "turbo": turbo,
        **request.args

    }
    
    _, session_id = ollama_queue.submit_request_article(app, **params)
    session[log_dir] = {"article": session_id}
    print(session_id)

    # Busca o response.md associado para contexto
    response = Upload.objects(filename__contains=os.path.join(log_dir, "response.md"), creator=User.objects(username=username).first()).first()
    article = Upload.objects(filename__contains=os.path.join(log_dir, "article.md"), creator=User.objects(username=username).first()).first()    
    return render_template('response.html', response=response, article=False, read_markdown_to_html=read_markdown_to_html, response_id='', article_id=session_id)


# ============================================================================
# ROTAS DE SUBMISSÃO DE FORMULÁRIOS E REMOÇÃO DE DADOS PELO USUÁRIO
# ============================================================================

@app.route("/<username>/<log_dir>/delete")
@check_if_logged_in
def delete(username:str, log_dir:str):
    if session.get("username") != username:
        flash("You cannot delete others logs", "error")
        return redirect(url_for("home"))

    usr = User.objects(username=username).first()
    objs = Upload.objects(filename__contains=log_dir, creator=usr)
    ollama_queue.cleanup_session(session.get(log_dir))
    
    for obj in objs:
        obj.delete()

    return redirect(url_for("home"))    


@app.route("/submit_question", methods=["GET", "POST"])
@check_if_logged_in
def submit_question():
    """
    Formulário para submeter uma pergunta/problema para raciocínio profundo.
    
    Este formulário coleta:
    - Pergunta: O problema a ser resolvido
    - Contexto: Informações adicionais para orientar o raciocínio
    - Configurações de raciocínio: max_width, max_depth, n_tokens
    - Modelo: Qual modelo Ollama usar
    - API Key: Autenticação para Ollama
    - Log Dir: Diretório para armazenar logs
    
    GET: Exibe o formulário vazio
    POST: 
        1. Valida o formulário
        2. Cria arquivos iniciais (context.md, response.md, article.md)
        3. Redireciona para /write com os parâmetros para iniciar raciocínio
    
    Returns:
        str: HTML do formulário ou redirecionamento para processar pergunta
        
    Database Operations:
        - Cria 3 arquivos iniciais por pergunta:
          * context.md: Contexto fornecido
          * response.md: Vazio, será preenchido com resposta
          * article.md: Vazio, será preenchido se artigo for gerado
    
    Redirect:
        - Redireciona para rota /write com todos os parâmetros
        - Inicia processamento de raciocínio
    """
    form = SubmitQueryForm()
    
    if form.validate_on_submit() and request.method == 'POST':
        # Obtém usuário autenticado
        usr = User.objects(username=session.get('username')).first()
        
        # Define diretório de log (padrão: 'default_log' se não fornecido)
        log_dir_value = form.log_dir.data or 'default_log'
        cits = [log.strip() for log in form.citations.data.split('#')]
        while '' in cits:
            cits.remove('')

        print(cits)

        # Cria arquivo de contexto inicial
        upload_file(
            user=usr,
            log_dir=log_dir_value,
            filename='context.md',
            raw_file=f"Initial context: {form.context.data}".encode('utf-8'),
            citations=cits,
            initial=True
        )

        # Cria arquivo de resposta vazio (será preenchido durante raciocínio)
        upload_file(
            user=usr,
            log_dir=log_dir_value,
            filename='response.md',
            raw_file=" ".encode('utf-8'),
            citations=cits,
            initial=True
        )

        # Cria arquivo de artigo vazio (será preenchido se gerado)
        upload_file(
            user=usr,
            log_dir=log_dir_value,
            filename='article.md',
            raw_file=" ".encode('utf-8'),
            citations=cits,
            initial=True
        )

        # Redireciona para iniciar o raciocínio com os parâmetros
        return redirect(url_for('write', 
            query=form.query.data, 
            prompt=None, 
            username=session.get('username'), 
            log_dir=log_dir_value, 
            model=form.model_name.data, 
            max_width=form.max_width.data, 
            max_depth=form.max_depth.data, 
            n_tokens=form.n_tokens.data if form.n_tokens.data is not None else 100000, 
            api_key=form.api_key.data
        ))
    
    return render_template('form.html', form=form)


@app.route("/submit_article", methods=["GET", "POST"])
@check_if_logged_in
def submit_article():
    """
    Formulário para gerar um artigo baseado em um log de raciocínio existente.
    
    Permite que o usuário solicite a geração de um artigo estruturado
    sobre um problema que foi previamente resolvido.
    
    GET: Exibe formulário com opções de configuração
    POST:
        1. Valida os dados do formulário
        2. Redireciona para /write_article com parâmetros
        3. Inicia geração do artigo em background
    
    Parâmetros do Formulário:
        - log_dir (str): Qual log usar como base
        - n_iterations (int): Quantas iterações/páginas para o artigo
        - api_key (str): Chave de autenticação Ollama
        - model (str): Qual modelo usar (opcional, usa padrão se vazio)
    
    Returns:
        str: HTML do formulário ou redirecionamento para processar artigo
        
    Estrutura do Artigo Gerado:
        - Introdução (20% das iterações)
        - Declaração do Problema (20% das iterações)
        - Metodologia (20% das iterações)
        - Resultados (20% das iterações)
        - Conclusão (20% das iterações)
    
    Model Selection:
        - Se modelo não for especificado, usa thinker.model (padrão)
    """
    form = CreateArticle()
    
    if form.validate_on_submit():
        log_dir = form.log_dir.data
        iterations = form.n_iterations.data
        api_key = form.api_key.data

        # Redireciona para iniciar geração do artigo
        
        return redirect(url_for("write_article", 
            username=session.get("username"), 
            log_dir=log_dir, 
            model = form.model.data,
            iterations=iterations, 
            api_key=api_key
        ))
    
    return render_template("create_article.html", form=form)


# ============================================================================
# INICIALIZAÇÃO DA APLICAÇÃO
# ============================================================================

if __name__ == '__main__':
    """
    Ponto de entrada da aplicação.
    
    Inicia o servidor Flask com:
    - debug=True: Modo de depuração (auto-reload em mudanças)
    - threaded=True: Suporta múltiplas threads para requisições concorrentes
    
    AVISO: Para produção, use um servidor WSGI como Gunicorn
    Exemplo: gunicorn -w 4 -b 0.0.0.0:5000 app:app
    
    A aplicação roda em http://localhost:5000 por padrão
    """
    # Habilita threading para que threads de worker possam fazer requisições
    # HTTP de volta para este servidor
    app.run(debug=True, threaded=True)
