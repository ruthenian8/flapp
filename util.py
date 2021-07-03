import sqlalchemy as db
import json
import pickle
from config import CONFIG
from sqlalchemy.orm.session import sessionmaker
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session
from models import main_schema
from lunr import lunr, get_default_builder

db_url = "mysql+pymysql://{}:{}@{}:{}/{}".format(
    CONFIG["USER"],
    CONFIG["PASSWORD"],
    CONFIG["HOST"],
    CONFIG["PORT"],
    CONFIG["DATABASE"]
)

engine = db.create_engine(db_url)
Session = sessionmaker(autoflush=False, bind=engine)
session = scoped_session(Session)
Model = declarative_base(name="Model")
Model.query = session.query_property()

class Texts(Model):
    __tablename__ = "texts"
    id = db.Column("id", db.Integer, primary_key=True, autoincrement=True)
    main = db.Column("text", LONGTEXT)
    # keyword = db.relationship("Keywords", secondary="t2k")
    # year = db.relationship("Years", secondary="t2y")
    # informator = db.relationship("Informants", secondary="t2i")
    # collector = db.relationship("Collectors", secondary="t2s")
    # file = db.relationship("Files", secondary="t2f")
    # question = db.relationship("Questions", secondary="t2q")
    # vill = db.relationship("VillsTxt", secondary="t2v")
    def __repr__(self):
        # return f'{{"id":"{self.id}","main":"{self.text}"}}'
        return json.dumps(dict(id=self.id, main=self.main))

builder = get_default_builder(languages="ru")
builder.metadata_whitelist.append("position")
lunr_index = lunr(
    ref="id",
    fields=["id", "main"],
    documents=[main_schema.loads(str(i), many=False) for i in Texts.query.all()],
    builder=builder)

with open("byteindex", "wb+") as newfile:
    pickle.dump(lunr_index, newfile)