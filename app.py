from flask import Flask, render_template, redirect, url_for
from forms.user import SubmitQueryForm
from markupsafe import Markup
from markdown import markdown
from database import db, upload_file, Upload
from api.model.reasoning import Reasoning
from dotenv import load_dotenv
import threading
import os

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
app.config['MONGODB_HOST'] = os.getenv("MONGODB_URI")

# Simple set of threads
threads = []
db.init_app(app)

def read_markdown_to_html(log_dir:str):
    objs = Upload.objects(filename__contains=log_dir)
    markdown_content = ""
    for obj in objs:
        markdown_content += '\n\n' + obj.file.read().decode('utf-8')

    html_code = markdown(markdown_content)
    return Markup(html_code)

@app.route("/")
def home():
    # Simple thread handling
    print(threads)
    for thread in threads:
        if not thread.is_alive():
            try:
                thread.start()

            except:
                thread.join()
                threads.remove(thread)

    return render_template('index.html')

@app.route("/<log_dir>")
def read(log_dir:str):
    result = read_markdown_to_html(log_dir)
    if result:
        return render_template('response.html', aditional_code=result)

    return "Log directory not found.", 404

@app.route("/load_log_dir/<log_dir>")
def load(log_dir:str):
    for file in os.listdir(os.path.join('/tmp', log_dir, 'steps')):
        with open(os.path.join('/tmp', log_dir, 'steps', file), 'rb') as f:
            raw = f.read()
            upload_file(temp_log_dir=log_dir, filename=file, raw_file=raw)

    return redirect(url_for('home'))


@app.route("/submit_question", methods=["GET", "POST"])
def submit_question():
    form = SubmitQueryForm()
    if form.validate_on_submit():
        # Form validation and processing

        query = form.query.data
        context = form.context.data
        log_dir_temp = form.log_dir.data or 'default_log'
        n_tokens = form.n_tokens.data if form.n_tokens.data is not None else 100000 # Default value
        model_name = form.model_name.data if form.model_name.data else "deepseek-v3.1:671b-cloud"
        max_depth = form.max_depth.data

        # Generates and stores the raw data on database
        threads.append(threading.Thread(target=generate, args=(log_dir_temp, query, context, n_tokens, model_name, max_depth)))
        return redirect(url_for('home'))
    
    return render_template('form.html', form=form)

def generate(log_dir:str, query:str, context:str, n_tokens:int, model_name:str, max_depth:int):
    thinker = Reasoning(
        max_width=5,
        max_depth=max_depth,
        model_name=model_name if model_name else "deepseek-v3.1:671b-cloud",
        n_tokens_default=n_tokens

    )
    # Retorna o resultado da cadeia de raciocínio para que possamos repassar à rota Flask
    #print(query, context, log_dir)
    return thinker.reasoning_step(query=query, context=context, log_dir=log_dir)
    

if __name__ == '__main__':
    app.run(debug=True)
