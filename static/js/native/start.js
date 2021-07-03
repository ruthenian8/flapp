let categories = null;
async function loadJson(json_uri) {
  let data;
  await fetch(json_uri)
  .then(response => {data = response.body})
  .catch(err => {
    console.log("failed to access the json uri");
    return;
  });
  const reader = data.getReader();
  let chunks = []
  let recLength = 0
  while (true) {
    const {done, value} = await reader.read()
    if (done) {
      break;
    }
    chunks.push(value)
    recLength += value.length
  }
  let chunksAll = new Uint8Array(recLength); // (4.1)
  let position = 0;
  for(let chunk of chunks) {
    chunksAll.set(chunk, position); // (4.2)
    position += chunk.length;
  }
  
  let result = new TextDecoder("utf-8").decode(chunksAll);
  let dat = JSON.parse(result);
  categories = JSON.parse(dat.content)
  return;  
}