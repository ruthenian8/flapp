from sqlalchemy import and_, not_
from flapp.models import *
import os
import pickle
import re

PAGINATION_ITEMS = 10

def unpickle_index(idx_name="byteindex"):
    with open("flapp/" + idx_name, "rb") as bytefile:
        index = pickle.load(bytefile)
    return index
lunr_index = unpickle_index("byteindex")

nonedict = {"", " ", "-", None}
params = {
"id":0,
"FT":"",
"inf":0,
"year":0,
"questions":0,
"q_list":0,
"keywords":0,
"vill_inf":0,
"vill_txt":0,
"ray":0,
"found":"Введите запрос"
}

def abort_empty():
    context = params
    context["found"]="Запрос не дал результатов"
    return context

def unique_not_none(schema, attribute):
    return list(
        i
        for i in sorted(set(
            getattr(n, attribute) for n in schema.query.all()
            if getattr(n, attribute) not in nonedict
            ))
        )

def termsToQuery(inp:list, mainname:str="main"):
    text = inp.copy()
    for index in range(len(text)):
        text[index] = "+{}:".format(mainname) + text[index]    
    query = " ".join([word for word in text])
    return query

def return_positions(item:object, mainname:str="main"):
    keys = item["match_data"].metadata.keys()
    output = []
    for key in keys:
        pos = []
        limiter = 0
        for span in item["match_data"].metadata[key][mainname]['position']:
            pos.append(span)
            limiter += 1
            if limiter >= 1:
                break
        output += pos
    output = sorted(output, key=lambda x: x[0])
    return output

def return_indices(item:object, refname:str="ref"):
    return int(item[refname])

def indices_lunr(query, index, ref="ref"):
    results = index.search(query)
    results = sorted(results, key=lambda x: int(x[ref]))
    indices = [idx for idx in map(return_indices, results)]
    return indices, results

def indices_kw(kws:str, db:object):
    kw_list = kws.split(",")
    kw_ids = db.session.query(Keywords.id).filter(Keywords.main.in_(kw_list))
    indices = db.session.query(Text2key.main).filter(Text2key.refer.in_(kw_ids.subquery())).all()
    return [i[0] for i in indices]

def filter_by_id(inp:object, db:object, model:object) -> list:
    if type(inp) == list:
        ids = [item[0] for item in \
        db.session.query(model.main).filter(model.refer.in_(inp)).all()]
    else:
        ids = [item[0] for item in \
        db.session.query(model.main).filter(model.refer==int(inp)).all()]
    return ids

def query_wrapper(db:object, **kwargs):
    new_context = kwargs.copy()
    # retrieve a list of text ids for each of the searched parameters (None if not present)
    # find an intersection
    # return a slice
    l_indices = None
    if "FT" in new_context:
        new_query = termsToQuery([i for i in new_context["FT"].split() if len(i) > 2])
        if len(new_query) == 0: return abort_empty()
        l_indices, _ = indices_lunr(new_query, lunr_index)
        l_indices = set(l_indices)
    inform_indices = set(filter_by_id(new_context["inf"], db, Text2inf)) if "inf" in new_context else None
    kw_indices = set(indices_kw(new_context["keywords"], db)) if "keywords" in new_context else None
    vt_indices = set(filter_by_id(new_context["vill_txt"], db, Text2vill)) if "vill_txt" in new_context else None
    q_indices = set(filter_by_id(new_context["questions"], db, Text2quest)) if "questions" in new_context else None
    y_indices = set(filter_by_id(new_context["year"], db, Text2year)) if "year" in new_context else None
    inf_indices = None
    if "vill_inf" in new_context:
        vi_inf_indices = filter_by_id(new_context["vill_inf"], db, Inf2vill)
        inf_indices = set(filter_by_id(vi_inf_indices, db, Text2inf))
    merged_ray = None
    if "ray" in new_context:
        # by vill_inf table
        ray_vi_indices = filter_by_id(new_context["ray"], db, VI2ray)
        ray_inf_indices = filter_by_id(ray_vi_indices, db, Inf2vill)
        txt_by_vi = set(filter_by_id(ray_inf_indices, db, Text2inf))
        # by vill_txt table
        ray_vil_indices =  filter_by_id(new_context["ray"], db, Vill2ray)
        txt_by_vt = set(filter_by_id(ray_vil_indices, db, Text2vill))
        merged_ray = txt_by_vt.copy()
        merged_ray.update(txt_by_vi)
    ql_indices = None
    if "q_list" in new_context:
        ql_quest_indices = filter_by_id(new_context["q_list"], db, Question2ql)
        ql_indices = set(filter_by_id(ql_quest_indices, db, Text2quest))
    present = [i for i \
        in [ql_indices, inform_indices, merged_ray, inf_indices, y_indices, q_indices, vt_indices, kw_indices, l_indices] \
        if i is not None]
    non_empty = [n for n in present if len(n) > 0]
    if len(non_empty) == 0: return abort_empty()
    id_intersection = non_empty[0]
    if len(non_empty) > 1:
        for i in non_empty[1:]:
            id_intersection = id_intersection.intersection(i)
    if len(id_intersection) == 0: return abort_empty()
    filtered = db.session.query(Texts).filter(Texts.id.in_(list(id_intersection))).paginate(
        page=new_context["page"],
        per_page=PAGINATION_ITEMS
    )
    new_context["found"] = filtered
    return new_context

