import pandas as pd
import sqlalchemy as db
import json
import pickle
import re
import os
from config import CONFIG
from sqlalchemy.schema import Table
from sqlalchemy import MetaData, Column, Integer, update
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
    CONFIG["DATABASE"],
)

engine = db.create_engine(db_url)
Session = sessionmaker(autoflush=False, bind=engine)
session = scoped_session(Session)
Model = declarative_base(name="Model")
Model.query = session.query_property()
metadata = MetaData()
target = Table(
    "texts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("text", LONGTEXT),
)

#tab = pd.read_excel("newnord.xlsx")
#col = tab["текст"]
#try:
#    for idx, obj in enumerate(col):
#        statement = update(target).where(target.c.id == idx + 1).values({"text": obj})
#        session.execute(statement)
#    else:
#        session.commit()
#except:
#    session.rollback()
#    print("error updating")
#    os.exit(-1)


class Texts(Model):
    __tablename__ = "texts"
    id = db.Column("id", db.Integer, primary_key=True, autoincrement=True)
    main = db.Column("text", LONGTEXT)

    def __repr__(self):
        # return f'{{"id":"{self.id}","main":"{self.text}"}}'
        return json.dumps(dict(id=self.id, main=self.main))


docs = [main_schema.loads(str(i), many=False) for i in Texts.query.all()]


def callback(item):
    newitem = item.copy()
    newitem["main"] = re.sub(r"́", "", item["main"])
    return newitem


newdocs = [i for i in map(callback, docs)]

builder = get_default_builder(languages="ru")
builder.metadata_whitelist.append("position")
lunr_index = lunr(ref="id", fields=["id", "main"], documents=newdocs, builder=builder)

with open("byteindex", "wb+") as newfile:
    pickle.dump(lunr_index, newfile)
