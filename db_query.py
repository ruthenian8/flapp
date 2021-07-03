from sqlalchemy import and_, not_
from flapp.models import *
import os
import pickle

def unpickle_index(idx_name="byteindex"):
    with open("flapp/" + idx_name, "rb") as bytefile:
        index = pickle.load(bytefile)
    return index
lunr_index = unpickle_index("byteindex")

nonedict = {"", " ", "-", None}
params = {
"id":0,
"FT":"",
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

    # positions = map(return_positions, results)
    # res_objects = db.session.query(Chunks).filter(Chunks.id.in_(indices)).all()
    # newres = []
    # for obj, pos in zip(res_objects, positions):
    #     dictionary = obj.__repr__()
    #     text = ' ' + dictionary["text"] + ' '
    #     matches = []
    #     for position in pos:
    #         init, fin = position[0] + 1, position[0] + position[1] + 1
    #         low = init - 180
    #         if low < 0:
    #             low = 0
    #         high = init + 180
    #         if high > len(text):
    #             high = len(text)
    #         match = "{}<b>{}</b>{}".format(
    #             text[low:init],
    #             text[init:fin],
    #             text[fin:high]
    #         )
    #         src = re.search(r"([А-Я]|^| ).* ", match)
    #         if bool(src):
    #             low_crop, high_crop = src.span()
    #         else:
    #             low_crop, high_crop = 0, len(match)
    #         final_match = match[low_crop:high_crop]
    #         matches.append(final_match)
    #     del dictionary["text"]
    #     dictionary["matches"] = matches
    #     newres.append(dictionary)
    # return newres

def filter_by_id(inp:object, db:object, model:object):
    if type(inp) == list:
        ids = [item[0] for item in \
        db.session.query(model.main).filter(model.refer.in_(inp)).all()]
    else:
        ids = [item[0] for item in \
        db.session.query(model.main).filter(model.refer==int(inp)).all()]
    return ids

def query_wrapper(db:object, **kwargs):
    new_context = kwargs
    # retrieve a list of text ids for each of the searched parameters (None if not present)
    # find an intersection
    # return a slice
    l_indices = None
    if "FT" in new_context:
        new_query = termsToQuery([i for i in new_context["FT"].split() if len(i) > 2])
        l_indices, results = indices_lunr(new_query, lunr_index)
        l_indices = set(l_indices)
    kw_indices = set(indices_kw(new_context["keywords"], db)) if "keywords" in new_context else None
    vt_indices = set(filter_by_id(new_context["vill_txt"], db, Text2vill)) if "vill_txt" in new_context else None
    q_indices = set(filter_by_id(new_context["questions"], db, Text2quest)) if "questions" in new_context else None
    y_indices = set(filter_by_id(new_context["year"], db, Text2year)) if "year" in new_context else None
    inf_indices = None
    if "vill_inf" in new_context:
        vi_inf_indices = filter_by_id(new_context["vill_inf"], db, Inf2vill)
        inf_indices = set(filter_by_id(vi_inf_indices, db, Text2inf))
    ray_indices = None
    if "ray" in new_context:
        ray_vil_indices =  filter_by_id(new_context["ray"], db, Vill2ray)
        ray_indices = set(filter_by_id(ray_vil_indices, db, Text2vill))
    ql_indices = None
    if "q_list" in new_context:
        ql_quest_indices = filter_by_id(new_context["q_list"], db, Question2ql)
        ql_indices = set(filter_by_id(ql_quest_indices, db, Text2quest))
    present = [i for i \
        in [ql_indices, ray_indices, inf_indices, y_indices, q_indices, vt_indices, kw_indices, l_indices] \
        if i is not None]
    non_empty = [n for n in present if len(n) > 0]
    if len(non_empty) == 0:
        new_context = abort_empty()
        return new_context
    id_intersection = non_empty[0]
    if len(non_empty) > 1:
        for i in non_empty[1:]:
            id_intersection = id_intersection.intersection(i)
    if len(id_intersection) == 0:
        new_context = abort_empty()
        return new_context
    filtered = db.session.query(Texts).filter(Texts.id.in_(list(id_intersection))).all()
    if len(filtered) < new_context["limit"] - new_context["offset"]:
        subset = filtered
    else:
        upper = min(len(filtered), new_context["limit"])
        subset = filtered[new_context["offset"]:upper]
    new_context["found"] = text_schema.dump(subset, many=True)
    return new_context

