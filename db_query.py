from sqlalchemy import and_, not_
from sqlalchemy.sql.elements import FunctionFilter
from models import *
import pickle
from functools import singledispatch

PAGINATION_ITEMS = 10

def unpickle_index(idx_name="byteindex"):
    with open(idx_name, "rb") as bytefile:
        index = pickle.load(bytefile)
    return index
lunr_index = unpickle_index("byteindex")

nonedict = {"", " ", "-", None}
params = {
"id":0,
"FT":"",
"inf":0,
"sob":0,
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

@singledispatch
def filter_by_id(inp, db:object, model:object) -> list:
    pass
@filter_by_id.register(list)
def _(inp, db:object, model:object):
    ids = [item[0] for item in db.session.query(model.main).filter(model.refer.in_(inp)).all()]
    return ids
@filter_by_id.register(int)
@filter_by_id.register(str)
def _(inp, db:object, model:object):
    ids = [item[0] for item in db.session.query(model.main).filter(model.refer==int(inp)).all()]
    return ids

def filter_by_ft(inp:str, db:object, model:object=None) -> list:
    new_query = termsToQuery([i for i in inp.split() if len(i) > 2])
    if len(new_query) == 0: return []
    l_indices, _ = indices_lunr(new_query, lunr_index)
    return l_indices

def filter_by_relation(inp:str, db:object, model:object) -> list:
    rel_indices = filter_by_id(inp, db, model["relation"])
    main_indices = filter_by_id(rel_indices, db, model["main"])
    return main_indices

def filter_by_kw(inp:str, db:object, model:object=Text2key) -> list:
    kw_list = inp.split(",")
    id_sets = []
    for k in kw_list:
        sub = db.session.query(Keywords.id).filter(Keywords.main==k)
        indices = db.session.query(model.main).filter(model.refer.in_(sub.subquery())).all()
        id_sets.append({i[0] for i in indices})
    intersection = id_sets[0]
    for id_set in id_sets[1:]:
        intersection = intersection.intersection(id_set)
    t_ids = list(intersection)
    if len(t_ids) == 0:
        return []
    text_inds = [item[0] for item in db.session.query(Texts.id).filter(Texts.id.in_(t_ids)).all()]
    return text_inds

mapping = {
    "FT":{"filter":filter_by_ft,"model":None},
    "keywords":{"filter":filter_by_kw,"model":Text2key},
    "inf":{"filter":filter_by_id,"model":Text2inf},
    "vill_txt":{"filter":filter_by_id,"model":Text2vill},
    "questions":{"filter":filter_by_id,"model":Text2quest},
    "year":{"filter":filter_by_id,"model":Text2year},
    "sob":{"filter":filter_by_id,"model":Text2sob},
    "vill_inf":{"filter":filter_by_relation,"model":{"relation":Inf2vill, "main":Text2inf}},
    "q_list":{"filter":filter_by_relation,"model":{"relation":Question2ql, "main":Text2quest}},
    "ray":{"filter":filter_by_relation,"model":{"relation":Vill2ray, "main":Text2vill}}
}

def query_wrapper(db:object, paginate:bool, **kwargs):
    new_context = kwargs.copy()
    non_empty = []
    for key in new_context.keys():
        if key == "page" or key == "download": continue
        result = set(mapping[key]["filter"](new_context[key], db, mapping[key]["model"]))
        if len(result) == 0:
            return abort_empty()
        non_empty.append(result)
    if len(non_empty) == 0: return abort_empty()
    id_intersection = non_empty[0]
    for i in non_empty[1:]:
        id_intersection = id_intersection.intersection(i)
    if len(id_intersection) == 0: return abort_empty()
    if paginate:
        filtered = db.session.query(Texts).filter(Texts.id.in_(list(id_intersection))).paginate(
            page=new_context["page"],
            per_page=PAGINATION_ITEMS)
    else:
        filtered = db.session.query(Texts).filter(Texts.id.in_(list(id_intersection))).all()
    new_context["found"] = filtered
    return new_context