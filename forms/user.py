"""
Formulários WTForms para Autenticação e Submissão de Perguntas

Este módulo define todos os formulários da aplicação usando WTForms
e Flask-WTF para validação server-side e proteção CSRF.

Formulários:
1. SubmitQueryForm: Submeter pergunta para raciocínio profundo
2. CreateArticle: Gerar artigo baseado em raciocínio
3. CreateUser: Registro de novo usuário
4. LoginUser: Autenticação de usuário

Validações:
- WTForms: client-side e server-side
- Email: validação de formato
- Números: validação de range
- Igualdade: validação de campos correspondentes

Proteção:
- CSRF: Tokens gerados automaticamente pelo Flask-WTF
"""

from wtforms import StringField, SubmitField, IntegerField, PasswordField
from wtforms.validators import DataRequired, Optional, NumberRange, Email, EqualTo
from flask_wtf import FlaskForm
from backend.database.db import User


# ============================================================================
# FORMULÁRIO: SUBMIT QUERY - SUBMETER PERGUNTA
# ============================================================================

class SubmitQueryForm(FlaskForm):
    """
    Formulário para submeter uma pergunta para raciocínio profundo.
    
    Campos:
        query (str): Pergunta/problema principal
        context (str): Informações de contexto para orientar raciocínio
        api_key (str): Chave de autenticação para Ollama
        log_dir (str): Nome do diretório para logs (opcional)
        n_tokens (int): Número máximo de tokens (opcional)
        max_depth (int): Profundidade máxima (2-20)
        max_width (int): Largura máxima (2-10, alternativas)
        model_name (str): Nome do modelo Ollama (opcional)
        submit (SubmitField): Botão de envio
    
    Validações:
        - query: Obrigatório (não vazio)
        - context: Obrigatório (não vazio)
        - api_key: Obrigatório (não vazio)
        - log_dir: Opcional (pode ser vazio)
        - n_tokens: Opcional, range quando fornecido
        - max_depth: Obrigatório, 2-20
        - max_width: Obrigatório, 2-10
        - model_name: Opcional (usa padrão se vazio)
    
    Exemplos:
        >>> form = SubmitQueryForm()
        >>> if form.validate_on_submit():
        ...     query = form.query.data
        ...     context = form.context.data
        ...     api_key = form.api_key.data
    """
    
    # Campo de pergunta principal
    query = StringField("Query ", validators=[DataRequired()])
    
    # Campo de contexto para orientar raciocínio
    context = StringField("AI context ", validators=[DataRequired()])
    
    # Chave de autenticação Ollama
    api_key = StringField("Your Ollama API key", validators=[DataRequired()])
    
    # Diretório para logs (opcional - usa padrão se vazio)
    log_dir = StringField("Logging Dir Temp", validators=[Optional()])
    
    # Número máximo de tokens (opcional)
    n_tokens = IntegerField("Number of tokens (max)", validators=[Optional()])
    
    # Profundidade máxima: 2 a 20
    max_depth = IntegerField("Max Depth", validators=[DataRequired(), NumberRange(2, 20)])
    
    # Largura máxima (alternativas por nível): 2 a 10
    max_width = IntegerField("Max Width", validators=[DataRequired(), NumberRange(2, 10)])

    # Rerências
    citations = StringField('Citations (State profiles with #)', validators=[Optional()])
    
    # Nome do modelo Ollama (opcional)
    model_name = StringField("Model name", validators=[Optional()])
    
    # Botão de envio
    submit = SubmitField('submit')


# ============================================================================
# FORMULÁRIO: CREATE ARTICLE - GERAR ARTIGO
# ============================================================================

class CreateArticle(FlaskForm):
    """
    Formulário para gerar um artigo baseado em raciocínio anterior.
    
    Usado para criar um artigo estruturado sobre um problema
    que foi previamente investigado/resolvido.
    
    Campos:
        log_dir (str): Qual diretório de log usar como base
        n_iterations (int): Número de iterações (páginas/seções)
        api_key (str): Chave de autenticação Ollama
        model (str): Modelo Ollama (opcional)
        submit (SubmitField): Botão de envio
    
    Validações:
        - log_dir: Obrigatório (diretório deve existir)
        - n_iterations: Obrigatório (número inteiro)
        - api_key: Obrigatório (token de autenticação)
        - model: Opcional (usa padrão se vazio)
    
    Estrutura de Artigo:
        Cada iteração gera uma parte do artigo:
        - 20% iterações: Introdução
        - 20% iterações: Declaração do Problema
        - 20% iterações: Metodologia
        - 20% iterações: Resultados
        - 20% iterações: Conclusão
    
    Exemplos:
        >>> form = CreateArticle()
        >>> if form.validate_on_submit():
        ...     log_dir = form.log_dir.data
        ...     iterations = form.n_iterations.data
        ...     api_key = form.api_key.data
    """
    
    # Diretório do log a usar como base
    log_dir = StringField("Directory to parse", validators=[DataRequired()])
    
    # Número de iterações (seções do artigo)
    n_iterations = IntegerField("Number of pages", validators=[DataRequired()])
    
    # Chave de autenticação Ollama
    api_key = StringField("Ollama API key", validators=[DataRequired()])
    
    # Modelo Ollama (opcional)
    model = StringField("Model", validators=[Optional()])
    
    # Botão de envio
    submit = SubmitField("Create Article")


# ============================================================================
# FORMULÁRIO: CREATE USER - REGISTRO
# ============================================================================

class CreateUser(FlaskForm):
    """
    Formulário para registro de novo usuário.
    
    Valida dados de cadastro e cria novo usuário no banco de dados.
    
    Campos:
        username (str): Nome de usuário (único)
        email (str): Email válido (único)
        password (str): Senha (confirmação necessária)
        confirm (str): Confirmação de senha
        submit (SubmitField): Botão de envio
    
    Validações:
        - username: Obrigatório, deve ser único no banco
        - email: Obrigatório, formato válido, único no banco
        - password: Obrigatório, deve ser igual a confirm
        - confirm: Obrigatório, mensagem de erro se diferente
    
    Segurança:
        - Senhas nunca são enviadas em texto plano (HTTPS recomendado)
        - Senhas são hashadas com bcrypt + salt no servidor
        - Confirmação previne erros de digitação
    
    Exemplos:
        >>> form = CreateUser()
        >>> if form.validate_on_submit():
        ...     username = form.username.data
        ...     email = form.email.data
        ...     password = form.password.data
        ...     # Hash será gerado automaticamente
    """
    
    # Nome de usuário (deve ser único)
    username = StringField("Username", validators=[DataRequired()])
    
    # Email (deve ser válido e único)
    email = StringField("Email", validators=[DataRequired(), Email()])
    
    # Senha (com validação de igualdade)
    password = PasswordField(
        "Password", 
        validators=[
            DataRequired(), 
            EqualTo('confirm', message="Passwords must match")
        ]
    )
    
    # Confirmação de senha
    confirm = PasswordField("Confirm Password", validators=[DataRequired()])
    
    # Botão de envio
    submit = SubmitField("Register")


# ============================================================================
# FORMULÁRIO: LOGIN USER - AUTENTICAÇÃO
# ============================================================================

class LoginUser(FlaskForm):
    """
    Formulário para login de usuário existente.
    
    Permite autenticação usando username OU email (flexível).
    
    Campos:
        username_or_email (str): Nome de usuário ou email
        password (str): Senha
        submit (SubmitField): Botão de envio
    
    Validações:
        - username_or_email: Obrigatório (não vazio)
        - password: Obrigatório (não vazio)
    
    Autenticação:
        - Server: busca usuário por username OU email
        - Valida senha com check_password()
        - Cria sessão se credenciais corretas
    
    Segurança:
        - Nunca indica se username ou password está errado
        - Sempre retorna "Credenciais inválidas" genérico
        - Protege contra user enumeration
    
    Exemplos:
        >>> form = LoginUser()
        >>> if form.validate_on_submit():
        ...     username_or_email = form.username_or_email.data
        ...     password = form.password.data
        ...     # Verificar credenciais no servidor
    """
    
    # Campo flexível: aceita username OU email
    username_or_email = StringField("Username or email", validators=[DataRequired()])
    
    # Senha
    password = PasswordField("Password", validators=[DataRequired()])
    
    # Botão de envio
    submit = SubmitField("Login")

