import datetime
import hmac
import re
import secrets
from marshmallow.exceptions import ValidationError
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, Response, make_response, abort, session
from flask import render_template, request, url_for, redirect, Markup
from flask_login import login_user, logout_user, login_required, current_user

# from flask_uploads import UploadSet, configure_uploads
from flask_admin import Admin
from sqlalchemy.orm.exc import NoResultFound
from models import *
from admin_models import admin_views, IndexView
from config import CONFIG, ROOT_PATH, SECRET, URL_PREFIX
from db_query import query_wrapper, params
from flask_caching import Cache

db_url = "mysql+pymysql://{}:{}@{}:{}/{}".format(
    CONFIG["USER"],
    CONFIG["PASSWORD"],
    CONFIG["HOST"],
    CONFIG["PORT"],
    CONFIG["DATABASE"],
)

MAX_RESULT = 300
PER_PAGE = 30

query_params = params
ACCENTS = {
    'А́': 'А', 'Е́': 'Е', 'И́': 'И', 'О́': 'О', 'У́': 'У', 'Ы́': 'Ы',
    'Э́': 'Э', 'Ю́': 'Ю', 'Я́': 'Я', 'Ё': 'Ё',
    'а́': 'а', 'е́': 'е', 'и́': 'и', 'о́': 'о', 'у́': 'у',
    'ы́': 'ы', 'э́': 'э', 'ю́': 'ю', 'я́': 'я', 'ё': 'ё'}

get_accents = {item[1] + '\\': item[0] for item in ACCENTS.items()}


def create_app():
    application = Flask(__name__, static_url_path="/static", static_folder="static")
    application.config["MAX_CONTENT_LENGTH"] = 40 * 1024 * 1024
    application.config["APPLICATION_ROOT"] = ROOT_PATH
    application.config["TEMPLATES_AUTO_RELOAD"] = True
    application.config["FLASK_ADMIN_SWATCH"] = "cerulean"
    application.config["SQLALCHEMY_DATABASE_URI"] = db_url
    application.config["SQLALCHEMY_POOL_RECYCLE"] = 280
    application.config["SQLALCHEMY_POOL_TIMEOUT"] = 20
    application.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    application.config["SQLALCHEMY_RECORD_QUERIES"] = False
    application.config["SQLALCHEMY_MAX_OVERFLOW"] = 3
    application.config["SESSION_COOKIE_HTTPONLY"] = True
    application.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    application.config["SECRET_KEY"] = SECRET
    application.config["UPLOAD_FOLDER"] = "static"
    application.secret_key = SECRET
    database.app = application
    database.init_app(application)
    admin = Admin(
        application,
        name="Редакторский раздел",
        template_mode="bootstrap3",
        index_view=IndexView(),
        url="/admin",
    )
    admin = admin_views(admin)
    return application


cache = Cache(config={"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 300})

application = create_app()
login_manager.init_app(application)
cache.init_app(application)

@application.before_request
def protect_state_changes():
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        expected = session.get("csrf_token", "")
        supplied = request.form.get("csrf_token", "") or request.headers.get("X-CSRF-Token", "")
        if not expected or not hmac.compare_digest(expected, supplied):
            abort(400, "Invalid CSRF token")


#
@application.after_request
def after(response):
    if response.mimetype == "text/html" and not response.direct_passthrough:
        body = response.get_data(as_text=True)
        if re.search(r'<form\b[^>]*\bmethod\s*=\s*["\']?post\b', body, re.I):
            token = session.setdefault("csrf_token", secrets.token_urlsafe(32))
            body = re.sub(r'(<form\b[^>]*\bmethod\s*=\s*["\']?post\b[^>]*>)',
                          lambda m: m.group(1) + '<input type="hidden" name="csrf_token" value="' + token + '">',
                          body, flags=re.I)
            response.set_data(body)
    # response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'unsafe-inline'"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["SameSite"] = "Lax"
    return response


@application.context_processor
def add_prefix():
    return dict(prefix=URL_PREFIX)


@application.template_filter('prettify')
def prettify_text(text, html_br=False):
    for i in get_accents:
        if i in text:
            text = text.replace(i, get_accents[i])
    text = text.replace('у%', 'ў').replace('У%', 'Ў').replace('_', '̄').replace("\r\n", "<br/>")
    return text


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@application.route("/login", methods=["POST", "GET"])
def login():
    if request.form:
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).one_or_none()
        if user:
            if check_password_hash(user.password, password):
                login_user(user)
                return redirect("/admin")
        return render_template("login.html", message="Неверное имя или пароль")
    return render_template("login.html", message="")


@application.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


@application.route("/user", methods=["POST", "GET"])
@login_required
def user():
    if request.form:
        user_id = request.form.get("id")
        if user_id != str(current_user.id):
            abort(403)
        password = request.form.get("password")
        if not password:
            abort(400)
        current_user.username = request.form.get("username")
        current_user.password = password  # model listener hashes it
        current_user.email = request.form.get("email")
        database.session.commit()
        return render_template("user.html")
    return render_template("user.html")


def make_json_response(inp: list, schema: object = main_schema):
    response = make_response(schema.dumps(inp, many=True))
    response.headers["Content-Type"] = "application/json"
    return response


def form_txt(texts: list, delim="="):
    text = f"Записей: {str(len(texts))}"
    for item in texts:
        text += """
ID: {}
Год: {}
Место записи: {}
Информанты: {}
Вопрос: {}
Текст: {}
Ключевые слова: {}
{}
        """.format(
            item.id,
            item.year[0].main,
            "; ".join([f"{vill.ray[0].main}, {vill.main}" for vill in item.vill]),
            "; ".join([inf.code for inf in item.informator]),
            "; ".join(
                [f"{q.q_list[0].code} {q.q_num}{q.q_let}" for q in item.question]
            ),
            item.text.replace("\r\n", "\n"),
            "; ".join([keyword.main for keyword in item.keyword]),
            delim * 50,
        )
    response = Response(text, mimetype="text/txt")
    response.headers["Content-Disposition"] = 'attachment; filename="{}.txt"'.format(
        "QueryResult"
    )
    return response


@application.route("/search/", methods=["GET"])
def search():
    context = params
    if not request.args:
        return render_template("search.html", context=context)
    elif len(request.args) == 0:
        return render_template("search.html", context=context)
    try:
        user_params = SearchSchema().load(request.args)
    except ValidationError:
        abort(403)
    # go directly to the page, if id is given
    id = user_params.get("id", None)
    if id:
        return redirect(url_for("text", idx=id))
    # make a request to the api
    if request.args.get("download", None) == "True":
        context = query_wrapper(database, False, **user_params)
        # context = query_wrapper(database, False, **user_params)
        # not downloading empty subsets
        if context["found"] == "Запрос не дал результатов":
            return render_template("search.html", context=context)
        # download
        return form_txt(context["found"])
    # otherwise show results
    # context = query_wrapper(database, True, **user_params)
    context = query_wrapper(database, True, **user_params)
    return render_template("search.html", context=context)


apiMapping = {
    "sobs": {"model": Collectors, "schema": sob_schema},
    "yrs": {"model": Years, "schema": main_schema},
    "infs": {"model": Informants, "schema": inf_schema},
    "prs": {"model": Question_lists, "schema": ql_schema},
    "quests": {"model": Questions, "schema": quest_schema, "related": Question2ql},
    "rays": {"model": Rayons, "schema": main_schema},
    "rvi": {"model": VillsInf, "schema": main_schema, "related": VI2ray},
    "rvt": {"model": VillsTxt, "schema": main_schema, "related": Vill2ray},
    "kws": {"model": Keywords, "schema": main_schema},
}


@application.route("/api/<tabname>")
@cache.cached(timeout=120)
def apiGeneric(tabname):
    if tabname not in apiMapping:
        abort(404)
    result = apiMapping[tabname]["model"].query.all()
    resp = make_json_response(result, apiMapping[tabname]["schema"])
    return resp


@application.route("/api/<tabname>/<int:related>")
@cache.cached(timeout=120)
def apiGenericRelation(tabname, related):
    if tabname not in apiMapping or "related" not in apiMapping[tabname]:
        abort(404)
    mainModel = apiMapping[tabname]["model"]
    rel = apiMapping[tabname]["related"]
    try:
        sub = database.session.query(rel.main).filter(rel.refer == related)
    except NoResultFound:
        abort(404)
    result = (
        database.session.query(mainModel).filter(mainModel.id.in_(sub.subquery())).all()
    )
    resp = make_json_response(result, apiMapping[tabname]["schema"])
    return resp


@application.route("/gallery")
def gallery():
    initial = Pics.query.paginate(per_page=8, page=1)
    return render_template("gallery.html", imgs=initial)


@application.route("/api/pics")
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
        "page_items": galschema.dump(selected_page.items, many=True),
    }
    return page_request_schema.dumps(response)


@application.route("/text/<idx>")
def text(idx):
    text = Texts.query.filter_by(id=idx).one_or_none()
    if text is not None:
        context = {}
        context["id"] = text.id
        context["text"] = prettify_text(Markup.escape(text.text))
        context["year"] = dict(main=text.year[0].main, id=text.year[0].id)
        context["informs"] = text.informator
        context["sobs"] = text.collector
        context["kwords"] = [keyword.main for keyword in text.keyword]
        context["question"] = text.question
        context["vill"] = text.vill
        return render_template("text.html", **context)
    selected = params
    return render_template("search.html", **selected)


#
#
#


@application.route("/index")
@cache.cached(timeout=1800)
def index():
    all_ql = Question_lists.query.all()
    all_r = Rayons.query.all()
    context = dict(
        villnum=database.session.query(VillsTxt).count() // 10 * 10,
        infnum=database.session.query(Informants).count() // 100 * 100,
        curyear=datetime.date.today().year,
        qls=ql_schema.dump(all_ql, many=True),
        rays=main_schema.dump(all_r, many=True),
    )
    return render_template("index.html", **context)


@application.route("/")
def blank():
    return redirect(url_for("index"))


@application.route("/help")
def help_page():
    return render_template("help.html")


@application.route("/about")
def about_page():
    return render_template("about.html")


#
#
#


@application.route("/keywords")
def keyword_page():
    kws = Keywords.query.order_by("keyword").all()
    kw_groups = dict()
    for kw in kws:
        letter = kw.main[0]
        if letter not in kw_groups:
            kw_groups[letter] = []
        kw_groups[letter].append(kw.main)
        
    return render_template("keywords.html", kw_groups=kw_groups)

@application.route("/programs")
def program_page():
    questions = Questions.query.all()
    question_lists = Question_lists.query.order_by("id").all()
    
    question_groups = dict()
    for question in questions:
        if question.q_list:
            question_groups.setdefault(question.q_list[0].id, []).append(question)
    
    return render_template("programs.html", questions=question_groups, qlists=question_lists)


@application.route("/collectors")
@login_required
def collector_page():
    collect = Collectors.query.order_by("name").all()
    return render_template("collectors.html", collectors=collect)


@application.route("/files")
@login_required
def file_page():
    files = Files.query.all()
    return render_template("files.html", files=files)


@application.route("/informants")
@login_required
def informator_page():
    infs = Informants.query.order_by("name").all()
    return render_template("informants.html", informants=infs)


if __name__ == "__main__":
    application.run(host="0.0.0.0")
