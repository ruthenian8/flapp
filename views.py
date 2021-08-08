import copy
import json
import os
import re
from urllib.parse import quote
from collections import defaultdict
from datetime import datetime
import numpy as np
import pandas as pd

from sqlalchemy import and_, text as sql_text
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, Response, make_response, jsonify, send_file, safe_join, abort
from flask import render_template, request, url_for, redirect
from flask_login import login_user, logout_user, login_required
from flask_paginate import Pagination, get_page_parameter
# from flask_uploads import UploadSet, configure_uploads
from flask_admin import Admin
from sqlalchemy.orm.exc import NoResultFound
from flapp.models import *
from flapp.admin_models import admin_views, IndexView
from flapp.config import CONFIG, ROOT_PATH, SECRET, URL_PREFIX
from flapp.db_query import query_wrapper, nonedict, unique_not_none, params

db_url = "mysql+pymysql://{}:{}@{}:{}/{}".format(
    CONFIG["USER"],
    CONFIG["PASSWORD"],
    CONFIG["HOST"],
    CONFIG["PORT"],
    CONFIG["DATABASE"]
)

MAX_RESULT = 300
PER_PAGE = 30

query_params = params

def create_app():
    app = Flask(__name__,
        static_url_path='/static',
        static_folder='static')
    app.config["MAX_CONTENT_LENGTH"] = 40 * 1024 * 1024
    app.config["APPLICATION_ROOT"] = ROOT_PATH
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.config["FLASK_ADMIN_SWATCH"] = "cerulean"
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_RECORD_QUERIES"] = False
    app.config["SQLALCHEMY_MAX_OVERFLOW"] = 3
    app.config["SECRET_KEY"] = SECRET
    app.config["UPLOAD_FOLDER"] = "static"
    app.secret_key = SECRET
    database.app = app
    database.init_app(app)
    admin = Admin(
        app,
        name="Редакторский раздел",
        template_mode="bootstrap3",
        index_view=IndexView(),
        url="/admin"
    )
    admin = admin_views(admin)
    return app

app = create_app()
login_manager.init_app(app)

#
@app.after_request
def after(response):
    # response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'unsafe-inline'"
    response.headers['X-Content-Type-Options'] = "nosniff"
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Cross-Origin-Resource-Policy']='same-origin'
    response.headers['SameSite']='Lax'
    return response

@app.context_processor
def add_prefix():
    return dict(prefix=URL_PREFIX)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route("/login", methods=['POST', 'GET'])
def login():
    if request.form:
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).one_or_none()
        if user:
            if check_password_hash(user.password, password):
                login_user(user)
                return render_template("login.html", message="Добро пожаловать, {}".format(username))
        return render_template("login.html", message="Неверное имя или пароль")
    return render_template("login.html", message="")

@app.route("/logout")
@login_required
def logout(): 
    logout_user()
    return redirect(url_for('index'))

@app.route('/user', methods=["POST", "GET"])
@login_required
def user():
    if request.form:
        user_id = request.form.get("id")
        password = generate_password_hash(request.form.get("password"))
        email = request.form.get("email")
        username = request.form.get("username")
        if User.query.filter_by(id=user_id).one_or_none():
            current_user = User.query.filter_by(id=user_id).one()
            current_user.username = username
            current_user.password = password
            current_user.email = email
            database.session.flush()
            database.session.refresh(current_user)
            database.session.commit()
        return render_template("user.html")
    return render_template("user.html")

def make_json_response(inp:list, schema:object=main_schema):
    response = make_response(schema.dumps(inp, many=True))
    response.headers["Content-Type"] = "application/json"
    return response

@app.route('/search/', methods=["GET"])
def search():
    context = params
    if request.args:
        try:
            # The code in the comments is an alternative way of validating the input (does not work)
            # user_params = request.args.copy()
            # assert "page" in user_params
            # for key in user_params.keys():
            #     if not user_params[key]:
            #         del user_params[key]
            #         continue
            #     if key not in ["FT", "keywords"]:
            #         user_params[key] = int(user_params[key])
            user_params = SearchSchema().load(request.args)
        except:
            abort(404)
        # go directly to the page, if id is given
        id = user_params.get("id", None)
        if id:
            return redirect(url_for("text",
            idx=id))
        # make a request to the api
        context = query_wrapper(database, **user_params)
        return render_template("search.html", **context)
    return render_template("search.html", **context)

@app.route("/api/yrs")
def year():
    all_y = Years.query.all()
    resp = make_json_response(all_y, main_schema)
    return resp

@app.route('/api/infs')
def infs():
    all_infs = Informants.query.all()
    resp = make_json_response(all_infs, inf_schema)
    return resp

@app.route('/api/prs')
def q_lists():
    all_ql = Question_lists.query.all()
    resp = make_json_response(all_ql, ql_schema)
    return resp

@app.route("/api/qlist/<pr_id>")
def q_by_list(pr_id):
    try:
        in_ql = [item.id for item in Question2ql.query.filter(Question2ql.refer==int(pr_id)).all()]
    except NoResultFound:
        abort(404)
    qs = database.session.query(Questions).filter(Questions.id.in_(in_ql)).all()
    resp = make_json_response(qs, quest_schema)
    return resp

@app.route("/api/quests")
def all_qs():
    qs = database.session.query(Questions).all()
    resp = make_json_response(qs, quest_schema)
    return resp

@app.route("/api/rays")
def rayon():
    all_r = Rayons.query.all()
    resp = make_json_response(all_r, main_schema)
    return resp

@app.route('/api/rvi')
def all_v_inf():
    vil = database.session.query(VillsInf).all()
    resp = make_json_response(vil, main_schema)
    return resp

@app.route('/api/rvi/<r_id>')
def v_inf(r_id):
    in_r = database.session.query(VI2ray.main).filter(VI2ray.refer == r_id)
    vil = database.session.query(VillsInf).filter(VillsInf.id.in_(in_r.subquery())).all()
    resp = make_json_response(vil, main_schema)
    return resp

@app.route("/api/rvt")
def all_v_txt():
    vil = database.session.query(VillsTxt).all()
    resp = make_json_response(vil, main_schema)
    return resp

@app.route("/api/rvt/<r_id>")
def v_txt(r_id):
    in_r = database.session.query(Vill2ray.main).filter(Vill2ray.refer == r_id)
    vil = database.session.query(VillsTxt).filter(VillsTxt.id.in_(in_r.subquery())).all()
    resp = make_json_response(vil, main_schema)
    return resp

@app.route("/api/kws")
def kws():
    all_k = Keywords.query.all()
    resp = make_json_response(all_k, main_schema)
    return resp

@app.route("/gallery")
def gallery():
    initial = Pics.query.paginate(per_page=8, page=1)
    return render_template('gallery.html', imgs=initial)

@app.route("/api/pics")
def pics():
    try:
        arg = page_request_schema.load(request.args)
    except Exception as e:
        print(e)
        abort(403)
    selected_page = Pics.query.paginate(per_page=4, page=arg["pages"])
    print(selected_page.items)
    response = {
        "pages": selected_page.pages,
        "page_items": galschema.dump(selected_page.items, many=True)
    }
    return page_request_schema.dumps(response)

@app.route("/text/<idx>")
def text(idx):
    text = Texts.query.filter_by(id=idx).one_or_none()
    if text is not None:
        context = {}
        context["id"] = text.id
        context["text"] = text.text
        context["year"] = dict(main=text.year[0].main, id=text.year[0].id)
        context["informs"] = text.informator
        context["kwords"] = [keyword.main for keyword in text.keyword]
        context["question"] = text.question
        context["vill"] = text.vill
        return render_template("text.html", **context)
    selected = params
    return render_template("search.html", **selected)

#
#
#

@app.route("/index")
def index():
    all_ql = Question_lists.query.all()
    qls = ql_schema.dump(all_ql, many=True)
    all_r = Rayons.query.all()
    rays = main_schema.dump(all_r, many=True)   
    return render_template("index.html", qls=qls, rays=rays)

@app.route("/")
def blank():
    return redirect(url_for("index"))

@app.route("/help")
def help_page():
    return render_template("help.html")

@app.route("/about")
def about_page():
    return render_template("about.html")
#
#
#

@app.route("/keywords")
@login_required
def keyword_page():
    kws = Keywords.query.order_by("keyword").all()
    return render_template('keywords.html', keywords=kws)

@app.route("/collectors")
@login_required
def collector_page():
    collect = Collectors.query.order_by("name").all()
    return render_template("collectors.html", collectors=collect)

@app.route("/files")
@login_required
def file_page():
    files = Files.query.all()
    return render_template("files.html", files=files)

@app.route("/informants")
@login_required
def informator_page():
    infs = Informants.query.order_by("name").all()
    return render_template("informants.html", informants=infs)