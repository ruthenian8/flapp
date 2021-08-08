function viewImg(event) {
    // when image button is clicked,
    // adds the image to the modal window.
    let node = event.target;
    if (node.classList.contains("img")) {
        let modal = $("#imgModalBody");
        modal.empty();
        modal.append(node.cloneNode());
    };
};

// container fot carousel items
const carBody = $(".carousel-inner");
// initial page
// is incremented by pressing the forward button
let page = 1;
// initial number of pages in the base
// gets updated at each request to the base
let pageNum = 4;
const uriPrefix = "/static/";

function carListener(event) {
    // calls a function to update the carousel, if there remain any pages.
    if (page + 3 > pageNum) {return};
    updateCar(page + 2);
    page++;
    return;
}

async function updateCar(newPage) {
    // downloads links to photos
    // copies a carousel item
    // changes links inside photos
    // appends to the carousel
    if (typeof(newPage) !== "string") { newPage = newPage.toString(); }
    const result = await $.getJSON(`/api/pics?pages=${newPage}`)
    .catch(err => {
        console.log(err);
        return;
    });
    pageNum = result["pages"];
    const template = document.querySelector(".carousel-item").cloneNode(deep=true);
    if (template.classList.contains("active")) {template.classList.remove("active")};
    const imgList = template.getElementsByTagName("img")
    for (let idx = 0; idx < 3; idx++) {
        imgList[idx].setAttribute("src", uriPrefix + result["page_items"][idx]["path"]);
    }
    carBody.append(template);
    return;
}

$( document ).ready( () => {
	$("#carouselGallery").on("click", viewImg);
    $("#carForward").on("click", carListener);
})