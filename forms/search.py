"""
Formulário de Busca - Search Form

Formulário simples para buscar/filtrar logs de usuários.

Este formulário básico permite ao usuário digitar um termo
de busca para encontrar logs específicos.

Proteção:
- CSRF: Token gerado automaticamente pelo Flask-WTF
"""

from wtforms import StringField, SubmitField
from flask_wtf import FlaskForm


class Search(FlaskForm):
    """
    Formulário simples de busca.
    
    Usado para pesquisar logs e informações de usuários.
    
    Campos:
        query (str): Termo de busca
        submit (SubmitField): Botão de envio
    
    Validações:
        - Nenhuma validação específica (permite buscas vazias)
    
    Exemplos:
        >>> form = Search()
        >>> if form.validate_on_submit():
        ...     query = form.query.data
        ...     # Buscar no banco de dados
    
    Notas:
        - Sem validação obrigatória (permite buscas vazias)
        - Pode ser expandido com validações no futuro
        - Integrado com WTForms para segurança CSRF
    """
    
    # Campo de busca
    query = StringField("Search here: ")
    
    # Botão de envio
    submit = SubmitField("Search ")
