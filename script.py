import re
from collections import defaultdict
from functools import lru_cache

from tqdm import tqdm
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, Table, MetaData, and_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import select

from .config import CONFIG

# Database connection details
DATABASE_URI = f"mysql+pymysql://{CONFIG['USER']}:{CONFIG['PASSWORD']}@{CONFIG['HOST']}:{CONFIG['PASSWORD']}/{CONFIG['DATABASE']}"


def parse_questions(x):
    x = re.sub(r"([0-9]+)([а-яa-z])", r"\g<1> \g<2>", x)
    result = defaultdict(list)
    row = re.findall(r"\w+|[^ ]+", x)
    cur_num = 0
    for r in row:
        if r.isdigit():
            if cur_num not in result and cur_num != 0:
                result[cur_num].append("")
            cur_num = int(r)
        elif r in {",", ".", ";", ".,"}:
            continue
        elif r.isalpha():
            if r not in result[cur_num]:
                result[cur_num].append(r)
            elif r == "доп":
                result[0].append(r)
        else:
            print(r)
    if cur_num not in result and cur_num != 0:
        result[cur_num].append("")

    final = []
    for q in result:
        for subq in result[q]:
            subq = subq.replace("a", "а")
            final.append(str(q) + (" " + subq if subq else ""))
    return sorted(final)


# Create database engine and session
engine = create_engine(DATABASE_URI)
Session = sessionmaker(bind=engine)
session = Session()

# Read CSV files
tblCards = pd.read_csv("tblCards.csv").fillna(np.nan).replace([np.nan], [None])
tblSobirately = pd.read_csv("tblSobirately.csv").fillna(np.nan).replace([np.nan], [None])
tblInformators = pd.read_csv("tblInformators.csv").fillna(np.nan).replace([np.nan], [None])

# MetaData for schema reflection
metadata = MetaData()
metadata.reflect(bind=engine)

# Process and insert data from tblCards
texts_table = Table("texts", metadata, autoload_with=engine)
keywords_table = Table("keywords", metadata, autoload_with=engine)
questions_table = Table("questions", metadata, autoload_with=engine)
rayons_table = Table("rayons", metadata, autoload_with=engine)
vills_txt_table = Table("vills_txt", metadata, autoload_with=engine)
years_table = Table("years", metadata, autoload_with=engine)
informators_table = Table("informators", metadata, autoload_with=engine)
vills_inf_table = Table("vills_inf", metadata, autoload_with=engine)
collectors_table = Table("collectors", metadata, autoload_with=engine)

# Mapping tables
t2k_table = Table("t2k", metadata, autoload_with=engine)
t2q_table = Table("t2q", metadata, autoload_with=engine)
t2v_table = Table("t2v", metadata, autoload_with=engine)
t2y_table = Table("t2y", metadata, autoload_with=engine)
t2i_table = Table("t2i", metadata, autoload_with=engine)
t2s_table = Table("t2s", metadata, autoload_with=engine)
vt2r_table = Table("vt2r", metadata, autoload_with=engine)
i2vi_table = Table("i2vi", metadata, autoload_with=engine)

if __name__ == "__main__":
    # Process and insert data from tblSobirately
    for _, row in tblSobirately.iterrows():
        code = row["Код собирателя"]
        name = row["ФИО собирателя"]
        session.execute(collectors_table.insert().values(code=code, name=name))

    def vi_check(village):
        return session.execute(
            select([vills_inf_table.c.id]).where(vills_inf_table.c.v_name == village)
        ).fetchone()

    # Process and insert data from tblInformators
    for _, row in tblInformators.iterrows():
        initials = row["инициалы"]
        name = row["ФИО"]
        bio = row["биография"]
        village = row["село"]

        # Insert informator
        informator_id = session.execute(informators_table.insert().values(code=initials, name=name, bio=bio)).inserted_primary_key[0]

        # Further on: village linking
        if village is None:
            continue
        # Check if village already exists
        existing_village = vi_check(str(village))
        if existing_village:
            village_id = existing_village[0]
        else:
            village_id = session.execute(
                vills_inf_table.insert().values(v_name=village)
            ).inserted_primary_key[0]
        # Link informator to village
        session.execute(i2vi_table.insert().values(i_id=informator_id, v_id=village_id))

    # Process tblCards

    @lru_cache(maxsize=200)
    def keyword_check(keyword):
        return session.execute(
            select([keywords_table.c.id]).where(keywords_table.c.keyword == keyword)
        ).fetchone()

    def vt_check(village):
        return session.execute(
            select([vills_txt_table.c.id]).where(vills_txt_table.c.v_name == village)
        ).fetchone()

    @lru_cache(maxsize=12)
    def rayon_check(rayon):
        return session.execute(
            select([rayons_table.c.id]).where(rayons_table.c.ray == rayon)
        ).fetchone()

    @lru_cache(maxsize=30)
    def year_check(year):
        return session.execute(
            select([years_table.c.id]).where(years_table.c.year == year)
        ).fetchone()

    @lru_cache(maxsize=2000)
    def question_check(quest):
        q_list, q_num, q_let = quest
        return session.execute(
            select([questions_table.c.id]).where(
                and_(questions_table.c.q_list == q_list, questions_table.c.q_num == q_num, questions_table.c.q_let == q_let)
            )
        ).fetchone()

    for idx, row in tqdm(tblCards.iterrows()):
        try:
            # Insert text
            text = row["текст"].replace('\\', '́').replace('_', ' ̄')
            text_id = session.execute(texts_table.insert().values(text=text)).inserted_primary_key[0]

            # Process and link collectors
            for collector_code in [
                row[f"собиратель{i}"] for i in range(1, 5) if row[f"собиратель{i}"] is not None
            ]:
                collector_id_first = (
                    session.query(collectors_table).filter_by(code=collector_code).first()
                )
                if collector_id_first:
                    session.execute(t2s_table.insert().values(t_id=text_id, s_id=collector_id_first.id))

            # Process and link informators
            for informator_initials in [
                row[f"информант{i}"] for i in range(1, 5) if row[f"информант{i}"] is not None
            ]:
                informator_id_first = (
                    session.query(informators_table)
                    .filter_by(code=informator_initials)
                    .first()
                )
                if informator_id_first:
                    session.execute(t2i_table.insert().values(t_id=text_id, i_id=informator_id_first.id))

            # Process and insert keywords
            keywords = (
                re.split(r", +", row["ключевые слова"]) if row["ключевые слова"] is not None else []
            )
            for keyword in keywords:
                # Check if keyword already exists
                keyword = re.sub(r" +", " ", keyword)
                keyword = keyword.capitalize()
                existing_keyword = keyword_check(keyword)
                if existing_keyword:
                    keyword_id = existing_keyword[0]
                    session.execute(t2k_table.insert().values(t_id=text_id, k_id=keyword_id))

            # Process and insert questions
            q_list = row["программа"].replace("а", "a").replace("Х", "X")

            row_question = row["вопрос"] or ""
            # do corrections
            row_question = row_question.replace(";", ",").replace("-", "").replace("?", "").replace(",,", ",")
            row_question = re.sub(r",(?=[^ ])", ", ", row_question)
            # end corrections
            questions = parse_questions(row_question)
            for question in questions:
                q_num, q_let = question.split(" ") if " " in question else (question, "")
                if q_let == 'доп':
                    if q_num == '0':
                        q_num = 'доп'
                    q_let = ''

                existing_question = question_check((q_list, q_num, q_let))
                if existing_question:
                    question_id = existing_question[0]
                    # Link text to question
                    session.execute(t2q_table.insert().values(t_id=text_id, q_id=question_id))
                else:
                    print(q_list, q_num, q_let, sep=" ")

            # Process and insert village, rayons, and years
            rayon, raw_village = row["село"].strip().split(", ")[1:]
            rayon = str(rayon).strip().replace("  ", " ").replace("р-н", "район")
            village = raw_village.split("-")[-1].strip()
            year = str(row["год"]).strip().lower()

            # Check if rayon and year already exist
            existing_village = vt_check(str(village))
            existing_rayon = rayon_check(rayon)
            existing_year = year_check(year)

            rayon_id = existing_rayon[0]
            if existing_village:
                village_id = existing_village[0]
            else:
                village_id = session.execute(
                    vills_txt_table.insert().values(v_name=village)
                ).inserted_primary_key[0]
                session.execute(vt2r_table.insert().values(v_id=village_id, r_id=rayon_id))

            if existing_year:
                year_id = existing_year[0]
                session.execute(t2y_table.insert().values(t_id=text_id, y_id=year_id))

            # Link text to rayon and year
            session.execute(t2v_table.insert().values(t_id=text_id, v_id=village_id))
        except Exception as e:
            print(f"{e}: {str(idx)}: {str(row)}")

    # Commit changes
    session.commit()

    # Close session
    session.close()
