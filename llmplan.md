aspek = """
Anhedonia (kehilangan minat/kenikmatan)
Bias kognitif negatif & hopelessness
Rumination (pikiran berputar tanpa solusi)
Psikomotor retardation
Gangguan tidur (insomnia, kualitas tidur jelek)
Iritabilitas & ledakan marah
Rasa bersalah berlebih / self‑blame
Gangguan kognitif (concentration & executive function)
Penarikan diri sosial / isolasi
Alexithymia (sulit mengenali & mengungkap emosi)
Defisit regulasi emosi
Pastikan kamu menggali secara dalam, rinci, friendly, dan subtle.
Silahkan sapa dahulu sebelum memulai percakapan eksploratif
"""

Format prompt (constant)
Anda adalah Anisa, seorang mahasiswa psikologi yang supportive dan senang hati mendengarkan curhatan orang lain. Teman anda kemungkinan mengalami gejala depresi, atau bisa jadi tidak.
Buatlah beberapa pertanyaan dengan gaya non formal kepada rekan anda tentang aktivitas sehari-hari atau tentang kejadian yang akhir-akhir ini dialami. Tindak lanjuti setiap jawaban dengan pertanyaan yang lebih dalam. Setelah itu, secara alami alihkan percakapan untuk mengeksplorasi bagaimana kondisi psikologis mereka terutama yang berkaitan dengan gejala depresi. Berikut adalah indikator-indikator dari gejala depresi:
{aspek}
Nanti jika sudah didapatkan semua informasi yang perlu didapatkan Tolong stop ya dengan menutup. Percakapan dengan "gak papa kamu pasti bisa kok, semangat yaa ! Kalau memang darurat deh Hubungi psikolog terdekat mu !!" Tidak perlu bilang secara eksplisit menyebutkan mengenai depresi atau sejenisnya. Kemudian tulis </end_conversation> pada akhir kalimat

settings :
bisa menambah menggurangi aspek. lalu nanti akan di format sebagai \n seperated text yang kemudian akan dijadikan system prompt haha

Pada UI ini nanti diformalisasi sebagai field tapi per item gitu
jadi misalakan tambah aspek analisa atau apa

Kemudian ada Model yang dipakai Untuk analisa  
Nah itu nanti dimasukan sebagai list juga gitu https://platform.openai.com/docs/models dan ada referensi ini untuk mengecek model yang kaan digunakan

ada 2 bagian untuk analisa + untuk chat . Jadio model yang nantii di initiate akan dari settings. nanti agent nya akan berebda. tapi ini hanya bagian settings saja dulu

Kemudian untuk mengecek jika terdapat model

skeleton nya kira2 begini untuk mengecek

```<h1 class="text-2xl font-semibold mb-4">OpenAI model checker</h1>

<div class="grid gap-4">
  <form id="check-form" class="flex gap-2">
    <input id="model-id" class="flex-1 rounded-xl border px-4 py-2"
           placeholder="e.g., gpt-4o, gpt-4.1, o3, o1-mini" />
    <button class="rounded-xl bg-slate-900 text-white px-4 py-2">Check</button>
  </form>

  <div id="result" class="hidden rounded-xl border p-4"></div>

  <section class="mt-4">
    <div class="flex items-center justify-between mb-2">
      <h2 class="text-lg font-medium">Models your key can use</h2>
      <input id="search" class="rounded-xl border px-4 py-2 text-sm"
             placeholder="Search models… (e.g., gpt, o1, embedding)" />
    </div>

    <div id="model-list" class="rounded-xl border p-0 overflow-hidden">
      <div id="models-empty" class="hidden p-6 text-sm text-slate-500">No results.</div>
      <ul id="models" class="divide-y text-sm"></ul>
    </div>

    <p class="text-xs text-slate-500 mt-2">
      List comes from the official Models API (account-specific). Availability can differ from docs.
    </p>
  </section>
</div>

<script>
let ALL_MODELS = [];
const $ = (q) => document.querySelector(q);

// basic sanitizer
function esc(s){ return s.replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m])); }

// highlight simple substring matches (multi-term)
function highlight(id, query){
  if(!query) return esc(id);
  const parts = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  let out = esc(id);
  for(const term of parts){
    const re = new RegExp(`(${term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'ig');
    out = out.replace(re, '<mark class="bg-yellow-200">$1</mark>');
  }
  return out;
}

// simple ranking: exact > startsWith > includes
function rank(id, q){
  if(!q) return 2;
  const s = id.toLowerCase();
  const terms = q.toLowerCase().trim().split(/\s+/).filter(Boolean);
  const includesAll = terms.every(t => s.includes(t));
  if(!includesAll) return 99;
  if(terms.length === 1 && s === terms[0]) return 0;
  if(terms.some(t => s.startsWith(t))) return 1;
  return 2;
}

function render(list, q){
  const ul = $("#models");
  const empty = $("#models-empty");
  ul.innerHTML = "";
  if(list.length === 0){
    empty.classList.remove("hidden");
    return;
  }
  empty.classList.add("hidden");
  const frag = document.createDocumentFragment();
  for(const id of list){
    const li = document.createElement("li");
    li.className = "flex items-center justify-between p-3 hover:bg-slate-50";
    li.innerHTML = `
      <code class="font-mono text-[13px] break-all">${highlight(id, q)}</code>
      <button class="ml-3 shrink-0 text-xs rounded-lg border px-2 py-1 hover:bg-slate-100"
              data-copy="${esc(id)}">Copy</button>
    `;
    frag.appendChild(li);
  }
  ul.appendChild(frag);
}

// debounce util
function debounce(fn, ms=150){
  let t; return (...a)=>{ clearTimeout(t); t=setTimeout(()=>fn(...a), ms); };
}

async function loadAll() {
  const r = await fetch("/api/models");
  ALL_MODELS = await r.json();
  const q = new URLSearchParams(location.search).get("q") || "";
  $("#search").value = q;
  update(q);
}

function update(q){
  const ranked = [...ALL_MODELS]
    .map(id => ({id, r: rank(id, q)}))
    .filter(x => x.r < 99)
    .sort((a,b)=> a.r - b.r || a.id.localeCompare(b.id))
    .map(x => x.id);
  render(ranked, q);
  const url = new URL(location.href);
  if(q) url.searchParams.set("q", q); else url.searchParams.delete("q");
  history.replaceState(null, "", url);
}

$("#search").addEventListener("input", debounce(e => update(e.target.value), 120));

// copy buttons
document.addEventListener("click", (e)=>{
  const btn = e.target.closest("[data-copy]");
  if(!btn) return;
  navigator.clipboard.writeText(btn.dataset.copy);
  btn.textContent = "Copied";
  setTimeout(()=> btn.textContent = "Copy", 800);
});

// existing checker
document.getElementById("check-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const id = document.getElementById("model-id").value.trim();
  const box = document.getElementById("result");
  if (!id) return;
  box.classList.remove("hidden");
  box.textContent = "Checking…";
  try {
    const r = await fetch(`/api/models/${encodeURIComponent(id)}`);
    const { available } = await r.json();
    box.textContent = available
      ? ` ${id} is available for this API key.`
      : ` ${id} is NOT available for this API key.`;
    box.className = "rounded-xl border p-4 " + (available ? "border-green-300 bg-green-50" : "border-red-300 bg-red-50");
  } catch {
    box.textContent = "Error checking model.";
    box.className = "rounded-xl border p-4 border-amber-300 bg-amber-50";
  }
});

loadAll();
</script>
```

```
@app.get("/api/search")
def api_search():
    q = (request.args.get("q") or "").strip().lower()
    models = list_models_cached()
    if not q:
        return jsonify(models)
    terms = [t for t in q.split() if t]
    def score(mid: str):
        s = mid.lower()
        if not all(t in s for t in terms):
            return 999
        if len(terms)==1 and s == terms[0]: return 0
        if any(s.startswith(t) for t in terms): return 1
        return 2
    ranked = sorted((m for m in models if score(m) < 999), key=lambda m: (score(m), m))
    return jsonify(ranked)
```
