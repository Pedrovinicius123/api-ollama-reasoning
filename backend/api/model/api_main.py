"""
API Principal - Interface com o Servidor Ollama

Este módulo fornece a função principal para comunicar com o servidor
Ollama (llama.cpp compatible) para fazer requisições de chat com raciocínio.

A função faz requisições streaming ao servidor, permitindo receber
respostas token por token à medida que são geradas.

Servidor Ollama:
- Host: https://ollama.com (configurável)
- Autenticação: Bearer token (API key)
- Modelo: Configurável (ex: deepseek-v3.1:671b-cloud)

Dependências:
- ollama: Cliente Python para Ollama
- dotenv: Carregamento de variáveis de ambiente
"""

from ollama import Client
from dotenv import load_dotenv


def make_request_ollama_reasoning(api_key: str, model_name: str, prompt: str, context: str, n_tokens: int):
    """
    Faz uma requisição streaming ao servidor Ollama para raciocínio profundo.
    
    Utiliza o padrão de prompt de dois componentes:
    - System message (context): Contém a instrução do sistema e histórico de raciocínio
    - User message (prompt): Contém a pergunta ou continuação atual
    
    A comunicação com o servidor Ollama é feita via HTTP/HTTPS streaming,
    permitindo processar tokens à medida que são gerados (não espera resposta completa).
    
    Configurações de geração:
    - temperature: 0.01 (muito determinístico, quase sem aleatoriedade)
    - num_predict: Número máximo de tokens a gerar
    - stream: True (habilita streaming de resposta)
    
    Args:
        api_key (str): Token de autenticação Bearer para Ollama
        model_name (str): Nome do modelo a usar (ex: "deepseek-v3.1:671b-cloud")
        prompt (str): Mensagem do usuário/pergunta atual
        context (str): Context histórico incluindo sistema prompt e respostas anteriores
        n_tokens (int): Número máximo de tokens a gerar
    
    Returns:
        Iterator: Gerador que itera sobre os chunks da resposta
                  Cada chunk é um dicionário com 'message' contendo 'content'
    
    Exemplos de Uso:
        >>> api_key = "seu_token_aqui"
        >>> model = "deepseek-v3.1:671b-cloud"
        >>> prompt = "Qual é 2+2?"
        >>> context = "Você é um assistente matemático."
        >>> 
        >>> result = make_request_ollama_reasoning(
        ...     api_key=api_key,
        ...     model_name=model,
        ...     prompt=prompt,
        ...     context=context,
        ...     n_tokens=1000
        ... )
        >>> 
        >>> for chunk in result:
        ...     if 'message' in chunk:
        ...         print(chunk['message']['content'], end='', flush=True)
    
    Estrutura da Requisição:
        {
            "model": "deepseek-v3.1:671b-cloud",
            "messages": [
                {
                    "role": "user",
                    "content": "prompt atual"
                },
                {
                    "role": "system",
                    "content": "contexto e histórico"
                }
            ],
            "options": {
                "temperature": 0.01,  # Baixa aleatoriedade
                "num_predict": 65000  # Max tokens
            },
            "stream": True
        }
    
    Erros Possíveis:
        - ConnectionError: Servidor Ollama não acessível
        - AuthenticationError: API key inválida
        - ModelNotFoundError: Modelo não disponível no servidor
    
    Notas Importantes:
        - Temperature 0.01: Respostas muito determinísticas (ótimo para matemática)
        - Streaming: Respostas são processadas token por token
        - Context: Acumula histórico de raciocínio em profundidade
    """
    # Cria cliente Ollama com autenticação Bearer
    client = Client(
        host="https://ollama.com",
        headers={'authorization': f"Bearer {api_key}"}
    )

    # Faz requisição de chat com streaming habilitado
    result = client.chat(
        model=model_name,
        messages=[
            {
                "role": "user",
                "content": prompt,
            },
            {
                "role": "system",
                "content": context,
            }
        ], 
        options={
            "temperature": 0.01,          # Temperatura muito baixa para respostas determinísticas
            "num_predict": n_tokens,      # Número máximo de tokens
        },
        stream=True                       # Habilita streaming
    )
    
    # Retorna o gerador (iterator) de chunks da resposta
    return result
