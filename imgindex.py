import os
from config import CONFIG
from sqlalchemy import Table, MetaData, Integer, Column, create_engine, engine
from sqlalchemy.dialects.mysql import VARCHAR
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import insert
from sqlalchemy.orm.session import sessionmaker
from sqlalchemy.orm import scoped_session

folderName = "imgs/"
if not os.path.isdir("static/imgs"):
    os.exit(-1)
files = [i for i in os.listdir("static/imgs")]
baseUri = "mysql+pymysql://{}:{}@{}:{}/{}".format(
    CONFIG["USER"],
    CONFIG["PASSWORD"],
    CONFIG["HOST"],
    CONFIG["PORT"],
    CONFIG["DATABASE"],
)
engine = create_engine(baseUri)
Session = sessionmaker(autoflush=False, bind=engine)
session = scoped_session(Session)
Model = declarative_base(name="Model")
Model.query = session.query_property()
metadata = MetaData()
target = Table(
    "imgs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("path", VARCHAR(50)),
)

for idx, obj in enumerate(files):
    try:
        statement = insert(target).values({"path": folderName + obj})
        session.execute(statement)
    except Exception as e:
        print(e)
        session.rollback()
        break
else:
    session.commit()
    print("table filled")
