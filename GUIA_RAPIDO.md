# 🚀 GUIA RÁPIDO PARA DESENVOLVEDORES

## ⚡ Início Rápido

### Entender a Arquitetura em 5 Minutos

```
┌─────────────────────────────────────────────────────────┐
│              APLICAÇÃO FLASK (app.py)                   │
│  Gerencia rotas HTTP, sessões e redirecionamentos      │
└────────────────────┬────────────────────────────────────┘
                     │
    ┌────────────────┼────────────────┐
    │                │                │
    ▼                ▼                ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ ThreadManager│ │ Reasoning    │ │ WTForms      │
│ (threads)    │ │ (IA logic)   │ │ (validation) │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │
       └────────────────┼────────────────┘
                        │
                        ▼
              ┌──────────────────────┐
              │ MongoDB (database.py) │
              │ - User               │
              │ - Upload (files)     │
              └──────────────────────┘
                        │
                        ▼
              ┌──────────────────────┐
              │ Ollama API (api_main) │
              │ - Chat endpoint      │
              │ - Streaming          │
              └──────────────────────┘
```

### Onde Buscar Cada Funcionalidade

| Funcionalidade | Arquivo | Função |
|---|---|---|
| Rotas HTTP | app.py | `@app.route()` |
| Login/Registro | forms/user.py | `LoginUser`, `CreateUser` |
| Banco de dados | database/db.py | `User`, `Upload` |
| Raciocínio IA | reasoning.py | `Reasoning` classe |
| Threads | thread_manager.py | `ThreadManager` |
| API Ollama | api_main.py | `make_request_ollama_reasoning()` |
| Busca | forms/search.py | `Search` |

## 🔍 Como Adicionar Funcionalidades

### 1. Adicionar Nova Rota

```python
# Em app.py

@app.route("/nova_rota", methods=["GET", "POST"])
@check_if_logged_in  # Se precisa autenticação
def nova_rota():
    """
    Descrição clara da rota.
    
    GET: Retorna ...
    POST: Processa ... e redireciona
    
    Returns:
        str: HTML renderizado ou redirecionamento
    """
    # Sua lógica aqui
    return render_template('template.html', var=valor)
```

### 2. Adicionar Novo Formulário

```python
# Em forms/user.py

class NovoFormulario(FlaskForm):
    """
    Descrição do formulário.
    
    Usado para: ...
    """
    campo1 = StringField("Label", validators=[DataRequired()])
    campo2 = IntegerField("Label", validators=[Optional()])
    submit = SubmitField("Enviar")
```

### 3. Adicionar Função em Thread

```python
# Em app.py

def minha_tarefa_async(parametro: str):
    """
    Descrição da tarefa assíncrona.
    
    Executa em thread separada.
    """
    with app.app_context():
        # Seu código aqui
        pass

# Para executar:
t = threading.Thread(target=minha_tarefa_async, args=(param,))
with manager.lock:
    manager.threads.append(t)
```

### 4. Adicionar Função de Raciocínio

```python
# Em reasoning.py

def novo_metodo(self, parametro: str):
    """
    Descrição do método.
    
    Args:
        parametro: Descrição
    
    Returns:
        Descrição do retorno
    """
    def iterate():
        # Implementação iterativa
        for i in range(self.max_depth):
            # Processar
            yield resultado
    
    return iterate()
```

## 📍 Padrões Comuns

### Pattern: Validação de Usuário

```python
user = User.objects(username=username).first()
if user is None:
    flash("User not found", 'error')
    return redirect(url_for('home'))
```

### Pattern: Busca no MongoDB

```python
# Busca simples
uploads = Upload.objects(creator=user)

# Busca com condição
upload = Upload.objects(filename=path, creator=user).first()

# Busca com regex
uploads = Upload.objects(filename__contains=log_dir)
```

### Pattern: Stream com Turbo-Flask

```python
for chunk in generator:
    if chunk:
        content += chunk
        turbo.push(turbo.update(
            render_template('_fragment.html', data=content),
            'element_id'
        ))
```

### Pattern: Upload de Arquivo

```python
upload_file(
    user=user,
    log_dir='diretorio',
    filename='arquivo.md',
    raw_file=conteudo.encode('utf-8'),
    initial=False
)
```

## 🐛 Debugar Problemas Comuns

### Problema: Thread não inicia
```python
# ❌ Errado
thread.start()
thread.start()  # RuntimeError!

# ✅ Correto
with manager.lock:
    manager.threads.append(thread)
```

### Problema: Arquivo não encontrado
```python
# Verifique o caminho
print(path.join(log_dir, filename))  # debug

# Procure de forma flexível
uploads = Upload.objects(filename__contains=log_dir)
```

### Problema: Contexto de app não disponível
```python
# ❌ Errado
def funcao_em_thread():
    db.save()  # Erro! Sem contexto

# ✅ Correto
def funcao_em_thread():
    with app.app_context():
        db.save()  # OK!
```

### Problema: Sessão perdida em thread
```python
# A sessão está apenas na requisição HTTP
# Para threads, passe dados como argumentos
def funcao_async(username: str, data: str):
    user = User.objects(username=username).first()
    # Use o usuário obtido no banco
```

## 📚 Referência Rápida

### Importações Comuns

```python
# Flask básico
from flask import Flask, render_template, redirect, url_for, session, request, flash

# Banco de dados
from database.db import db, User, Upload, upload_file

# Formulários
from forms.user import SubmitQueryForm, LoginUser, CreateUser

# Raciocínio
from api.model.reasoning import Reasoning

# Threading
from thread_manager import ThreadManager
import threading

# Utilitários
from functools import wraps
import os
```

### Configurações Úteis (app.py)

```python
# Tempo de sessão (em app.py)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)

# Database
app.config['MONGODB_HOST'] = os.getenv("MONGODB_URI")

# Secret key (CSRF, sessions)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
```

### Variáveis de Ambiente Necessárias (.env)

```
SECRET_KEY=sua_chave_secreta_aqui
MONGODB_URI=mongodb://usuario:senha@localhost/database
```

## 🧪 Testar Funcionalidades

### Teste de Rota

```bash
# Terminal 1: Iniciar aplicação
python app.py

# Terminal 2: Testar
curl http://localhost:5000/login
```

### Teste de Banco de Dados

```python
# Em Python repl
from database.db import User

# Criar usuário
user = User(id=1, username='teste', email='teste@test.com')
user.generate_password_hash('senha123')
user.save()

# Verificar
user = User.objects(username='teste').first()
print(user.check_password('senha123'))  # True
```

### Teste de Raciocínio

```python
from api.model.reasoning import Reasoning

thinker = Reasoning(
    api_key='sua_key',
    max_width=3,
    max_depth=2,
    model='deepseek-v3.1:671b-cloud'
)

gen, status = thinker.reasoning_step(
    username='usuario',
    log_dir='teste',
    query='2+2=?',
    init=True
)

for chunk in gen:
    print(chunk, end='', flush=True)
```

## 📝 Convenções de Código

### Nomenclatura

```python
# Variáveis: snake_case
user_name = "João"
log_dir = "problema_1"

# Classes: PascalCase
class Reasoning: pass
class ThreadManager: pass

# Constantes: UPPER_SNAKE_CASE
MAX_DEPTH = 20
API_URL = "https://ollama.com"

# Funções privadas: prefixo _
def _helper_function(): pass
```

### Docstrings

```python
def funcao(param: str) -> str:
    """
    Descrição breve em uma linha.
    
    Descrição detalhada explicando o comportamento,
    casos especiais e notas importantes.
    
    Args:
        param (str): Descrição do parâmetro
    
    Returns:
        str: Descrição do retorno
    
    Raises:
        ValueError: Quando X ocorre
    
    Examples:
        >>> funcao("input")
        'output esperado'
    """
```

### Comentários

```python
# ============================================================================
# SEÇÃO PRINCIPAL
# ============================================================================

# Subsseção importante
def funcao():
    # Comentário inline para lógica complexa
    resultado = (valor1 + valor2) * fator  # Cálculo específico
    return resultado
```

## 🚀 Deployment

### Verificar antes de fazer deploy

```bash
# Verificar sintaxe Python
python -m py_compile *.py

# Verificar dependências
pip freeze > requirements.txt

# Testar importações
python -c "import app"

# Verificar variáveis de ambiente
echo $SECRET_KEY
echo $MONGODB_URI
```

### Iniciar em produção

```bash
# Com Gunicorn (não use debug=True!)
gunicorn -w 4 -b 0.0.0.0:5000 app:app

# Com Gunicorn + Systemd (systemd service)
[Unit]
Description=API Ollama Reasoning
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/app
ExecStart=/path/to/venv/bin/gunicorn -w 4 app:app

[Install]
WantedBy=multi-user.target
```

## 📞 Referências Rápidas

- **Flask docs**: https://flask.palletsprojects.com/
- **WTForms docs**: https://wtforms.readthedocs.io/
- **MongoEngine docs**: http://docs.mongoengine.org/
- **Ollama API**: https://github.com/ollama/ollama/blob/main/docs/api.md

---

**Última atualização**: 28 de Novembro, 2025
**Versão**: 1.0
