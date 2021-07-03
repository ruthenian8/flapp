const host = "http://" + String(window.location.host);
const field2box = {
	"idfield":"idbox",
	"kwfield":"kwbox",
	"qlfield":"qlbox",
	"qfield":"qbox",
	"yfield":"ybox",
	"rayfield":"raybox",
	"VTfield":"VTbox",
	"VIfield":"VIbox"
}

const full2pop = {
	"idfull":{
		"pop":"idpop",
		"field":"idfield",
		"uri":null
	},
	"kwfull":{
		"pop":"kwpop",
		"field":"kwfield",
		"uri":"/api/kws"
	},
	"qlfull":{
		"pop":"qlpop",
		"field":"qlfield",
		"uri":"/api/prs"
	},
	"qfull":{
		"pop":"qpop",
		"field":"qfield",
		"uri":"/api/qlist",
		"parent":"qlfield"
	},
	"yfull":{
		"pop":"ypop",
		"field":"yfield",
		"uri":"/api/yrs"
	},
	"rayfull":{
		"pop":"raypop",
		"field":"rayfield",
		"uri":"/api/rays"
	},
	"VTfull":{
		"pop":"vilpop",
		"field":"VTfield",
		"uri":"/api/rvt",
		"parent":"rayfield"
	},
	"VIfull":{
		"pop":"vilinfpop",
		"field":"VIfield",
		"uri":"/api/rvi",
		"parent":"rayfield"
	}
}

async function process_json(data) {
	let reader, chunks, recordLen, numrepr, result, position, jsonrepr;
	reader = data.getReader();
	chunks = [];
	recordLen = 0;
	while (true) {
		const {done, value} = await reader.read();
		if (done) {
			break;
		}
		chunks.push(value);
		recordLen += value.length;
	}
	numrepr = new Uint8Array(recordLen);
	position = 0;
	for (let chunk of chunks) {
		numrepr.set(chunk, position);
		position += chunk.length;
	}
	result = new TextDecoder("utf-8").decode(numrepr);
	jsonrepr = JSON.parse(result);
	return jsonrepr;
}

// async function attachIndex() {
// 	let data, ftIndex;
// 	await fetch(`${host}/search/index`)
// 	.then(response => {data = response.body;})
// 	.catch(err => {
// 		console.log("Failed to fetch data");
// 		console.log(err);
// 		return;
// 	});
// 	ftIndex = await process_json(data);
// 	if (!lunr) {
// 		console.log("No lunr detected");
// 	}
// 	document.idx = lunr.Index.load(ftIndex);
// }

function indexSearch(event) {
	let FTvalue, FTresults;
	event.preventDefault();
	if (!lunr || !document.idx) {
		return;
	};
	FTvalue = $( "#FTsearch" ).val();
	if (FTvalue == "") {
		alert("Введите слово для поиска");
		return;
	}
	FTresults = document.idx.search(FTvalue);
	document.FTids = FTresults.map(
		(item) => {return item["ref"]}
	);
}

function closePopups(event) {
	event.preventDefault();
	let pops = Array.from($( ".popup" ));
	for (let pop of pops) {
		pop.style.display = "none";
	};
	$( "#overlay" ).css("display", "none");
}

function expandSelection(event) {
	event.preventDefault();
	let fullId, namespace, popId, optsUri, updUri;
	fullId = event.target.id;
	if (!full2pop) {
		console.log("error: no namespace dictionary");
		return;
	}
	namespace = full2pop[fullId];
	popId = namespace["pop"];

	// a check not to expand child-selects before the parents are selected
	optsUri = host + namespace["uri"];
	updUri = parentCheck(namespace, optsUri);
	if (updUri === false) { return; }

	$( "#overlay" ).css("display", "block");
	$( `#${popId}` ).css("display", "block");
}

function setOpts(event) {
	event.preventDefault();
	let fullId, namespace, fieldId, optsUri, updUri;
	fullId = event.target.id;
	// return if setting options is not required
	if (fullId == "idfull") { return; };
	// return if the namespace object is not visible
	if (!full2pop) { return; };
	namespace = full2pop[fullId];
	fieldId = namespace["field"];
	// return if options have already been set
	if ( $( `#${fieldId}` ).children().length > 1 ) { return; };
	// proceed to downloading after the checks
	optsUri = host + namespace["uri"];

	// a check not to open child-selects before the parents are selected
	updUri = parentCheck(namespace, optsUri);
	if (updUri === false) {
		alert("Перед выбором вопроса или населённого пункта выберите опросник или район соответственно.");
		return;
	}
	optsLogic(fieldId, updUri);
}

function parentCheck(namespace, optsUri) {
	let parentId, parentVal;
	if (namespace.hasOwnProperty("parent")) {
		parentId = namespace["parent"];
		parentVal = $( `#${parentId} input:checked` ).val();
		if ( !parentVal ) {
			return false;
		} else {
			optsUri += `/${parentVal}`;
			return optsUri
		}
	}
	return optsUri;
}

function optsLogic(fieldId, optsUri) {
	var data, content, targetField;
	(async function download() {
		let respBody;
		await fetch(optsUri)
		.then(response => {respBody = response.body;})
		.catch((err) => {
			console.log('failed to fetch')
			console.log(err);
			return;
		});
		content = await process_json(respBody);
	})().then(resp => {
		targetField = $( `#${fieldId}` );
		let name = targetField.prop("name");

		if (targetField.hasClass("sing")) {
			var counter = 1;
			if (fieldId == "qlfield") {
				content.forEach((item) => {
					targetField.append(`<input type="radio" id="${fieldId+counter}" name="${name}" value="${item["id"]}"/>`);
					targetField.append(`<label for="${fieldId+counter}">${item["name"] + " " + item["code"]}</label>`);
					targetField.append(`<br />`);
					counter++;
				});				
			} else {
				content.forEach((item) => {
					targetField.append(`<input type="radio" id="${fieldId+counter}" name="${name}" value="${item["id"]}"/>`);
					targetField.append(`<label for="${fieldId+counter}">${item["main"]}</label>`)
					targetField.append(`<br />`);
					counter++;
				});
			}

		} else if (targetField.hasClass("mult")) {
			if (content.length == 0) {targetField.append("<p>Пересечений не найдено!</p>")};
			if (fieldId == "qfield") {
				content.forEach((item) => {
					targetField.append(`<option value="${item["id"]}">${item["code"] + " " + item["name"]}</option>`)
				})				
			} else {
				content.forEach((item) => {
					targetField.append(`<option value="${item["id"]}">${item["main"]}</option>`)
				})				
			};

		} else if (targetField.hasClass("tags")) {
			let taglist;
			taglist = content.map((item) => {return item["main"];})
			targetField.tagsInput({
				"autocomplete":{source:taglist},
				"delimiter":",",
				"whitelist":taglist
			});
		}
		targetField.on("input", changeBox);	
	});
}

function changeBox(event) {
	let fieldId, boxId;
	fieldId = event.target.id;
	boxId = field2box[fieldId];
	$( `#${boxId}` )
	.importTags($( `#${fieldId}` ).val());
}

function assignEvents() {
	let fullButtons = Array.from($( ".srcbtn" ));
	for (let button of fullButtons) {
		button.addEventListener("click", expandSelection);
		button.addEventListener("click", setOpts);
	};

	let closeButtons = Array.from($(".closebtn"));
	for (let close of closeButtons) {
		close.addEventListener("click", closePopups);
	};
	// attachIndex();
	$("#FTbutton").on("click", FTsearch);
	$("#FTsearch").on("submit", FTsearch);
	$( "#FTsearch" ).on("enter", FTsearch);
}

assignEvents();