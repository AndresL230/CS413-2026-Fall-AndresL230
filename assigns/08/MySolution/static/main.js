// Wiring: controls -> Player, Player snapshots -> renderer.

import { RpcClient } from "./rpc.js";
import { Player } from "./player.js";
import { createRenderer } from "./render.js";

const $ = (id) => document.getElementById(id);
const renderer = createRenderer(document);
const player = new Player({
  rpc: new RpcClient(),
  onChange: (snap) => renderer.render(snap),
  size: Number($("size").value),
});

const selectedSize = () => Number($("size").value);
const speedLabel = () => { $("speed-value").textContent = `${$("speed").value} events/s`; };
// Errors are shown by the Player; this only stops unhandled-rejection noise.
const run = (promise) => promise?.catch?.((err) => console.error(err));

$("btn-start").addEventListener("click", () => run(player.start(selectedSize())));
$("btn-restart").addEventListener("click", () => run(player.start(selectedSize())));
$("btn-step").addEventListener("click", () => run(player.step()));
$("btn-play").addEventListener("click", () => player.togglePlay());
$("btn-next").addEventListener("click", () => run(player.nextSolution()));
$("btn-reset").addEventListener("click", () => run(player.reset(selectedSize())));
$("size").addEventListener("change", () => run(player.reset(selectedSize())));
$("speed").addEventListener("input", () => { player.setSpeed(Number($("speed").value)); speedLabel(); });
window.addEventListener("pagehide", () => player.closeOnUnload());

player.setSpeed(Number($("speed").value));
speedLabel();
renderer.render(player.snapshot());
