// Ask the house a question the way a paired Emkay does, and print the answer.
//
//   node tools/ask.mjs pairing.json "what time is it"
//
// pairing.json is what tools/smoke.py prints ({"link": {...}, "ca": ...}).
// Uses Emkay's own HiveMind client (web/brains/hivemind.js, fetched from
// emkay-voice/emkay) over wss://<house>/hivemind. Run it with
// NODE_EXTRA_CA_CERTS=<the house's certificate> so Node trusts the house.
// Exits 0 when the house answers (a "speak"), 1 when it doesn't in time.
// Says how long the house took – from the question to its answer, which is
// the house's part of a turn (Emkay adds hearing and speaking, or the house
// does with speech in it: tools/speak.py).
import { readFileSync, writeFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [file, question = "what time is it", seconds = "90"] = process.argv.slice(2);
const { link } = JSON.parse(readFileSync(file, "utf8"));

const src = await (await fetch("https://raw.githubusercontent.com/emkay-voice/emkay/main/web/brains/hivemind.js")).text();
const mod = join(mkdtempSync(join(tmpdir(), "emkay-")), "hivemind.mjs");
writeFileSync(mod, src);
const { HiveMindClient } = await import(mod);

const hm = new HiveMindClient({ ...link, lang: link.lang || "en-us" });
const t0 = performance.now();
await hm.connect();
const secs = (t) => ((performance.now() - t) / 1000).toFixed(2);
console.log(`connected to ${link.host}:${link.port}${link.path} as node ${hm.nodeId} in ${secs(t0)} s`);
const said = new Promise((resolve) => hm.addEventListener("message", (e) => {
  const m = e.message;
  if (m.type === "speak") resolve(m.data.utterance);
  else console.log(`  ← ${m.type}`);
}));
const t1 = performance.now();
await hm.emit("recognizer_loop:utterance", { utterances: [question], lang: link.lang || "en-us" });
console.log(`asked: ${question}`);
const answer = await Promise.race([said, new Promise((r) => setTimeout(() => r(null), +seconds * 1000))]);
console.log(answer ? `speak: ${answer}  (answered in ${secs(t1)} s)` : `no answer in ${seconds} s`);
process.exit(answer ? 0 : 1);
