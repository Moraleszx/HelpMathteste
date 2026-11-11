
/* =========================================
   HELPMATH — MOTOR PRINCIPAL
   ========================================= */

// ELEMENTOS PRINCIPAIS

const assunto = document.getElementById("assunto");
const expressao = document.getElementById("expressao");
const botaoCalcular = document.getElementById("calcular");
const botaoLimpar = document.getElementById("limpar");
const resultado = document.getElementById("resultado");
const areaResultado = document.getElementById("area-resultado");
const erro = document.getElementById("erro");


// =========================================
// NAVEGAÇÃO
// =========================================

const paginas = document.querySelectorAll(".page");
const itensMenu = document.querySelectorAll(".nav-item");
const sidebar = document.getElementById("sidebar");
const breadcrumb = document.getElementById("breadcrumb");

function navegar(pagina) {
  paginas.forEach(p => p.classList.remove("active"));

  const destino = document.getElementById(`page-${pagina}`);

  if (destino) {
    destino.classList.add("active");
  }

  itensMenu.forEach(item => {
    item.classList.toggle("active", item.dataset.page === pagina);
  });

  const nomes = {
    inicio: "Início",
    funcoes: "Funções",
    limites: "Limites",
    derivadas: "Derivadas",
    integrais: "Integrais",
    equacoes: "Equações",
    historico: "Histórico",
    sobre: "Sobre o HelpMath"
  };

  breadcrumb.innerHTML = `Início <span>/</span> ${nomes[pagina] || "HelpMath"}`;

  sidebar.classList.remove("open");

  window.scrollTo({
    top: 0,
    behavior: "smooth"
  });
}

itensMenu.forEach(item => {
  item.addEventListener("click", () => {
    navegar(item.dataset.page);
  });
});

document.getElementById("menu-toggle").addEventListener("click", () => {
  sidebar.classList.toggle("open");
});

document.querySelectorAll(".topic-card").forEach(card => {
  card.addEventListener("click", () => {
    selecionarConteudo(card.dataset.topic);
  });
});

document.querySelectorAll(".go-home").forEach(botao => {
  botao.addEventListener("click", () => {
    navegar("inicio");
  });
});

function selecionarConteudo(tipo) {
  assunto.value = tipo;
  navegar("inicio");
  expressao.focus();
}


// =========================================
// EXEMPLOS
// =========================================

document.querySelectorAll(".example-btn").forEach(botao => {
  botao.addEventListener("click", () => {
    expressao.value = botao.dataset.example;
    expressao.focus();
    erro.textContent = "";
  });
});


// =========================================
// UTILITÁRIOS MATEMÁTICOS
// =========================================

function formatar(numero) {
  if (!Number.isFinite(numero)) {
    return String(numero);
  }

  if (Math.abs(numero) < 0.0000001) {
    return "0";
  }

  return Number(numero.toFixed(6)).toString();
}

function escaparHTML(texto) {
  return String(texto).replace(/[&<>"']/g, caractere => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  })[caractere]);
}

function normalizarExpressao(texto) {
  return texto
    .toLowerCase()
    .replace(/−/g, "-")
    .replace(/[×·]/g, "*")
    .replace(/÷/g, "/")
    .replace(/²/g, "^2")
    .replace(/³/g, "^3")
    .replace(/√/g, "sqrt")
    .replace(/,/g, ".");
}


// =========================================
// LEITURA DE POLINÔMIOS
// Exemplo: 3x^2 + 2x - 5
// =========================================

function analisarPolinomio(texto) {
  let exp = normalizarExpressao(texto);

  exp = exp
    .replace(/f\(x\)\s*=/g, "")
    .replace(/y\s*=/g, "")
    .replace(/\s+/g, "")
    .replace(/\*/g, "");

  exp = exp.replace(/-/g, "+-");

  if (exp.startsWith("+")) {
    exp = exp.slice(1);
  }

  const termos = exp.split("+").filter(Boolean);

  const coeficientes = {};

  for (let termo of termos) {
    let coeficiente;
    let grau;

    if (termo.includes("x")) {
      const partes = termo.split("x");

      let parteCoef = partes[0];
      const parteGrau = partes[1];

      if (parteCoef === "" || parteCoef === "+") {
        coeficiente = 1;
      } else if (parteCoef === "-") {
        coeficiente = -1;
      } else {
        coeficiente = Number(parteCoef);
      }

      if (parteGrau === "") {
        grau = 1;
      } else if (parteGrau.startsWith("^")) {
        grau = Number(parteGrau.slice(1));
      } else {
        throw new Error("Formato de potência inválido.");
      }
    } else {
      coeficiente = Number(termo);
      grau = 0;
    }

    if (!Number.isFinite(coeficiente) || !Number.isInteger(grau) || grau < 0 || grau > 20) {
      throw new Error("Não foi possível interpretar essa expressão.");
    }

    coeficientes[grau] = (coeficientes[grau] || 0) + coeficiente;
  }

  return coeficientes;
}


// =========================================
// MONTAR POLINÔMIO
// =========================================

function montarPolinomio(coeficientes) {
  const graus = Object.keys(coeficientes)
    .map(Number)
    .sort((a, b) => b - a);

  const termos = [];

  for (const grau of graus) {
    const valor = coeficientes[grau];

    if (valor === 0) continue;

    const absoluto = Math.abs(valor);

    let parte;

    if (grau === 0) {
      parte = formatar(absoluto);
    } else if (grau === 1) {
      parte = (absoluto === 1 ? "" : formatar(absoluto)) + "x";
    } else {
      parte = (absoluto === 1 ? "" : formatar(absoluto)) + `x^${grau}`;
    }

    if (termos.length === 0) {
      termos.push(valor < 0 ? `-${parte}` : parte);
    } else {
      termos.push(valor < 0 ? ` - ${parte}` : ` + ${parte}`);
    }
  }

  return termos.join("") || "0";
}


// =========================================
// AVALIAR POLINÔMIO
// =========================================

function avaliarPolinomio(coeficientes, x) {
  let resultado = 0;

  for (const grau in coeficientes) {
    resultado += coeficientes[grau] * Math.pow(x, Number(grau));
  }

  return resultado;
}


// =========================================
// DERIVADA POLINOMIAL
// =========================================

function derivarPolinomio(coeficientes) {
  const derivada = {};

  for (const grau in coeficientes) {
    const n = Number(grau);

    if (n > 0) {
      derivada[n - 1] = coeficientes[grau] * n;
    }
  }

  return derivada;
}


// =========================================
// INTEGRAL POLINOMIAL
// =========================================

function integrarPolinomio(coeficientes) {
  const integral = {};

  for (const grau in coeficientes) {
    const n = Number(grau);

    integral[n + 1] = coeficientes[grau] / (n + 1);
  }

  return integral;
}


// =========================================
// CALCULAR LIMITES POLINOMIAIS
// =========================================

function calcularLimite(coeficientes, x0) {
  return avaliarPolinomio(coeficientes, x0);
}


// =========================================
// PASSOS DA RESOLUÇÃO
// =========================================

function criarPasso(titulo, descricao) {
  return `
    <div class="step-item">
      <strong>${escaparHTML(titulo)}</strong>
      <p>${escaparHTML(descricao)}</p>
    </div>
  `;
}


// =========================================
// RESOLUÇÃO DE FUNÇÕES
// =========================================

function resolverFuncao(coeficientes) {
  const grau = Math.max(...Object.keys(coeficientes).map(Number));

  if (grau > 2) {
    return `
      <h3>Função polinomial</h3>
      <div class="math-result">f(x) = ${escaparHTML(montarPolinomio(coeficientes))}</div>
      <p>Função polinomial de grau ${grau} identificada.</p>
      <p>O gráfico e a análise completa de raízes ainda precisam do motor matemático avançado.</p>
    `;
  }

  let html = `
    <h3>Função identificada</h3>
    <div class="math-result">f(x) = ${escaparHTML(montarPolinomio(coeficientes))}</div>
  `;

  if (grau === 0) {
    html += `
      ${criarPasso("Tipo", "Função constante. O valor não muda conforme x varia.")}
      <div class="math-result">f(x) = ${formatar(coeficientes[0] || 0)}</div>
    `;
  }

  if (grau === 1) {
    const a = coeficientes[1] || 0;
    const b = coeficientes[0] || 0;

    html += `
      ${criarPasso("Identificação", "Esta é uma função afim, representada por f(x) = ax + b.")}
      ${criarPasso("Coeficientes", `a = ${formatar(a)} e b = ${formatar(b)}.`)}
      ${criarPasso("Raiz da função", a !== 0 ? `x = -b/a = ${formatar(-b / a)}.` : "A função não possui raiz única.")}
      <div class="math-result">f(x) = ${escaparHTML(montarPolinomio(coeficientes))}</div>
    `;
  }

  if (grau === 2) {
    const a = coeficientes[2] || 0;
    const b = coeficientes[1] || 0;
    const c = coeficientes[0] || 0;

    const delta = b * b - 4 * a * c;

    html += `
      ${criarPasso("Identificação", "Esta é uma função quadrática, representada por f(x) = ax² + bx + c.")}
      ${criarPasso("Coeficientes", `a = ${formatar(a)}, b = ${formatar(b)} e c = ${formatar(c)}.`)}
      ${criarPasso("Discriminante", `Δ = b² - 4ac = ${formatar(delta)}.`)}
    `;

    if (delta > 0) {
      const x1 = (-b + Math.sqrt(delta)) / (2 * a);
      const x2 = (-b - Math.sqrt(delta)) / (2 * a);

      html += criarPasso("Raízes", `x₁ = ${formatar(x1)} e x₂ = ${formatar(x2)}.`);
    } else if (delta === 0) {
      html += criarPasso("Raiz", `A função possui uma raiz real dupla: x = ${formatar(-b / (2 * a))}.`);
    } else {
      html += criarPasso("Raízes", "A função não possui raízes reais.");
    }

    const xv = -b / (2 * a);
    const yv = avaliarPolinomio(coeficientes, xv);

    html += criarPasso("Vértice", `V = (${formatar(xv)}, ${formatar(yv)}).`);
  }

  return html;
}


// =========================================
// RESOLUÇÃO DE DERIVADAS
// =========================================

function resolverDerivada(coeficientes) {
  const derivada = derivarPolinomio(coeficientes);

  return `
    <h3>Derivada calculada</h3>

    <div class="math-result">
      f(x) = ${escaparHTML(montarPolinomio(coeficientes))}
    </div>

    ${criarPasso("Regra utilizada", "Regra da potência: a derivada de axⁿ é a·n·xⁿ⁻¹.")}

    ${criarPasso("Aplicação", "Multiplicamos cada coeficiente pelo expoente e reduzimos o expoente em uma unidade.")}

    <div class="math-result">
      f'(x) = ${escaparHTML(montarPolinomio(derivada))}
    </div>
  `;
}


// =========================================
// RESOLUÇÃO DE INTEGRAIS
// =========================================

function resolverIntegral(coeficientes) {
  const integral = integrarPolinomio(coeficientes);

  return `
    <h3>Integral indefinida</h3>

    <div class="math-result">
      f(x) = ${escaparHTML(montarPolinomio(coeficientes))}
    </div>

    ${criarPasso("Regra utilizada", "Regra da potência: somamos 1 ao expoente e dividimos o coeficiente pelo novo expoente.")}

    <div class="math-result">
      ∫ f(x) dx = ${escaparHTML(montarPolinomio(integral))} + C
    </div>

    ${criarPasso("Constante de integração", "C representa uma constante real arbitrária.")}
  `;
}


// =========================================
// RESOLUÇÃO DE LIMITES
// =========================================

function resolverLimite(coeficientes, texto) {
  const corresponde = texto.match(/(?:x\s*(?:tende|->|→)\s*|quando\s*x\s*(?:tende|->|→)\s*)([-+]?\d*\.?\d+)/i);

  if (!corresponde) {
    throw new Error("Informe para qual valor x tende. Exemplo: limite de x² + 2x quando x tende a 2.");
  }

  const x0 = Number(corresponde[1]);
  const valor = calcularLimite(coeficientes, x0);

  return `
    <h3>Limite calculado</h3>

    ${criarPasso("Identificação", `Queremos calcular o limite quando x tende a ${formatar(x0)}.`)}

    ${criarPasso("Substituição", `Substituímos x por ${formatar(x0)} na expressão polinomial.`)}

    <div class="math-result">
      lim f(x) = ${formatar(valor)}
    </div>

    ${criarPasso("Conclusão", `O limite é ${formatar(valor)}, pois polinômios são contínuos em todos os números reais.`)}
  `;
}


// =========================================
// IDENTIFICAR O TIPO DE OPERAÇÃO
// =========================================

function identificarAssunto(texto) {
  const t = texto.toLowerCase();

  if (t.includes("derivada") || t.includes("derivar") || t.includes("f'(x)")) {
    return "derivadas";
  }

  if (t.includes("integral") || t.includes("integrar")) {
    return "integrais";
  }

  if (t.includes("limite") || t.includes("lim ")) {
    return "limites";
  }

  return "funcoes";
}


// =========================================
// EXECUTAR RESOLUÇÃO
// =========================================

function resolverModoBasico(textoOriginal, tipo) {
  // Motor antigo (só polinômios) — usado apenas se o motor completo não carregar.
  if (tipo === "automatico") {
    tipo = identificarAssunto(textoOriginal);
  }

  if (tipo === "equacoes" || (tipo === "automatico" && /=/.test(textoOriginal) && !/f\(x\)\s*=/.test(textoOriginal))) {
    throw new Error("Equações precisam do motor completo. Abra a página por um servidor (ex.: Live Server).");
  }

  const limpo = textoOriginal
    .replace(/^.*?\b(derivada|integral|limite)\s+de\s+/i, "")
    .replace(/\s*(quando|com)\s+x\s+tende.*$/i, "");
  const coeficientes = analisarPolinomio(limpo);

  switch (tipo) {
    case "funcoes": return resolverFuncao(coeficientes);
    case "derivadas": return resolverDerivada(coeficientes);
    case "integrais": return resolverIntegral(coeficientes);
    case "limites": return resolverLimite(coeficientes, textoOriginal);
    default: throw new Error("No modo básico só é possível resolver polinômios.");
  }
}


// =========================================
// MOTOR COMPLETO (SymPy via Pyodide, em um Web Worker)
// =========================================

const TEMPO_LIMITE_MS = 30000;

const motor = {
  worker: null,
  estado: "carregando", // carregando | pronto | falhou
  pendentes: new Map(),
  proximoId: 1,
  config: window.HELPMATH_CONFIG || {}
};

const indicador = document.querySelector(".status-indicator");
const textoStatus = document.querySelector(".status-text");

function atualizarStatus(estado, texto) {
  motor.estado = estado;
  indicador.dataset.estado = estado;
  textoStatus.textContent = texto;
}

function iniciarMotor() {
  atualizarStatus("carregando", "Carregando motor matemático…");

  try {
    motor.worker = new Worker("worker.js");
  } catch (e) {
    atualizarStatus("falhou", "Modo básico (abra pelo servidor)");
    console.warn("HelpMath: Web Worker indisponível (a página foi aberta como arquivo?).", e);
    return;
  }

  motor.worker.onmessage = evento => {
    const msg = evento.data;

    if (msg.tipo === "pronto") {
      atualizarStatus("pronto", "Motor matemático pronto");
    } else if (msg.tipo === "falha") {
      atualizarStatus("falhou", "Modo básico (sem conexão com o motor)");
      console.error("HelpMath: falha ao carregar o motor:", msg.erro);
      motor.pendentes.forEach(p => p.reject(new Error("motor indisponível")));
      motor.pendentes.clear();
    } else if (msg.tipo === "resultado") {
      const pendente = motor.pendentes.get(msg.id);
      if (pendente) {
        clearTimeout(pendente.timer);
        motor.pendentes.delete(msg.id);
        pendente.resolve(msg.dados);
      }
    }
  };

  motor.worker.onerror = evento => {
    console.error("HelpMath: erro no worker:", evento.message);
    if (motor.estado === "carregando") {
      atualizarStatus("falhou", "Modo básico (abra pelo servidor)");
    }
  };

  motor.worker.postMessage({ tipo: "iniciar", config: motor.config });
}

function resolverNoMotor(texto, tipo) {
  return new Promise((resolve, reject) => {
    const id = motor.proximoId++;

    const timer = setTimeout(() => {
      motor.pendentes.delete(id);
      // Um cálculo travado não pode bloquear os próximos: reinicia o worker.
      motor.worker.terminate();
      motor.pendentes.forEach(p => p.reject(new Error("reiniciado")));
      motor.pendentes.clear();
      iniciarMotor();
      resolve({
        ok: false,
        erro: "O cálculo demorou demais e foi interrompido. Tente simplificar a expressão."
      });
    }, TEMPO_LIMITE_MS);

    motor.pendentes.set(id, { resolve, reject, timer });
    motor.worker.postMessage({ tipo: "resolver", id, texto, assunto: tipo });
  });
}


// =========================================
// EXIBIÇÃO DO RESULTADO
// =========================================

function renderizarTeX(latex, emBloco = true) {
  if (window.katex) {
    try {
      return katex.renderToString(latex, {
        displayMode: emBloco,
        throwOnError: false,
        output: "html"
      });
    } catch {
      /* cai no texto puro */
    }
  }
  return `<code>${escaparHTML(latex)}</code>`;
}

function montarResultado(dados) {
  let html = `<h3>${escaparHTML(dados.titulo)}</h3>`;

  if (dados.entrada !== dados.resultado) {
    html += `<div class="math-input">${renderizarTeX(dados.entrada)}</div>`;
  }

  html += `<div class="math-result">${renderizarTeX(dados.resultado)}`;
  if (dados.aproximacao) {
    html += `<div class="math-approx">≈ ${escaparHTML(dados.aproximacao)}</div>`;
  }
  html += `</div>`;

  (dados.avisos || []).forEach(aviso => {
    html += `<p class="math-warning">⚠ ${escaparHTML(aviso)}</p>`;
  });

  if (dados.passos && dados.passos.length) {
    html += `<h3>Passo a passo</h3>`;
    dados.passos.forEach(p => {
      html += `
        <div class="step-item">
          <strong>${escaparHTML(p.titulo)}</strong>
          ${p.texto ? `<p>${escaparHTML(p.texto)}</p>` : ""}
          ${p.latex ? `<div class="step-math">${renderizarTeX(p.latex)}</div>` : ""}
        </div>
      `;
    });
  }

  if (dados.grafico) {
    html += `<h3>Gráfico</h3><div class="graph-container">${desenharGrafico(dados.grafico)}</div>`;
  }

  return html;
}

function desenharGrafico({ x: xs, y: ys, variavel }) {
  const L = 640, A = 340, M = 34;
  const validos = ys.filter(v => v !== null);
  if (validos.length < 2) return "";

  // escala vertical robusta: ignora picos (assíntotas) usando percentis
  const ordenados = [...validos].sort((a, b) => a - b);
  const pct = q => ordenados[Math.min(ordenados.length - 1, Math.floor(q * (ordenados.length - 1)))];
  let yMin = Math.min(pct(0.03), 0);
  let yMax = Math.max(pct(0.97), 0);
  if (yMax - yMin < 1e-9) { yMin -= 1; yMax += 1; }
  const folga = (yMax - yMin) * 0.12;
  yMin -= folga; yMax += folga;

  const xMin = xs[0], xMax = xs[xs.length - 1];
  const px = v => M + (v - xMin) / (xMax - xMin) * (L - 2 * M);
  const py = v => A - M - (v - yMin) / (yMax - yMin) * (A - 2 * M);

  let caminho = "";
  let anterior = null;
  for (let i = 0; i < xs.length; i++) {
    const v = ys[i];
    const fora = v === null || v < yMin - (yMax - yMin) || v > yMax + (yMax - yMin);
    const salto = anterior !== null && v !== null && Math.abs(v - anterior) > (yMax - yMin) * 0.9;
    if (fora) { anterior = null; continue; }
    caminho += (anterior === null || salto ? "M" : "L") + px(xs[i]).toFixed(1) + "," + py(v).toFixed(1) + " ";
    anterior = v;
  }

  const eixoX = yMin <= 0 && yMax >= 0 ? py(0) : null;
  const eixoY = xMin <= 0 && xMax >= 0 ? px(0) : null;
  const rot = n => Number(n.toPrecision(3)).toString().replace(".", ",");

  return `
    <svg viewBox="0 0 ${L} ${A}" class="graph-svg" role="img" aria-label="Gráfico da função">
      <rect x="0" y="0" width="${L}" height="${A}" fill="#0c1427"/>
      ${eixoX !== null ? `<line x1="${M}" y1="${eixoX}" x2="${L - M}" y2="${eixoX}" class="graph-axis"/>` : ""}
      ${eixoY !== null ? `<line x1="${eixoY}" y1="${M}" x2="${eixoY}" y2="${A - M}" class="graph-axis"/>` : ""}
      <clipPath id="area-grafico"><rect x="${M}" y="${M}" width="${L - 2 * M}" height="${A - 2 * M}"/></clipPath>
      <path d="${caminho}" class="graph-line" clip-path="url(#area-grafico)"/>
      <text x="${M}" y="${A - 10}" class="graph-label">${rot(xMin)}</text>
      <text x="${L - M}" y="${A - 10}" class="graph-label" text-anchor="end">${rot(xMax)}</text>
      <text x="${L - M}" y="${M - 12}" class="graph-label" text-anchor="end">${escaparHTML(variavel)}</text>
      <text x="6" y="${M}" class="graph-label">${rot(yMax)}</text>
      <text x="6" y="${A - M}" class="graph-label">${rot(yMin)}</text>
    </svg>
  `;
}

function mostrarResultado(html) {
  resultado.innerHTML = html;
  areaResultado.hidden = false;

  setTimeout(() => {
    areaResultado.scrollIntoView({ behavior: "smooth", block: "start" });
  }, 100);
}


// =========================================
// EXECUTAR RESOLUÇÃO
// =========================================

async function resolver() {
  const textoOriginal = expressao.value.trim();

  erro.textContent = "";

  if (!textoOriginal) {
    erro.textContent = "Digite uma expressão matemática para começar.";
    expressao.focus();
    return;
  }

  const tipo = assunto.value;

  botaoCalcular.disabled = true;
  botaoCalcular.classList.add("loading");
  const rotulo = botaoCalcular.querySelector("span");
  const rotuloOriginal = rotulo.textContent;
  rotulo.textContent = motor.estado === "carregando" ? "Carregando motor…" : "Resolvendo…";

  try {
    if (motor.estado !== "falhou" && motor.worker) {
      let dados;
      try {
        dados = await resolverNoMotor(textoOriginal, tipo);
      } catch {
        dados = null; // motor caiu: usa o modo básico abaixo
      }

      if (dados) {
        if (!dados.ok) {
          throw new Error(dados.erro);
        }
        mostrarResultado(montarResultado(dados));
        salvarHistorico(textoOriginal, dados.tipo);
        return;
      }
    }

    // Modo básico
    const html = resolverModoBasico(textoOriginal, tipo);
    mostrarResultado(
      html + `<p class="math-warning">⚠ Resolvido no modo básico (apenas polinômios). O motor completo não está disponível.</p>`
    );
    salvarHistorico(textoOriginal, tipo);

  } catch (e) {
    erro.textContent = e.message || "Não foi possível resolver essa expressão.";
    areaResultado.hidden = true;
  } finally {
    botaoCalcular.disabled = false;
    botaoCalcular.classList.remove("loading");
    rotulo.textContent = rotuloOriginal;
  }
}


// =========================================
// HISTÓRICO LOCAL
// =========================================

function salvarHistorico(expressaoTexto, tipo) {
  let historico = [];

  try {
    historico = JSON.parse(localStorage.getItem("helpmath-historico")) || [];
  } catch {
    historico = [];
  }

  historico.unshift({
    expressao: expressaoTexto,
    tipo: tipo,
    data: new Date().toLocaleString("pt-BR")
  });

  historico = historico.slice(0, 30);

  localStorage.setItem("helpmath-historico", JSON.stringify(historico));
}

function mostrarHistorico() {
  let historico = [];

  try {
    historico = JSON.parse(localStorage.getItem("helpmath-historico")) || [];
  } catch {
    historico = [];
  }

  const pagina = document.getElementById("page-historico");

  const conteudo = historico.length
    ? historico.map(item => `
        <div class="step-item">
          <strong>${escaparHTML(item.expressao)}</strong>
          <p>${escaparHTML(item.tipo)} · ${escaparHTML(item.data)}</p>
          <button class="example-btn" data-history="${escaparHTML(item.expressao)}">
            Reutilizar expressão
          </button>
        </div>
      `).join("")
    : "<p>Você ainda não possui resoluções no histórico.</p>";

  pagina.querySelector(".placeholder-card").innerHTML = `
    <span>◷</span>
    <h2>Suas atividades</h2>
    ${conteudo}
    <button class="go-home" id="limpar-historico">Limpar histórico</button>
  `;

  pagina.querySelectorAll("[data-history]").forEach(botao => {
    botao.addEventListener("click", () => {
      expressao.value = botao.dataset.history;
      navegar("inicio");
    });
  });

  document.getElementById("limpar-historico").addEventListener("click", () => {
    localStorage.removeItem("helpmath-historico");
    mostrarHistorico();
  });
}


// Atualiza o histórico ao abrir sua página
document.querySelector('[data-page="historico"]').addEventListener("click", mostrarHistorico);


// =========================================
// LIMPAR CAMPOS
// =========================================

botaoLimpar.addEventListener("click", () => {
  expressao.value = "";
  erro.textContent = "";
  resultado.innerHTML = "";
  areaResultado.hidden = true;
  expressao.focus();
});


// =========================================
// EVENTOS
// =========================================

botaoCalcular.addEventListener("click", resolver);

expressao.addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    resolver();
  }
});


// =========================================
// INICIALIZAÇÃO
// =========================================

areaResultado.hidden = true;
iniciarMotor();
console.log("HelpMath iniciado com sucesso.");
