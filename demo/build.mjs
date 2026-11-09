import { readFile, writeFile } from 'node:fs/promises';
const read = (file) => readFile(new URL(file, import.meta.url), 'utf8');
let html = await read('index.html');
const font = (await readFile(new URL('assets/inter-latin-variable.woff2', import.meta.url))).toString('base64');
const fontCSS = (await read('fonts.css')).replace('url(assets/inter-latin-variable.woff2)', `url(data:font/woff2;base64,${font})`);
const awaitedStyles = await read('styles.css');
html = html.replace('<link rel="stylesheet" href="fonts.css">', () => `<style>\n${fontCSS}\n</style>`);
html = html.replace('<link rel="stylesheet" href="styles.css">', () => `<style>\n${awaitedStyles}\n</style>`);
for (const file of ['model.js', 'panels.js', 'app.js']) {
  const script = (await read(file)).replace(/<\/script/gi, '<\\/script');
  html = html.replace(`<script src="${file}"></script>`, () => `<script>\n${script}\n</script>`);
}
await writeFile(new URL('ramus-demo.html', import.meta.url), html);
console.log('Built demo/ramus-demo.html — open it directly in a browser.');
