from sqlalchemy.dialects.mysql import VARCHAR, YEAR, TINYTEXT, LONGTEXT
from flask_login import LoginManager, UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from werkzeug.security import generate_password_hash
import json
from marshmallow import fields, Schema, validate

database = SQLAlchemy()
login_manager = LoginManager()


class FkColumn(database.Column):
    """Easier creation for a foreign key column"""

    def __init__(self, colname: str, refers: str):
        super(FkColumn, self).__init__(
            colname, database.Integer, database.ForeignKey(refers)
        )


def common_repr(self):
    """Representation for a non-relational table"""
    return json.dumps(dict(id=self.id, main=self.main), ensure_ascii=False)


class MainSchema(Schema):
    id = fields.Int(required=True)
    main = fields.Str(required=True)


main_schema = MainSchema(many=True)


def rel_table_repr(self):
    """Representation for a relational table"""
    return f"{self.id}: entry {self.main} maps to {self.refer}"


roles = {"admin": 0, "editor": 1, "user": 2}


class SearchSchema(Schema):
    id = fields.Int()
    FT = fields.Str()
    keywords = fields.Str()
    q_list = fields.Int()
    questions = fields.Str()
    year = fields.Int()
    inf = fields.Int()
    sob = fields.Int()
    ray = fields.Int()
    vill_txt = fields.Int()
    vill_inf = fields.Int()
    page = fields.Int(required=True)
    download = fields.Str()


class User(UserMixin, database.Model):
    __tablename__ = "users"
    id = database.Column("id", database.Integer, primary_key=True, autoincrement=True)
    username = database.Column("username", TINYTEXT)
    role = database.Column("role", TINYTEXT)
    password = database.Column("password", TINYTEXT)
    email = database.Column("email", TINYTEXT)

    def __repr__(self):
        return f"{self.username}: {self.role}"

    def has_roles(self, role):
        cur = roles.get(self.role, 10)
        inp = roles.get(role, 0)
        return cur <= inp

    def roles_range(self, role_lower, role_upper):
        cur = roles.get(self.role, 10)
        low = roles.get(role_lower, 0)
        up = roles.get(role_upper, 0)
        return (low <= cur) and (cur <= up)


@event.listens_for(User.password, "set", retval=True)
def hash_user_password(target, value, oldvalue, initiator):
    if value != oldvalue:
        return generate_password_hash(value)
    return value


class Years(database.Model):
    __tablename__ = "years"
    id = database.Column("id", database.Integer, primary_key=True, autoincrement=True)
    main = database.Column("year", YEAR(4))

    def __repr__(self):
        json.dumps(dict(id=self.id, main=str(self.main)), ensure_ascii=False)


class Keywords(database.Model):
    __tablename__ = "keywords"
    id = database.Column("id", database.Integer, primary_key=True, autoincrement=True)
    main = database.Column("keyword", VARCHAR(45))
    __repr__ = common_repr


class Rayons(database.Model):
    __tablename__ = "rayons"
    id = database.Column("id", database.Integer, primary_key=True, autoincrement=True)
    main = database.Column("ray", TINYTEXT)
    __repr__ = common_repr


class Files(database.Model):
    __tablename__ = "files"
    id = database.Column("id", database.Integer, primary_key=True, autoincrement=True)
    main = database.Column("name", VARCHAR(80))
    __repr__ = common_repr


class VillsInf(database.Model):
    __tablename__ = "vills_inf"
    id = database.Column("id", database.Integer, primary_key=True, autoincrement=True)
    main = database.Column("v_name", VARCHAR(25))
    ray = database.relationship("Rayons", secondary="vi2r")
    __repr__ = common_repr


class VillsTxt(database.Model):
    __tablename__ = "vills_txt"
    id = database.Column("id", database.Integer, primary_key=True, autoincrement=True)
    main = database.Column("v_name", VARCHAR(25))
    ray = database.relationship("Rayons", secondary="vt2r")
    __repr__ = common_repr


class Informants(database.Model):
    __tablename__ = "informators"
    id = database.Column("id", database.Integer, primary_key=True, autoincrement=True)
    name = database.Column("name", TINYTEXT)
    code = database.Column("code", VARCHAR(8))
    bio = database.Column("bio", database.Text)
    vill = database.relationship("VillsInf", secondary="i2vi")

    def __repr__(self):
        return json.dumps(dict(id=self.id, code=self.code, name=self.name), ensure_ascii=False)


class InfSchema(Schema):
    id = fields.Int(reqired=True)
    code = fields.Str(required=True)
    name = fields.Str(required=True)


inf_schema = InfSchema(many=True)


class Collectors(database.Model):
    __tablename__ = "collectors"
    id = database.Column("id", database.Integer, primary_key=True, autoincrement=True)
    name = database.Column("name", TINYTEXT)
    code = database.Column("code", VARCHAR(8))

    def __repr__(self):
        return json.dumps(dict(id=self.id, code=self.code, name=self.name), ensure_ascii=False)


class SobSchema(Schema):
    id = fields.Int(reqired=True)
    name = fields.Str(required=True)
    code = fields.Str(required=True)


sob_schema = SobSchema(many=True)


class Questions(database.Model):
    __tablename__ = "questions"
    id = database.Column("id", database.Integer, primary_key=True, autoincrement=True)
    q_list = database.relationship("Question_lists", secondary="q2ql")
    q_num = database.Column("q_num", VARCHAR(5))
    q_let = database.Column("q_let", VARCHAR(3))
    q_txt = database.Column("q_txt", database.Text)
    q_theme = database.Column("q_theme", database.Text)

    def __repr__(self):
        return json.dumps(
            dict(id=self.id, code=self.q_num + self.q_let, name=self.q_txt), ensure_ascii=False
        )


class QuestSchema(Schema):
    id = fields.Int(required=True)
    q_list = fields.Nested(lambda: QLSchema())
    q_num = fields.Str(required=True)
    q_let = fields.Str(required=True)
    q_txt = fields.Str(required=True)


quest_schema = QuestSchema(many=True)


class Question_lists(database.Model):
    __tablename__ = "q_lists"
    id = database.Column("id", database.Integer, primary_key=True, autoincrement=True)
    code = database.Column("code", VARCHAR(8))
    name = database.Column("name", VARCHAR(50))

    def __repr__(self):
        return json.dumps(dict(id=self.id, code=self.code, name=self.name), ensure_ascii=False)


class QLSchema(Schema):
    id = fields.Int(required=True)
    code = fields.Str(required=True)
    name = fields.Str(required=True)


ql_schema = QLSchema(many=True)


class Texts(database.Model):
    __tablename__ = "texts"
    id = database.Column("id", database.Integer, primary_key=True, autoincrement=True)
    text = database.Column("text", LONGTEXT)
    keyword = database.relationship("Keywords", secondary="t2k")
    year = database.relationship("Years", secondary="t2y")
    informator = database.relationship("Informants", secondary="t2i")
    collector = database.relationship("Collectors", secondary="t2s")
    file = database.relationship("Files", secondary="t2f")
    question = database.relationship("Questions", secondary="t2q")
    vill = database.relationship("VillsTxt", secondary="t2v")

    def __repr__(self):
        return json.dumps(dict(id=self.id, main=self.text[:100]), ensure_ascii=False)


class TextSchema(Schema):
    id = fields.Int(required=True)
    text = fields.Str(required=True)
    year = fields.Nested(lambda: MainSchema())
    vill = fields.Nested(lambda: MainSchema())
    keyword = fields.List(fields.Nested(lambda: MainSchema()))
    informator = fields.List(fields.Nested(lambda: InfSchema()))
    collector = fields.List(fields.Nested(lambda: SobSchema()))
    question = fields.List(fields.Nested(lambda: QuestSchema()))


text_schema = TextSchema()


class Pics(database.Model):
    __tablename__ = "imgs"
    id = database.Column("id", database.Integer, primary_key=True, autoincrement=True)
    path = database.Column("path", VARCHAR(50))
    descr = database.Column("descr", VARCHAR(255))


class PicSchema(Schema):
    id = fields.Int(required=True)
    path = fields.Str(required=True)
    descr = fields.Str()


galschema = PicSchema()


class PageRequestSchema(Schema):
    pages = fields.Int(required=True, validate=validate.Range(min=0))
    page_items = fields.List(fields.Nested(lambda: PicSchema()), required=False)


page_request_schema = PageRequestSchema()


class Text2vill(database.Model):
    __tablename__ = "t2v"
    id = database.Column("id", database.Integer, primary_key=True, autoincrement=True)
    main = FkColumn("t_id", "texts.id")
    refer = FkColumn("v_id", "vills_txt.id")
    __repr__ = rel_table_repr


class Inf2vill(database.Model):
    __tablename__ = "i2vi"
    id = database.Column("id", database.Integer, primary_key=True, autoincrement=True)
    main = FkColumn("i_id", "informators.id")
    refer = FkColumn("v_id", "vills_inf.id")
    __repr__ = rel_table_repr


class Vill2ray(database.Model):
    __tablename__ = "vt2r"
    id = database.Column("id", database.Integer, primary_key=True, autoincrement=True)
    main = FkColumn("v_id", "vills_txt.id")
    refer = FkColumn("r_id", "rayons.id")
    __repr__ = rel_table_repr


class VI2ray(database.Model):
    __tablename__ = "vi2r"
    id = database.Column("id", database.Integer, primary_key=True, autoincrement=True)
    main = FkColumn("v_id", "vills_inf.id")
    refer = FkColumn("r_id", "rayons.id")
    __repr__ = rel_table_repr


class Text2year(database.Model):
    __tablename__ = "t2y"
    id = database.Column("id", database.Integer, primary_key=True, autoincrement=True)
    main = FkColumn("t_id", "texts.id")
    refer = FkColumn("y_id", "years.id")
    __repr__ = rel_table_repr


class Text2key(database.Model):
    __tablename__ = "t2k"
    id = database.Column("id", database.Integer, primary_key=True, autoincrement=True)
    main = FkColumn("t_id", "texts.id")
    refer = FkColumn("k_id", "keywords.id")
    __repr__ = rel_table_repr


class Text2quest(database.Model):
    __tablename__ = "t2q"
    id = database.Column("id", database.Integer, primary_key=True, autoincrement=True)
    main = FkColumn("t_id", "texts.id")
    refer = FkColumn("q_id", "questions.id")
    __repr__ = rel_table_repr


class Text2file(database.Model):
    __tablename__ = "t2f"
    id = database.Column("id", database.Integer, primary_key=True, autoincrement=True)
    main = FkColumn("t_id", "texts.id")
    refer = FkColumn("f_id", "files.id")
    __repr__ = rel_table_repr


class Text2sob(database.Model):
    __tablename__ = "t2s"
    id = database.Column("id", database.Integer, primary_key=True, autoincrement=True)
    main = FkColumn("t_id", "texts.id")
    refer = FkColumn("s_id", "collectors.id")
    __repr__ = rel_table_repr


class Text2inf(database.Model):
    __tablename__ = "t2i"
    id = database.Column("id", database.Integer, primary_key=True, autoincrement=True)
    main = FkColumn("t_id", "texts.id")
    refer = FkColumn("i_id", "informators.id")
    __repr__ = rel_table_repr


class Question2ql(database.Model):
    __tablename__ = "q2ql"
    id = database.Column("id", database.Integer, primary_key=True, autoincrement=True)
    main = FkColumn("q_id", "questions.id")
    refer = FkColumn("ql_id", "q_lists.id")
    __repr__ = rel_table_repr
