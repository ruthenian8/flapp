import os
import flask_admin as flask_admin
from flask_admin import expose
from wtforms.fields import PasswordField
from flask_admin.contrib.sqla import ModelView
from flask_admin.base import MenuLink
from flask_login import current_user
from flask import redirect, url_for
from jinja2 import Markup
from flapp.models import *

class BaseView(ModelView):
    """Class for admin models"""
    page_size = 25
    can_export = True
    column_display_pk = True

    def is_accessible(self):
        if not current_user.is_authenticated:
            return False
        elif current_user.has_roles("user"):
            return False
        return True

    def inaccessible_callback(self, name, **kwargs):
        return login(url_for("login"))

class UserView(BaseView):
    form_choices = {
        "role": [
            ("admin", "Администратор"),
            ("editor", "Редактор"),
            ("user", "Пользователь")
        ]
    }

    form_extra_fields = {
        "new_password": PasswordField("New Password")
    }
    form_columns = ("username", "role", "email", "new_password")
    column_list = ("username", "role", "email")

    def is_accessible(self):
        if not current_user.is_authenticated:
            return False
        if not current_user.has_roles("admin"):
            return False
        self.can_delete = True
        self.can_create = True
        self.can_edit = True
        return True

    def on_model_change(self, form, User, is_created=False):
        User.Password = form.new_password.data

class EditorView(BaseView):
    def is_accessible(self):
        if not current_user.is_authenticated:
            return False
        if current_user.has_roles("editor"):
            self.can_delete = True
            self.can_create = True
            self.can_edit = True
        return True

def admin_views(admin):
    """Function that adds the administrator views"""
    admin.add_view(UserView(User, database.session, category="Участники", name="Пользователи"))
    admin.add_view(EditorView(Collectors, database.session, category="Участники", name="Собиратели"))
    admin.add_view(EditorView(Informants, database.session, category="Участники", name="Информанты"))
    admin.add_view(EditorView(Texts, database.session, category="Метаданные", name="Тексты"))
    admin.add_view(EditorView(Keywords, database.session, category="Метаданные", name="Ключевые слова"))
    admin.add_view(EditorView(Questions, database.session, category="Метаданные", name="Вопросы"))
    admin.add_view(EditorView(VillsInf, database.session, category="Геоданные", name="Место жительства информанта"))
    admin.add_view(EditorView(VillsTxt, database.session, category="Геоданные", name="Место записи текста"))
    admin.add_view(EditorView(Rayons, database.session, category="Геоданные", name="Районы записи"))
    admin.add_link(MenuLink(name="Вернуться на сайт", url="/"))
    return admin


class IndexView(flask_admin.AdminIndexView):
    @expose("/")
    def index(self):
        if not current_user.is_authenticated:
            return redirect(url_for("login"))
        return super(IndexView, self).index()