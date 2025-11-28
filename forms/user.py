from wtforms import StringField, SubmitField, IntegerField, PasswordField
from wtforms.validators import DataRequired, Optional, NumberRange, Email, EqualTo
from flask_wtf import FlaskForm
from database.db import User

class SubmitQueryForm(FlaskForm):
    query = StringField("Query ", validators=[DataRequired()])
    context = StringField("AI context ", validators=[DataRequired()])
    api_key = StringField("Your Ollama API key", validators=[DataRequired()])
    log_dir = StringField("Logging Dir Temp", validators=[Optional()])
    n_tokens = IntegerField("Number of tokens (max)", validators=[Optional()])
    max_depth = IntegerField("Max Depth", validators=[DataRequired(), NumberRange(2, 20)])
    max_width = IntegerField("Max Width", validators=[DataRequired(), NumberRange(2, 10)])
    model_name = StringField("Model name", validators=[Optional()])
    submit = SubmitField('submit')

class CreateArticle(FlaskForm):
    log_dir = StringField("Directory to parse", validators=[DataRequired()])
    n_iterations = IntegerField("Number of pages", validators=[DataRequired()])
    api_key = StringField("Ollama API key", validators=[DataRequired()])
    model = StringField("Model", validators=[Optional()])
    submit = SubmitField("Create Article")

class CreateUser(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), EqualTo('confirm', message="Passwords must match")])
    confirm = PasswordField("Confirm Password", validators=[DataRequired()])
    submit = SubmitField("Register")

class LoginUser(FlaskForm):
    username_or_email = StringField("Username or email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")

