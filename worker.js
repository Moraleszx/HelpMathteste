/* =========================================
   HELPMATH — WORKER DO MOTOR MATEMÁTICO
   Carrega o Pyodide (Python no navegador) + SymPy
   e executa engine.py fora da thread da interface.
   ========================================= */

const PYODIDE_PADRAO = "https://cdn.jsdelivr.net/pyodide/v0.29.5/full/";

let pyodide = null;
let resolverPy = null;
let pronto = null;

async function iniciar(config = {}) {
  const base = config.pyodideURL || PYODIDE_PADRAO;

  importScripts(base + "pyodide.js");
  pyodide = await loadPyodide({ indexURL: base });

  if (config.wheels && config.wheels.length) {
    // usado nos testes offline: instala os pacotes a partir de arquivos locais
    for (const url of config.wheels) {
      const dados = await (await fetch(url)).arrayBuffer();
      pyodide.unpackArchive(dados, "wheel");
    }
  } else {
    await pyodide.loadPackage(["sympy"]); // traz o mpmath junto
  }

  const codigo = await (await fetch(config.engineURL || "engine.py")).text();
  pyodide.runPython(codigo);
  resolverPy = pyodide.globals.get("resolver");

  // aquece o SymPy (a primeira chamada importa vários módulos)
  try {
    resolverPy("lim(x->0) sin(x)/x", "automatico");
  } catch (e) {
    console.warn("HelpMath: aquecimento falhou (o motor continua ativo):", e);
  }
}

self.onmessage = async (evento) => {
  const msg = evento.data;

  if (msg.tipo === "iniciar") {
    pronto = iniciar(msg.config);
    try {
      await pronto;
      self.postMessage({ tipo: "pronto" });
    } catch (e) {
      self.postMessage({ tipo: "falha", erro: String(e && e.message || e) });
    }
    return;
  }

  if (msg.tipo === "resolver") {
    try {
      if (!pronto) {
        throw new Error("o motor ainda não foi iniciado");
      }
      await pronto;
      const json = resolverPy(msg.texto, msg.assunto || "automatico");
      self.postMessage({ tipo: "resultado", id: msg.id, dados: JSON.parse(json) });
    } catch (e) {
      self.postMessage({
        tipo: "resultado",
        id: msg.id,
        dados: { ok: false, erro: "Erro interno do motor: " + String(e && e.message || e) }
      });
    }
  }
};
