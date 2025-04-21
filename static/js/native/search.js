const host = "https://" + window.location.host;
const selectParamsToEndpoint = {
	"#yfield":{
		"endpoint":"/api/yrs",
		"result":[]
	},
	"#inffield":{
		"endpoint":"/api/infs",
		"result":[]
	},
	"#sobfield":{
		"endpoint":"/api/sobs",
		"result":[]
	},
	"#qlfield":{
		"endpoint":"/api/prs",
		"result":[]
	},
	"#qfield":{
		"endpoint":"/api/quests",
		"result":[]
	},
	"#rayfield":{
		"endpoint":"/api/rays",
		"result":[]
	},
	"#VTfield":{
		"endpoint":"/api/rvt",
		"result":[]
	},
	"#VIfield":{
		"endpoint":"/api/rvi",
		"result":[]
	},
	"#kwfield":{
		"endpoint":"/api/kws",
		"result":[]
	}
}

const childParamsToParent = {
	"#qlfield": {
		"endpoint":"api/quests",
		"child":"#qfield",
		"result":[]
	},
	"#rayfield": {
		"endpoint":"api/rvt",
		"child":"#VTfield",
		"result":[]
	}
	// "#VIfield": {
	// 	"endpoint":"api/rvi",
	// 	"parent":"#rayfield",
	// 	"result":[]
	// }
}


function applyKeywords() {
	const kwfield = document.getElementById("kwfield");
	kwfield.value = kwfield.dataset.selected == "0" ? "" : kwfield.dataset.selected;
}

function applySelected() {
	for (let select of Array.from(document.getElementsByTagName("select"))) {
		const val = select.dataset.selected;
		if (Boolean(val)) {
			select.value = val;
		} else {
			select.value = "0";
		}
	}
}

async function loadInitial(host) {
	applyKeywords();
	const urls = [];
	for (let key in selectParamsToEndpoint) {
		selectParamsToEndpoint[key]["promise"] = fetch(host + selectParamsToEndpoint[key]["endpoint"])
		.catch(err => this.onLoadError(err))
		.then(res => res.json())
		.then(data =>  {selectParamsToEndpoint[key]["result"] = data})
	}
	await Promise.allSettled(Object.values(selectParamsToEndpoint).map(item => item["promise"]));
	// initiate callback when options are downloaded
	for (let key in selectParamsToEndpoint) {
		setField(key, selectParamsToEndpoint[key]);
	}
	applySelected();
}

async function loadRelated(host, parameter, targetObj) {
	let url = parameter == "0" ? [host, targetObj["endpoint"]].join("/") : [host, targetObj["endpoint"], parameter].join("/");
	await fetch(url).catch(err => console.log(err)).then(res => res.json()).then(data => targetObj["result"] = data);
	return targetObj;
}

// update different fields depending on the received JSON schema
function setField(fieldId, entries) {
	let targetField = $( fieldId )
	// try {
	switch (fieldId) {
		case "#kwfield":
			let taglist;
			taglist = entries["result"].map((item) => {return item["main"];})
			targetField.tagsInput({
				"autocomplete":{source:taglist},
				"delimiter":",",
				"whitelist":taglist
			});
			break;
		case "#qlfield":
		case "#inffield":
		case "#sobfield":
			targetField.append(`<option value="0">Не выбрано</option>`);
			entries["result"].sort((x, y) => ('' + x.code).localeCompare(y.code)).forEach((item) => {
				let textOpt = Boolean(item["name"]) ? item["name"].slice(0,40) + "..." : "";
				targetField.append(`<option value="${item["id"]}">${item["code"] + " " + textOpt}</option>`)
			})
			break;
		case "#qfield":
			targetField.append(`<option value="0">Не выбрано</option>`);
			entries["result"].forEach((item) => {
				let textOpt = Boolean(item["q_txt"]) ? item["q_txt"].slice(0,40) + "..." : "";
				targetField.append(`<option value="${item["id"]}">${item["q_num"] + item["q_let"] + " " + textOpt}</option>`)
			})
			break;
		default:
			targetField.append(`<option value="0">Не выбрано</option>`);
			entries["result"].sort((x, y) => Number(x.main) - Number(y.main)).forEach((item) => {
				targetField.append(`<option value="${item["id"]}">${item["main"].slice(0,40)}</option>`)
			})
			break;
	}  // }  catch (err) { console.log(fieldId) }
}

async function updateChild(event) {
	let id = "#" + event.target.id;
	let val = $( id ).val();
	let child = $( childParamsToParent[id]["child"] );
	child.empty();
	childParamsToParent[id] = await loadRelated(host, val, childParamsToParent[id]);
	setField(childParamsToParent[id]["child"], childParamsToParent[id]);
}

function assignEvents() {
	let form = document.getElementById("srcform");
	form.addEventListener("submit", (event) => {
		event.preventDefault();
		let uriString = host + "/search/?page=1"
		const formData = new FormData(event.target);
		for (var pair of formData.entries()) {
			if ( pair[1] == "0" || pair[1] == "" ) { continue }
			uriString = uriString + '&' + pair[0] + '=' + pair[1];
		}
		window.location.replace(uriString);
	})

	for (let parent in childParamsToParent) {
		document.querySelector( parent ).addEventListener("input", updateChild);
	}
}

$( document ).ready( () => {
	loadInitial(host);
	assignEvents();
} )
