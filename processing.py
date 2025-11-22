from flask import Blueprint, redirect, url_for, stream_with_context, Response, flash
from api.model.reasoning import Reasoning
from database.db import Upload
import os
import time

bp_processing_api = Blueprint("bp_processing_api", __name__)
thinker = Reasoning("", 0, 0)

@bp_processing_api.route('/process?query=<query>&log_dir=<log_dir>&model=<model>&max_width=<int:max_width>&max_depth=<int:max_depth>&n_tokens=<int:n_tokens>&api_key=<api_key>')
def process(query, log_dir, model, max_width, max_depth, n_tokens, api_key):
    obj_context = Upload.objects(filename__contains=os.path.join(log_dir, 'context.md')).first()
    if not query:
        flash("No query provided", "error")
        return redirect(url_for('home'))

    # set model and numeric parameters
    if model:
        thinker.model = model

    try:
        thinker.max_width = int(max_width) if max_width is not None else thinker.max_width
    except Exception:
        thinker.max_width = thinker.max_width
    
    thinker.api_key = api_key
    thinker.max_depth = int(max_depth) if max_depth is not None else thinker.max_depth
    thinker.n_tokens_default = int(n_tokens) if n_tokens is not None else thinker.n_tokens_default
    print(thinker.max_depth, obj_context.depth)
    time.sleep(1)

    result = thinker.reasoning_step(
        username=obj_context.creator.username,
        log_dir=log_dir,
        query=query,
        init=obj_context.depth == 0,
    )

    return Response(stream_with_context(result), content_type='text/plain'), 200

@bp_processing_api.route('/create_article?username=<username>&log_dir=<log_dir>&model=<model>&iteration=<int:iteration>&api_key=<api_key>', methods=['GET'])
def create_article(username, log_dir, model, iteration, api_key):
    obj_response = Upload.objects(filename__contains=os.path.join(log_dir, 'response.md')).first()
    obj_context = Upload.objects(filename__contains=os.path.join(log_dir, 'context.md')).first()

    if obj_response is None or obj_context is None:
        return redirect(url_for('home'))

    # set model and numeric parameters
    if model:
        thinker.model = model
    
    thinker.api_key = api_key
    result = thinker.generate_article_step(
        username=username,
        log_dir=log_dir,
        iteration=iteration,
        content=obj_response.file.read().decode('utf-8')
    )

    return Response(stream_with_context(result), content_type='text/plain'), 200
