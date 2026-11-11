"""
HelpMath — motor matemático (SymPy)

Executado no navegador via Pyodide (ver worker.js), mas também roda em
Python normal para testes:  python3 engine.py "derivada de x^x"

Entrada:  resolver(texto, assunto) -> str (JSON)
Saída:    {ok, tipo, titulo, entrada, resultado, aproximacao, passos, avisos, grafico}
          (entrada/resultado/latex dos passos em LaTeX para o KaTeX)
"""

import json
import re

import mpmath
from sympy import (
    Abs, Add, Derivative, E, Eq, Expr, FiniteSet, Function, I, ImageSet, Integer,
    Integral, Interval, Lambda, Mul, Pow, Rational, S, Symbol, Union, acos, acot,
    asin, atan, cos, cosh, cot, count_ops, csc, diff, dsolve, exp, factor,
    factorial, fraction, idiff, im, integrate, latex, limit, log, nan, nsimplify,
    oo, pi, re as re_part, sec, simplify, sin, sinh, solve, solveset, sqrt, tan,
    tanh, together, trigsimp, zoo, cancel, expand, Piecewise, ConditionSet,
    Complement, Intersection, lambdify, N, nsolve, Dummy, sympify,
)
from sympy.calculus.util import continuous_domain
from sympy.core.function import AppliedUndef
from sympy.parsing.sympy_parser import (
    convert_xor, implicit_multiplication_application, parse_expr,
    rationalize, standard_transformations,
)
from sympy.calculus.accumulationbounds import AccumBounds

# ---------------------------------------------------------------------------
# Símbolos e dicionário de nomes
# ---------------------------------------------------------------------------

x, y, z, t, k, n = (Symbol(s, real=True) for s in "xyztkn")
VARS = {"x": x, "y": y, "z": z, "t": t}
yfun = Function("y")

TRANSFORMACOES = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
    rationalize,   # 2.5 -> 5/2 : cálculo exato, sem erro de ponto flutuante
)


class _log10(Function):
    """log na base 10 (convenção brasileira: log x = log₁₀ x, ln x = logaritmo natural)."""
    nargs = 1

    @classmethod
    def eval(cls, arg):
        # log(arg, 10) devolve valor exato quando possível: log(100) = 2, log(0,001) = -3
        return log(arg, 10)

    def _latex(self, printer):
        return r"\log_{10}\left(" + printer._print(self.args[0]) + r"\right)"


class _logb(Function):
    """log em base qualquer: log_2(8), log2(8) -> logbase(2, 8) = 3."""
    nargs = 2

    @classmethod
    def eval(cls, base, arg):
        return log(arg, base)


NOMES = {
    "x": x, "y": y, "z": z, "t": t,
    "e": E, "E": E, "pi": pi, "oo": oo, "i": I,
    "ln": log, "log": _log10, "log10": _log10, "logbase": _logb,
    "sin": sin, "cos": cos, "tan": tan, "cot": cot, "sec": sec, "csc": csc,
    "asin": asin, "acos": acos, "atan": atan, "acot": acot,
    "sinh": sinh, "cosh": cosh, "tanh": tanh,
    "sqrt": sqrt, "exp": exp, "abs": Abs, "Abs": Abs,
}

FUNCOES_TEXTO = [
    # (padrão em português/variações, nome SymPy) — a ordem importa
    (r"arcsen|arcsin|asen|asin", "asin"),
    (r"arccos|acos", "acos"),
    (r"arctg|arctan|atg|atan", "atan"),
    (r"arccotg|arccot|acot", "acot"),
    (r"senh|sinh", "sinh"),
    (r"cosh", "cosh"),
    (r"tgh|tanh", "tanh"),
    (r"cossec|cosec|csc", "csc"),
    (r"cotg|cotan|cot", "cot"),
    (r"sen|sin", "sin"),
    (r"cos", "cos"),
    (r"tg|tan", "tan"),
    (r"sec", "sec"),
    (r"raiz", "sqrt"),
]
NOMES_FUNCOES = "asin|acos|atan|acot|sinh|cosh|tanh|csc|cot|sin|cos|tan|sec|sqrt|ln|log|exp|abs"


class ErroHelpMath(Exception):
    """Erro com mensagem amigável para o usuário."""


# ---------------------------------------------------------------------------
# Normalização do texto
# ---------------------------------------------------------------------------

SOBRESCRITOS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789-")


def normalizar(texto):
    s = texto.strip()
    s = (s.replace("−", "-").replace("–", "-").replace("×", "*").replace("·", "*")
          .replace("÷", "/").replace("π", "pi").replace("∞", "oo").replace("→", "->")
          .replace("√", "sqrt").replace("’", "'").replace("′", "'").replace("″", "''")
          .replace("⁺", "+").replace("₀", "0"))
    # graus -> radianos: sen(30°) = sen(30·π/180). "º" só vira grau se não for ordinal (2º grau, 2º ordem)
    s = re.sub(r"(\d)\s*°", r"\1*(pi/180)", s)
    s = re.sub(r"(\d)\s*º(?!\s*(?:ordem|derivada|grau))", r"\1*(pi/180)", s)
    # expoentes sobrescritos: x²  x⁻¹  -> x^(2) x^(-1)
    s = re.sub(r"([⁰¹²³⁴⁵⁶⁷⁸⁹⁻]+)", lambda m: "^(" + m.group(1).translate(SOBRESCRITOS) + ")", s)
    s = s.lower()
    s = re.sub(r"\binfinito\b", "oo", s)
    s = re.sub(r"\bmais\s+oo\b", "oo", s)
    s = re.sub(r"\bmenos\s+oo\b", "-oo", s)
    return s


def traduzir_funcoes(s):
    for padrao, nome in FUNCOES_TEXTO:
        s = re.sub(r"(?<![a-z])(?:" + padrao + r")(?![a-z])", nome, s)
    return s


def _fechar_parentese(s, i):
    """Índice do ')' que fecha o '(' em s[i]."""
    nivel = 0
    for j in range(i, len(s)):
        if s[j] == "(":
            nivel += 1
        elif s[j] == ")":
            nivel -= 1
            if nivel == 0:
                return j
    return -1


def ajustar_potencia_funcao(s):
    """sin^2(x) -> (sin(x))^2 ;  sin^2 x -> (sin(x))^2 ; sin x^2 fica sin(x^2)."""
    padrao = re.compile(r"\b(" + NOMES_FUNCOES + r")\^\(?(-?\d+)\)?\s*")
    while True:
        m = padrao.search(s)
        if not m:
            return s
        nome, exp_ = m.group(1), m.group(2)
        resto = s[m.end():]
        if resto.startswith("("):
            fim = _fechar_parentese(resto, 0)
            if fim < 0:
                raise ErroHelpMath("Parênteses não balanceados.")
            arg, depois = resto[1:fim], resto[fim + 1:]
        else:
            m2 = re.match(r"[a-z0-9.]+", resto)
            if not m2:
                raise ErroHelpMath(f"Não entendi o argumento de {nome}^{exp_}.")
            arg, depois = m2.group(0), resto[m2.end():]
        s = s[:m.start()] + f"({nome}({arg}))^({exp_})" + depois


def preparar(s):
    """Converte o texto (já normalizado) para sintaxe que o SymPy entende."""
    s = traduzir_funcoes(s)
    s = s.replace("**", "^")
    # log_2(8), log_{2}(8), log2(8) -> logbase(2, 8)
    s = re.sub(r"\blog_\{?\s*([0-9.]+|e)\s*\}?\s*\(", r"logbase(\1, ", s)
    s = re.sub(r"\blog(\d+)\s*\(", r"logbase(\1, ", s)
    # |x|  ->  abs(x)   (pares de barras não aninhados)
    s = re.sub(r"\|([^|]+)\|", r"abs(\1)", s)
    # vírgula decimal: 2,5 -> 2.5
    s = re.sub(r"(?<=\d),(?=\d)", ".", s)
    s = ajustar_potencia_funcao(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def verificar_parenteses(s):
    nivel = 0
    for c in s:
        if c in "([":
            nivel += 1
        elif c in ")]":
            nivel -= 1
            if nivel < 0:
                raise ErroHelpMath("Há um ')' sem o '(' correspondente.")
    if nivel > 0:
        raise ErroHelpMath("Há parênteses abertos que não foram fechados.")


def tex_entrada(s, extras=None):
    """LaTeX da expressão como o usuário digitou (sem reordenar os termos)."""
    try:
        return tex(ler(s, extras, avaliar=False), ordem="none")
    except Exception:
        return tex(ler(s, extras))


def ler(s, extras=None, avaliar=True):
    """Lê uma expressão matemática (texto) e devolve objeto SymPy."""
    s = preparar(s)
    if not s:
        raise ErroHelpMath("Expressão vazia.")
    verificar_parenteses(s)
    if re.search(r"[=<>]", s):
        raise ErroHelpMath("Sinal de igualdade/desigualdade inesperado nesta expressão.")
    nomes = dict(NOMES)
    if extras:
        nomes.update(extras)
    try:
        expr = parse_expr(s, local_dict=nomes, transformations=TRANSFORMACOES, evaluate=avaliar)
    except ErroHelpMath:
        raise
    except Exception:
        raise ErroHelpMath(f"Não consegui interpretar a expressão “{s}”. Confira a escrita.")
    if not isinstance(expr, Expr) and not hasattr(expr, "free_symbols"):
        raise ErroHelpMath("Expressão inválida.")
    desconhecidos = [str(sy) for sy in expr.free_symbols if sy not in VARS.values() and sy != n]
    if desconhecidos:
        raise ErroHelpMath(
            "Não reconheci: " + ", ".join(sorted(desconhecidos)) +
            ". Use x, y, z ou t como variáveis e funções como sen, cos, tg, ln, log, sqrt, e^x."
        )
    return expr


# ---------------------------------------------------------------------------
# Formatação
# ---------------------------------------------------------------------------

def tex(expr, ordem=None):
    s = latex(expr, ln_notation=True, order=ordem) if ordem else latex(expr, ln_notation=True)
    trocas = [
        (r"\operatorname{asin}", r"\operatorname{arcsen}"), (r"\arcsin", r"\operatorname{arcsen}"),
        (r"\operatorname{atan}", r"\operatorname{arctg}"), (r"\arctan", r"\operatorname{arctg}"),
        (r"\operatorname{acot}", r"\operatorname{arccotg}"),
        (r"\sinh", r"\operatorname{senh}"), (r"\tanh", r"\operatorname{tgh}"),
        (r"\sin", r"\operatorname{sen}"), (r"\tan", r"\operatorname{tg}"),
        (r"\cot", r"\operatorname{cotg}"), (r"\csc", r"\operatorname{cossec}"),
        (r"\operatorname{erfi}", r"\operatorname{erfi}"),
    ]
    for a, b in trocas:
        s = s.replace(a, b)
    # \operatorname{sen}h  (caso \sinh tenha sido tocado depois) — segurança
    return s


def num_str(valor, digitos=12):
    """Número em formato brasileiro (vírgula decimal)."""
    try:
        v = N(valor, digitos + 3)
    except Exception:
        return None
    if v.has(nan) or v.has(zoo) or v in (oo, -oo):
        return None
    if v.is_real is False or (v.is_number and abs(im(v)) > 1e-12 * max(1, abs(re_part(v)))):
        r_, i_ = re_part(v), im(v)
        parte_r = _fmt_real(r_, digitos)
        parte_i = _fmt_real(abs(i_), digitos)
        if parte_r == "0":
            return ("-" if i_ < 0 else "") + parte_i + "i"
        return parte_r + (" − " if i_ < 0 else " + ") + parte_i + "i"
    return _fmt_real(re_part(v), digitos)


def _fmt_real(v, digitos):
    f = float(v)
    if f == 0 or abs(f) < 1e-14:
        return "0"
    s = mpmath.nstr(mpmath.mpf(str(N(v, digitos + 5))), digitos, strip_zeros=True)
    if s.endswith(".0"):
        s = s[:-2]
    if "e" in s:
        mant, ex = s.split("e")
        return mant.replace(".", ",") + " × 10^" + str(int(ex))
    return s.replace(".", ",")


def eh_numero_exato_simples(expr):
    """True se a forma exata já é um decimal/inteiro (não vale mostrar ≈)."""
    return expr.is_Integer or expr.is_Float


def mais_simples(expr, *, trig=True):
    """Tenta várias simplificações e devolve a forma mais curta."""
    try:
        livres = expr.free_symbols
        if livres and expr.is_polynomial(*livres):
            return expand(expr)
    except Exception:
        pass
    candidatos = [expr]
    for f in (simplify, factor, cancel, together):
        try:
            candidatos.append(f(expr))
        except Exception:
            pass
    if trig:
        try:
            candidatos.append(trigsimp(expr))
        except Exception:
            pass
    validos = [c for c in candidatos if c is not None and not c.has(nan)]
    return min(validos, key=lambda c: (count_ops(c), len(str(c))))


def mesmo_valor(a, b, var, pontos=(0.37, 1.29, 2.71, -0.83, 0.61)):
    """Confere numericamente se duas expressões em `var` coincidem."""
    testados = 0
    for p in pontos:
        try:
            va = complex(N(a.subs(var, p), 30))
            vb = complex(N(b.subs(var, p), 30))
        except Exception:
            continue
        if any(map(lambda q: q != q or abs(q) == float("inf"), (va, vb))):
            continue
        testados += 1
        if abs(va - vb) > 1e-9 * max(1, abs(va)):
            return False
    return testados > 0


def passo(titulo, texto="", latex_=None):
    d = {"titulo": titulo, "texto": texto}
    if latex_ is not None:
        d["latex"] = latex_
    return d


def resposta(tipo, titulo, entrada, resultado, passos, aproximacao=None, avisos=None, grafico=None):
    return {
        "ok": True, "tipo": tipo, "titulo": titulo, "entrada": entrada,
        "resultado": resultado, "aproximacao": aproximacao, "passos": passos,
        "avisos": avisos or [], "grafico": grafico,
    }


def variavel_principal(expr, preferida=None):
    if preferida is not None:
        return preferida
    livres = expr.free_symbols & set(VARS.values())
    for v in (x, t, y, z):
        if v in livres:
            return v
    return x


# ---------------------------------------------------------------------------
# Gráfico (amostragem de pontos para o front-end desenhar)
# ---------------------------------------------------------------------------

def amostrar(expr, var, a=-10.0, b=10.0, qtd=400):
    try:
        f = lambdify(var, expr, modules=["mpmath"])
    except Exception:
        return None
    xs, ys = [], []
    for i in range(qtd + 1):
        xv = a + (b - a) * i / qtd
        try:
            v = f(mpmath.mpf(xv))
            if isinstance(v, mpmath.mpc):
                v = float(v.real) if abs(v.imag) < 1e-12 else None
            else:
                v = float(v)
            if v is not None and (v != v or abs(v) > 1e6):
                v = None
        except Exception:
            v = None
        xs.append(round(xv, 6))
        ys.append(v)
    if all(v is None for v in ys):
        return None
    return {"x": xs, "y": ys, "variavel": str(var)}


# ---------------------------------------------------------------------------
# LIMITES
# ---------------------------------------------------------------------------

RE_PONTO_LIM = re.compile(
    r"(?:\(|\b)\s*([xyzt])\s*(?:->|tende\s+(?:ao|à|a|para)|tendendo\s+(?:ao|à|a|para))\s*"
    r"(-?\s*oo|[-+]?\s*[0-9a-z.,/^()*+\-]+?)\s*(\+|-|⁺|⁻)?\s*(?:\)|\s|$|,)"
)


def interpretar_limite(s):
    # forma lim(x->a) expr   ou  lim_{x->a} expr
    direcao = None
    if re.search(r"pela\s+direita|à\s+direita", s):
        direcao = "+"
    if re.search(r"pela\s+esquerda|à\s+esquerda", s):
        direcao = "-"

    m = re.search(r"lim(?:ite)?\s*_?\{?\(?\s*([xyzt])\s*->\s*([^)}\s]+?)\s*(\+|-)?\s*[)}]", s)
    if m:
        var, ponto_txt = m.group(1), m.group(2)
        if m.group(3):
            direcao = m.group(3)
        corpo = s[m.end():]
    else:
        m = re.search(
            r"(?:quando|com|para)?\s*([xyzt])\s*(?:->|tende\s+(?:ao|à|a|para)|tendendo\s+(?:ao|à|a|para))\s*"
            r"(-?\s*oo|[-+]?[0-9a-z.,/^*()]+?)(\+|-)?(?=\s|$|,(?!\d)|\.(?!\d))", s)
        if not m:
            raise ErroHelpMath("Informe para onde a variável tende. Ex.: lim(x->0) sen(x)/x  ou  limite de ... quando x tende a 2.")
        var, ponto_txt = m.group(1), m.group(2)
        if m.group(3):
            direcao = m.group(3)
        corpo = s[:m.start()] + " " + s[m.end():]
        corpo = re.sub(r"\b(?:lim(?:ite)?|calcule|calcular|o|de|do|da|quando|pela\s+direita|pela\s+esquerda)\b", " ", corpo)
    corpo = re.sub(r"^\s*(?:de|do|da)\b", " ", corpo)
    corpo = re.sub(r"\b(?:pela\s+direita|pela\s+esquerda)\b", " ", corpo).strip(" ,.:")
    ponto_txt = ponto_txt.replace(" ", "").rstrip(".,")
    if ponto_txt.endswith("+") or ponto_txt.endswith("-"):
        if ponto_txt not in ("+", "-") and not ponto_txt.endswith("oo"):
            direcao, ponto_txt = ponto_txt[-1], ponto_txt[:-1]
    return VARS[var], ponto_txt, direcao, corpo


def forma_indeterminada(expr, var, ponto):
    """Detecta 0/0, ∞/∞, ∞−∞, 0·∞, 1^∞, 0^0, ∞^0 por substituição."""
    def lim_parte(e):
        try:
            return limit(e, var, ponto)
        except Exception:
            return None

    def eh_inf(v):
        return v in (oo, -oo, zoo)

    try:
        num, den = fraction(together(expr))
        if den != 1 and den.has(var):
            ln_, ld_ = lim_parte(num), lim_parte(den)
            if ln_ == 0 and ld_ == 0:
                return "0/0"
            if ln_ is not None and ld_ is not None and eh_inf(ln_) and eh_inf(ld_):
                return "∞/∞"
    except Exception:
        pass
    if isinstance(expr, Pow) and expr.exp.has(var):
        b, e_ = lim_parte(expr.base), lim_parte(expr.exp)
        if b == 1 and e_ is not None and eh_inf(e_):
            return "1^∞"
        if b == 0 and e_ == 0:
            return "0^0"
        if b is not None and eh_inf(b) and e_ == 0:
            return "∞^0"
    if isinstance(expr, Add):
        lims = [lim_parte(a) for a in expr.args]
        if any(l == oo for l in lims) and any(l == -oo for l in lims):
            return "∞ − ∞"
    if isinstance(expr, Mul):
        lims = [lim_parte(a) for a in expr.args]
        if any(l == 0 for l in lims) and any(l is not None and eh_inf(l) for l in lims):
            return "0 · ∞"
    return None


def resolver_limite(s):
    var, ponto_txt, direcao, corpo = interpretar_limite(s)
    if not corpo:
        raise ErroHelpMath("Não encontrei a função do limite.")
    ponto = ler(ponto_txt)
    f = ler(corpo)
    ent_ponto = tex(ponto) + ("^{+}" if direcao == "+" else "^{-}" if direcao == "-" else "")
    entrada = r"\lim_{" + tex(var) + r" \to " + ent_ponto + "} " + tex_entrada(corpo)
    passos = []
    avisos = []

    # Substituição direta
    if ponto.is_finite:
        try:
            direto = simplify(f.subs(var, ponto))
        except Exception:
            direto = nan
        if direto.is_number and direto.is_finite and direto.is_real and not direto.has(nan, zoo):
            passos.append(passo("Substituição direta",
                                f"Substituindo {var} = {ponto_txt}, a expressão vale um número finito:",
                                tex(direto)))
        else:
            passos.append(passo("Substituição direta",
                                "A substituição direta não dá um valor definido, então é preciso analisar o comportamento perto do ponto."))
    forma = forma_indeterminada(f, var, ponto)
    if forma:
        dica = {
            "0/0": "Usar L'Hôpital, fatoração ou expansão em série de Taylor.",
            "∞/∞": "Comparar os termos dominantes ou usar L'Hôpital.",
            "∞ − ∞": "Racionalizar ou reunir em uma única fração.",
            "0 · ∞": "Reescrever como quociente (0/0 ou ∞/∞).",
            "1^∞": "Usar o limite fundamental: lim (1 + u)^{1/u} = e, ou aplicar ln.",
            "0^0": "Aplicar logaritmo: e^{lim g·ln f}.",
            "∞^0": "Aplicar logaritmo: e^{lim g·ln f}.",
        }[forma]
        passos.append(passo("Forma indeterminada", f"O limite tem a forma {forma}. {dica}"))

    def calc(d):
        return limit(f, var, ponto, dir=d)

    def oscila(v):
        return isinstance(v, AccumBounds)

    if ponto in (oo, -oo):
        L = limit(f, var, ponto)
        laterais = None
    elif direcao:
        L = calc(direcao)
        laterais = None
    else:
        Ld, Le = calc("+"), calc("-")
        laterais = (Le, Ld)
        if oscila(Ld) or oscila(Le):
            L, laterais = (Ld if oscila(Ld) else Le), None
        else:
            L = Ld if Ld == Le or simplify(Ld - Le) == 0 else None

    if laterais and L is None:
        Le, Ld = laterais
        passos.append(passo("Limites laterais", "Pela esquerda e pela direita os valores são diferentes:",
                            r"\lim_{" + tex(var) + r"\to " + tex(ponto) + "^-} = " + tex(Le) +
                            r",\quad \lim_{" + tex(var) + r"\to " + tex(ponto) + "^+} = " + tex(Ld)))
        return resposta("limite", "Limite", entrada, r"\text{O limite não existe}", passos,
                        avisos=["Os limites laterais são diferentes, por isso o limite bilateral não existe."])
    if laterais:
        passos.append(passo("Limites laterais", "Os limites pela esquerda e pela direita coincidem.",
                            tex(L)))

    if isinstance(L, AccumBounds):
        return resposta("limite", "Limite", entrada, r"\text{O limite não existe (oscila)}",
                        passos + [passo("Oscilação", "A função oscila entre " + tex(L.min) + " e " + tex(L.max) + ".")])
    if L.func.__name__ == "Limit":
        raise ErroHelpMath("Não consegui calcular esse limite de forma exata.")

    L = mais_simples(L)
    passos.append(passo("Resultado", "", r"\lim = " + tex(L)))
    if L == zoo:
        resultado = r"\infty \ (\text{sem sinal definido})"
    else:
        resultado = tex(L)
    aprox = None if (L.is_Integer or not L.is_finite) else num_str(L)
    return resposta("limite", "Limite", entrada, resultado, passos, aproximacao=aprox, avisos=avisos,
                    grafico=amostrar_perto(f, var, ponto))


def amostrar_perto(f, var, ponto):
    if ponto in (oo, -oo) or not ponto.is_real:
        return amostrar(f, var, -20, 20) if ponto in (oo, -oo) else None
    p = float(ponto)
    return amostrar(f, var, p - 4, p + 4)


# ---------------------------------------------------------------------------
# DERIVADAS
# ---------------------------------------------------------------------------

ORDENS = {"primeira": 1, "segunda": 2, "terceira": 3, "quarta": 4, "quinta": 5,
          "sexta": 6, "sétima": 7, "setima": 7, "oitava": 8, "nona": 9, "décima": 10, "decima": 10}


def regras_usadas(f, var):
    regras = []
    def visita(e):
        if isinstance(e, Pow):
            if e.base.has(var) and e.exp.has(var):
                regras.append("derivação logarítmica (variável na base e no expoente)")
            elif e.exp.is_negative and e.base.has(var):
                regras.append("regra do quociente / potência negativa")
            elif e.base.has(var) and e.base != var:
                regras.append("regra da cadeia")
            elif e.base.has(var):
                regras.append("regra da potência")
            elif e.exp.has(var):
                regras.append("derivada da exponencial")
        elif isinstance(e, Mul):
            fatores = [a for a in e.args if a.has(var)]
            if len(fatores) >= 2:
                regras.append("regra do produto")
        elif hasattr(e, "func") and e.is_Function and e.args and e.args[0].has(var):
            if e.args[0] != var:
                regras.append("regra da cadeia")
        for a in getattr(e, "args", ()):
            visita(a)
    visita(f)
    vistos = []
    for r in regras:
        if r not in vistos:
            vistos.append(r)
    return vistos


def resolver_derivada(s):
    ordem = 1
    var = None
    m = re.search(r"d\^?\(?(\d+)\)?\s*/\s*d([xyzt])\^?\(?\d*\)?", s)
    if m:
        ordem, var = int(m.group(1)), VARS[m.group(2)]
        s = s[:m.start()] + " " + s[m.end():]
    m = re.search(r"d\^?\(?n\)?\s*/\s*d[xyzt]\^?\(?n?\)?|n-?[ée]sima|ordem\s+n\b", s)
    if m:
        return derivada_n_esima(s[:m.start()] + " " + s[m.end():])
    m = re.search(r"(?:∂|d)\s*/\s*(?:∂|d)\s*([xyzt])", s)
    if m:
        var = VARS[m.group(1)]
        s = s[:m.start()] + " " + s[m.end():]
    nomes_ordem = "|".join(ORDENS)
    m = (re.search(r"\b(" + nomes_ordem + r")\s+derivada", s) or
         re.search(r"\bderivada\s+(" + nomes_ordem + r")\b", s))
    if m:
        ordem = ORDENS[m.group(1)]
    # "2ª derivada", "2a derivada", "derivada 2ª", "3º derivada"
    m = (re.search(r"\b(\d+)\s*[ªaºo]\s+derivada\b", s) or
         re.search(r"\bderivada\s+(\d+)\s*[ªaºo](?!\w)", s))
    if m:
        ordem = int(m.group(1))
        s = s[:m.start()] + " derivada " + s[m.end():]
    # "ordem 2", "2ª ordem", "de segunda ordem"
    m = re.search(r"ordem\s+(\d+)", s) or re.search(r"\b(\d+)\s*[ªaºo]?\s+ordem\b", s)
    if m:
        ordem = int(m.group(1))
        s = s[:m.start()] + " " + s[m.end():]
    m = re.search(r"\b(" + nomes_ordem + r")\s+ordem\b", s)
    if m:
        ordem = ORDENS[m.group(1)]
        s = s[:m.start()] + " " + s[m.end():]
    m = re.search(r"em\s+rela[çc][ãa]o\s+a\s+([xyzt])", s)
    if m:
        var = VARS[m.group(1)]
        s = s[:m.start()] + " " + s[m.end():]
    implicita = "implícita" in s or "implicita" in s
    s = re.sub(r"\b(?:calcule|calcular|encontre|ache|a|o|de|da|do|derivada|derive|derivar|"
               r"primeira|segunda|terceira|quarta|quinta|sexta|s[ée]tima|oitava|nona|d[ée]cima|"
               r"impl[íi]cita|parcial)\b", " ", s)
    s = re.sub(r"\b[fgh]\s*\(\s*[xyzt]\s*\)\s*=", " ", s)
    s = re.sub(r"^\s*y\s*=(?!=)", " ", s).strip(" :,.")
    if ordem > 30:
        raise ErroHelpMath("Ordem de derivada muito alta (máximo 30).")

    # derivada implícita: equação em x e y
    if "=" in s:
        esq, dir_ = s.split("=", 1)
        F = ler(esq) - ler(dir_)
        if not F.has(y):
            raise ErroHelpMath("Para derivada implícita, a equação deve envolver x e y.")
        dy = mais_simples(idiff(F, y, x, ordem))
        entrada = tex_entrada(esq) + " = " + tex_entrada(dir_)
        simb = r"\frac{dy}{dx}" if ordem == 1 else r"\frac{d^{%d}y}{dx^{%d}}" % (ordem, ordem)
        passos = [
            passo("Derivação implícita", "Derivamos os dois lados em relação a x, tratando y como função de x (y = y(x)) e aplicando a regra da cadeia em cada termo com y."),
            passo("Isolando dy/dx", "", simb + " = " + tex(dy)),
        ]
        return resposta("derivada", "Derivada implícita", entrada, simb + " = " + tex(dy), passos)

    f = ler(s)
    var = variavel_principal(f, var)
    entrada_f = tex_entrada(s)
    bruto = diff(f, var, ordem)
    d = mais_simples(bruto)
    if not mesmo_valor(d, bruto, var):
        d = bruto
    simb = ("f'" if ordem == 1 else "f''" if ordem == 2 else "f^{(%d)}" % ordem) + "(" + tex(var) + ")"
    passos = [passo("Função", "", "f(" + tex(var) + ") = " + entrada_f)]
    regras = regras_usadas(f, var)
    if regras:
        passos.append(passo("Regras aplicadas", ", ".join(regras).capitalize() + "."))
    if ordem > 1:
        atual = f
        for i in range(1, min(ordem, 4)):
            atual = diff(atual, var)
            passos.append(passo(f"Derivada de ordem {i}", "", tex(mais_simples(atual))))
    passos.append(passo("Simplificação", "", simb + " = " + tex(d)))
    rotulo = "d" if ordem == 1 else "d^{%d}" % ordem
    entrada = r"\frac{" + rotulo + "}{d" + tex(var) + ("^{%d}" % ordem if ordem > 1 else "") + r"}\left[" + entrada_f + r"\right]"
    return resposta("derivada", "Derivada", entrada, simb + " = " + tex(d), passos,
                    grafico=amostrar(f, var))


def derivada_n_esima(s):
    s = re.sub(r"\b(?:calcule|a|o|de|da|do|derivada|ordem)\b", " ", s)
    s = re.sub(r"\b[fgh]\s*\(\s*x\s*\)\s*=", " ", s).strip(" :,.")
    f = ler(s)
    var = variavel_principal(f)
    derivs = [f]
    for _ in range(6):
        derivs.append(mais_simples(diff(derivs[-1], var)))
    passos = [passo(f"Derivada {i}", "", tex(derivs[i])) for i in range(1, 5)]
    # tenta reconhecer padrão  (a·n + P(x))·g(x)  checando um palpite
    nn = Symbol("n", integer=True, positive=True)
    palpites = []
    try:
        for g in (exp(var), exp(-var), sin(var), cos(var)):
            q = [simplify(dk / g) for dk in derivs[1:6]]
            if all(qi.is_polynomial(var) for qi in q):
                # ajusta polinômio em n de grau ≤ 2 coeficiente a coeficiente
                from sympy import interpolate
                cand = interpolate([(i + 1, q[i]) for i in range(3)], nn)
                cand = expand(cand)
                if all(simplify(cand.subs(nn, i + 1) - q[i]) == 0 for i in range(5)):
                    palpites.append(factor(cand) * g)
                break
    except Exception:
        pass
    if palpites:
        res = palpites[0]
        passos.append(passo("Padrão encontrado", "Comparando as derivadas sucessivas, o padrão vale para todo n ≥ 1 (conferido até n = 5).",
                            tex(res)))
        return resposta("derivada", "Derivada de ordem n", r"\frac{d^n}{d" + tex(var) + r"^n}\left[" + tex(f) + r"\right]",
                        r"f^{(n)}(" + tex(var) + ") = " + tex(res), passos)
    return resposta("derivada", "Derivadas sucessivas", tex(f), tex(derivs[4]), passos,
                    avisos=["Não encontrei uma fórmula geral para a derivada de ordem n; mostrando as primeiras derivadas."])


# ---------------------------------------------------------------------------
# INTEGRAIS
# ---------------------------------------------------------------------------

ESPECIAIS = ("erf", "erfi", "erfc", "Si", "Ci", "Ei", "li", "fresnels", "fresnelc",
             "gamma", "uppergamma", "lowergamma", "polylog", "LambertW", "hyper", "Shi", "Chi", "expint")


def funcoes_especiais(expr):
    return sorted({f.func.__name__ for f in expr.atoms(Function) if f.func.__name__ in ESPECIAIS})


def com_modulo_no_log(F, f, var):
    """log(u) -> ln|u| quando u pode ser negativo (antiderivada real correta)."""
    if f.has(log):
        return F

    repl = {}
    for L in F.atoms(log):
        u = L.args[0]
        if u.has(I) or u.is_positive or isinstance(u, Abs):
            continue
        repl[L] = log(Abs(u))
    return F.xreplace(repl) if repl else F


def interpretar_integral(s):
    a = b = None
    var = None
    # ∫[a, b] ...  ou ∫_a^b ...  ou ∫_{a}^{b}
    m = re.search(r"∫\s*\[\s*([^,\]]+?)\s*[,;]\s*([^\]]+?)\s*\]", s)
    if m:
        a, b = m.group(1), m.group(2)
        s = s[:m.start()] + " " + s[m.end():]
    else:
        m = re.search(r"∫\s*_\s*\{?([^}^\s]+)\}?\s*\^\s*\{?([^}\s]+)\}?", s)
        if m:
            a, b = m.group(1), m.group(2)
            s = s[:m.start()] + " " + s[m.end():]
    if a is None:
        # "integral de 0 a 1 de x^2"  (limites antes da função)
        m = re.search(r"\b(?:de|entre)\s+(-?[0-9a-z.,/^*()+]+?)\s+(?:a|até|ate|e)\s+(-?[0-9a-z.,/^*()+]+?)\s+(?:de|da|do)\s+(.+)$", s)
        if m and not re.search(r"\b(?:de|entre)\s", m.group(3)):
            a, b = m.group(1), m.group(2)
            s = s[:m.start()] + " " + m.group(3)
    if a is None:
        m = re.search(r"(?:\bde|\bentre|\bno\s+intervalo\s+de|\bdesde)\s+(-?[0-9a-z.,/^*()+]+?)\s+(?:a|até|ate|e)\s+(-?[0-9a-z.,/^*()+]+?)\s*$", s)
        if m:
            a, b = m.group(1), m.group(2)
            s = s[:m.start()]
        else:
            m = re.search(r"\[\s*(-?[^,\]]+?)\s*[,;]\s*(-?[^\]]+?)\s*\]\s*$", s)
            if m:
                a, b = m.group(1), m.group(2)
                s = s[:m.start()]
    m = re.search(r"(?:^|(?<=[\s∫]))d([xyzt])\s*/", s)
    if m:
        var = VARS[m.group(1)]
        s = s[:m.start()] + "1/" + s[m.end():]
    m = re.search(r"\bd([xyzt])\b\s*$", s.strip()) if var is None else None
    if m:
        var = VARS[m.group(1)]
        s = s.strip()[:-2]
    elif var is None:
        m = re.search(r"\s\*?d([xyzt])\b", s)
        if m:
            var = VARS[m.group(1)]
            s = s[:m.start()] + " " + s[m.end():]
    s = s.replace("∫", " ")
    s = re.sub(r"\b(?:calcule|calcular|a|o|integral|integre|integrar|indefinida|definida|de|da|do)\b", " ", s)
    s = re.sub(r"\b[fgh]\s*\(\s*[xyzt]\s*\)\s*=", " ", s).strip(" :,.")
    return s, var, a, b


def singularidades_no_intervalo(f, var, a, b):
    from sympy import singularities
    pontos = set()
    try:
        sing = singularities(f, var, Interval(a, b))
        if isinstance(sing, FiniteSet):
            pontos |= set(sing)
    except Exception:
        pass
    try:
        num, den = fraction(together(f))
        if den.has(var):
            raizes = solveset(den, var, Interval(a, b))
            if isinstance(raizes, FiniteSet):
                pontos |= set(raizes)
    except Exception:
        pass
    return sorted([p for p in pontos if p.is_real], key=lambda p: float(p))


def integral_numerica(f, var, a, b):
    fl = lambdify(var, f, modules=["mpmath"])
    mpmath.mp.dps = 30
    try:
        def g(t_):
            v = fl(t_)
            return v
        aa = mpmath.inf if a == oo else -mpmath.inf if a == -oo else mpmath.mpf(str(N(a, 35)))
        bb = mpmath.inf if b == oo else -mpmath.inf if b == -oo else mpmath.mpf(str(N(b, 35)))
        v, err = mpmath.quad(g, [aa, bb], error=True, maxdegree=10)
        return v, err
    finally:
        mpmath.mp.dps = 15


def resolver_integral(s):
    corpo, var, a_txt, b_txt = interpretar_integral(s)
    if not corpo:
        raise ErroHelpMath("Não encontrei a função a ser integrada.")
    f = ler(corpo)
    var = variavel_principal(f, var)
    entrada_f = tex_entrada(corpo)
    passos = [passo("Integrando", "", "f(" + tex(var) + ") = " + entrada_f)]
    avisos = []

    if a_txt is None:
        F = integrate(f, var)
        if F.has(Integral):
            raise ErroHelpMath("Não encontrei uma primitiva em forma fechada para essa integral.")
        F = com_modulo_no_log(F, f, var)
        F2 = mais_simples(F)
        if mesmo_valor(diff(F2, var), f, var):
            F = F2
        especiais = funcoes_especiais(F)
        if especiais:
            avisos.append("Essa integral não tem primitiva elementar; o resultado usa a função especial " +
                          ", ".join(especiais) + ".")
        ok = mesmo_valor(diff(F, var), f, var) or simplify(diff(F, var) - f) == 0
        passos.append(passo("Primitiva", "", r"\int f\,d" + tex(var) + " = " + tex(F) + " + C"))
        passos.append(passo("Verificação", "Derivando o resultado obtemos de volta o integrando ✓" if ok else
                            "Não foi possível conferir automaticamente derivando o resultado."))
        entrada = r"\int " + entrada_f + r"\,d" + tex(var)
        return resposta("integral", "Integral indefinida", entrada, tex(F) + " + C", passos, avisos=avisos,
                        grafico=amostrar(f, var))

    # definida
    a, b = ler(a_txt), ler(b_txt)
    entrada = r"\int_{" + tex(a) + "}^{" + tex(b) + "} " + entrada_f + r"\,d" + tex(var)
    imprópria = a in (oo, -oo) or b in (oo, -oo)
    sing = [] if imprópria and False else singularidades_no_intervalo(f, var, min(a, b) if a.is_real and b.is_real and a.is_finite and b.is_finite else a, max(a, b) if a.is_finite and b.is_finite else b) if (a.is_finite and b.is_finite) else []
    if sing:
        imprópria = True
        passos.append(passo("Integral imprópria", "O integrando não está definido em " +
                            ", ".join(f"{var} = {p}" for p in sing) + " — é preciso analisar como limite."))
        pontos = [a] + [p for p in sing if p != a and p != b] + [b]
        partes = []
        for p, q in zip(pontos, pontos[1:]):
            partes.append(integrate(f, (var, p, q)))
        valor = Add(*partes) if all(v.is_finite for v in partes) else None
        diverge = [v for v in partes if not v.is_finite or v.has(nan)]
        if diverge or valor is None:
            passos.append(passo("Convergência", "Pelo menos uma das partes diverge (vai para ±∞), então a integral diverge."))
            return resposta("integral", "Integral definida", entrada, r"\text{A integral diverge}", passos,
                            avisos=["Cuidado: a integral não vale 0 só porque a função é ímpar — ela não converge."])
    else:
        valor = integrate(f, (var, a, b))

    if valor.has(nan) or valor in (oo, -oo, zoo):
        passos.append(passo("Convergência", "A integral não converge para um número finito."))
        return resposta("integral", "Integral definida", entrada, r"\text{A integral diverge}" if valor != oo and valor != -oo else tex(valor), passos)

    numerico, erro_num = None, None
    try:
        numerico, erro_num = integral_numerica(f, var, a, b)
    except Exception:
        pass

    if valor.has(Integral):
        if numerico is None:
            raise ErroHelpMath("Não consegui calcular essa integral nem numericamente.")
        passos.append(passo("Sem forma fechada", "Não existe primitiva elementar; o valor foi calculado numericamente (quadratura de alta precisão)."))
        aprox = num_str(sympify(str(mpmath.nstr(numerico, 20))), 12)
        return resposta("integral", "Integral definida", entrada, r"\approx " + aprox.replace(",", "{,}"), passos)

    valor = mais_simples(valor)
    if not imprópria:
        F = integrate(f, var)
        if not F.has(Integral):
            F = com_modulo_no_log(mais_simples(F), f, var)
            passos.append(passo("Primitiva", "", "F(" + tex(var) + ") = " + tex(F)))
            passos.append(passo("Teorema Fundamental do Cálculo", "", "F(" + tex(b) + ") - F(" + tex(a) + ") = " + tex(valor)))
    else:
        passos.append(passo("Integral imprópria", "Calculada como limite nos extremos.", tex(valor)))
    if numerico is not None and valor.is_finite:
        dif = abs(complex(N(valor, 30)) - complex(numerico))
        if dif < 1e-8 * max(1, abs(complex(numerico))):
            passos.append(passo("Conferência numérica", "O valor numérico (quadratura) confirma o resultado ✓"))
        else:
            avisos.append("O resultado exato e a conferência numérica não bateram — confira o enunciado.")
    aprox = None if eh_numero_exato_simples(valor) else num_str(valor)
    return resposta("integral", "Integral definida", entrada, tex(valor), passos, aproximacao=aprox,
                    grafico=amostrar(f, var, float(a) - 1 if a.is_finite else -10, float(b) + 1 if b.is_finite else 10))


# ---------------------------------------------------------------------------
# EQUAÇÕES
# ---------------------------------------------------------------------------

def valida_raiz(lhs, rhs, var, r):
    """Confere se r satisfaz a equação ORIGINAL nos reais (elimina raízes estranhas)."""
    try:
        a = N(lhs.subs(var, r), 40)
        b = N(rhs.subs(var, r), 40)
    except Exception:
        return False
    if a.has(nan, zoo, oo, -oo) or b.has(nan, zoo, oo, -oo):
        return False
    try:
        ca, cb = complex(a), complex(b)
    except Exception:
        return False
    if abs(ca.imag) > 1e-20 or abs(cb.imag) > 1e-20:
        return False
    return abs(ca - cb) <= 1e-15 * max(1, abs(ca))


def raizes_numericas(F, var, a=-60, b=60, passos_=3000):
    """Varredura por mudança de sinal + mínimos de |F| e refinamento com findroot."""
    try:
        fl = lambdify(var, F, modules=["mpmath"])
    except Exception:
        return []

    def val(xv):
        try:
            v = fl(mpmath.mpf(xv))
            if isinstance(v, mpmath.mpc):
                if abs(v.imag) > 1e-12:
                    return None
                v = v.real
            v = float(v)
            return v if v == v and abs(v) != float("inf") else None
        except Exception:
            return None

    h = (b - a) / passos_
    xs = [a + i * h for i in range(passos_ + 1)]
    vs = [val(xv) for xv in xs]
    candidatos = []
    for i in range(passos_):
        v0, v1 = vs[i], vs[i + 1]
        if v0 is None or v1 is None:
            continue
        if v0 == 0:
            candidatos.append(xs[i])
        elif v0 * v1 < 0:
            candidatos.append((xs[i] + xs[i + 1]) / 2)
        if 0 < i < passos_ and vs[i - 1] is not None:
            # mínimo local de |F| quase tocando zero (raiz dupla)
            if abs(v0) < abs(vs[i - 1]) and abs(v0) <= abs(v1) and abs(v0) < 1e-3:
                candidatos.append(xs[i])
    raizes = []
    mpmath.mp.dps = 40
    try:
        for c in candidatos:
            try:
                r = mpmath.findroot(lambda q: fl(q), mpmath.mpf(c))
                if isinstance(r, mpmath.mpc):
                    if abs(r.imag) > 1e-20:
                        continue
                    r = r.real
                if abs(fl(r)) > 1e-20:
                    continue
                if all(abs(r - q) > 1e-12 for q in raizes):
                    raizes.append(r)
            except Exception:
                continue
    finally:
        mpmath.mp.dps = 15
    return sorted(raizes)


def formatar_conjunto_periodico(conj):
    """ImageSet(Lambda(n, 2nπ + π/6), Integers)  ->  π/6 + 2kπ"""
    partes = conj.args if isinstance(conj, Union) else (conj,)
    saidas = []
    for p in partes:
        if isinstance(p, ImageSet):
            lam = p.lamda
            expr_ = lam.expr.subs(lam.variables[0], k)
            const = expr_.subs(k, 0)
            per = simplify(expr_ - const)
            saidas.append((const, tex(const) + " + " + tex(per)))
        elif isinstance(p, FiniteSet):
            for v in p:
                saidas.append((v, tex(v)))
        else:
            return None
    # ordena pela parte constante em [0, 2π)
    def chave(item):
        try:
            return float(item[0] % (2 * pi))
        except Exception:
            return 0
    saidas.sort(key=chave)
    return [s_ for _, s_ in saidas]


def resolver_equacao(s):
    s = re.sub(r"\b(?:resolva|resolver|calcule|encontre|ache|a|o|equa[çc][ãa]o)\b\s*:?", " ", s).strip(" :,.")
    if ";" in s or "\n" in s or s.count("=") > 1:
        raise ErroHelpMath("O HelpMath resolve uma equação por vez (sistemas não são suportados).")
    if s.count("=") != 1:
        raise ErroHelpMath("Digite uma equação com um único sinal de igual. Ex.: x^2 - 5x + 6 = 0")
    esq, dir_ = s.split("=")
    lhs, rhs = ler(esq), ler(dir_)
    F = lhs - rhs
    entrada = tex_entrada(esq) + " = " + tex_entrada(dir_)
    livres = F.free_symbols
    if not livres:
        ok = simplify(F) == 0
        return resposta("equacao", "Igualdade", entrada,
                        r"\text{Verdadeira}" if ok else r"\text{Falsa}", [])
    var = variavel_principal(F)
    passos = [passo("Equação", "Levando tudo para um lado:", tex(mais_simples(F)) + " = 0")]
    avisos = []
    try:
        dominio = continuous_domain(F, var, S.Reals)
        if dominio != S.Reals:
            passos.append(passo("Domínio", "Condição de existência (valores permitidos):", tex(dominio)))
    except Exception:
        pass

    # caso polinomial em uma variável
    outras = livres - {var}
    if outras:
        sol = solve(Eq(lhs, rhs), var)
        if not sol:
            raise ErroHelpMath("Não encontrei solução para " + str(var) + ".")
        res = r",\quad ".join(tex(var) + " = " + tex(mais_simples(s_)) for s_ in sol)
        return resposta("equacao", f"Isolando {var}", entrada, res, passos)

    conj = None
    try:
        conj = solveset(F, var, S.Reals)
    except Exception:
        conj = None

    exatas = []
    periodicas = None
    numericas_necessarias = True
    if isinstance(conj, FiniteSet):
        exatas = list(conj)
        numericas_necessarias = not F.is_polynomial(var)
        if F.is_polynomial(var):
            numericas_necessarias = False
    elif conj is not None and (isinstance(conj, ImageSet) or (isinstance(conj, Union) and all(isinstance(a_, (ImageSet, FiniteSet)) for a_ in conj.args))):
        periodicas = formatar_conjunto_periodico(conj)
        numericas_necessarias = periodicas is None
    elif conj == S.EmptySet:
        numericas_necessarias = not F.is_polynomial(var)
    elif conj == S.Reals:
        return resposta("equacao", "Identidade", entrada, r"\text{Verdadeira para todo } " + tex(var) + r" \in \mathbb{R}", passos)

    if periodicas:
        res = r",\quad ".join(tex(var) + " = " + p for p in periodicas)
        passos.append(passo("Soluções gerais", "Com k inteiro (k ∈ ℤ):", res))
        return resposta("equacao", "Equação trigonométrica", entrada, res + r",\ k \in \mathbb{Z}", passos)

    if numericas_necessarias and not exatas:
        try:
            for r in solve(Eq(lhs, rhs), var):
                if r.is_real is not False:
                    exatas.append(r)
        except Exception:
            pass

    # elimina raízes estranhas testando na equação original
    validas, estranhas = [], []
    for r in exatas:
        (validas if valida_raiz(lhs, rhs, var, r) else estranhas).append(r)
    if estranhas:
        passos.append(passo("Verificação", "Substituindo na equação original, estes valores NÃO servem (raízes estranhas ou fora do domínio):",
                            r",\ ".join(tex(var) + " = " + tex(r) for r in estranhas)))

    numericas = []
    if numericas_necessarias:
        for r in raizes_numericas(F, var):
            if all(abs(float(N(v)) - float(r)) > 1e-9 for v in validas):
                numericas.append(r)
        if numericas:
            avisos.append("Algumas soluções foram encontradas numericamente (busca em [−60, 60]).")

    validas = sorted(validas, key=lambda v: float(N(v)))
    if not validas and not numericas:
        if F.is_polynomial(var):
            complexas = solveset(F, var, S.Complexes)
            if isinstance(complexas, FiniteSet) and complexas:
                lista = [mais_simples(c) for c in complexas]
                res = r",\quad ".join(tex(var) + " = " + tex(c) for c in lista)
                passos.append(passo("Nos reais", "Não há solução real."))
                passos.append(passo("Nos complexos", "", res))
                return resposta("equacao", "Equação (soluções complexas)", entrada, res, passos,
                                avisos=["A equação não tem soluções reais; as soluções mostradas são complexas."])
        return resposta("equacao", "Equação", entrada, r"\text{Sem solução real}", passos, avisos=avisos)

    itens = []
    aprox = []
    for v in validas:
        v = mais_simples(v)
        txt = tex(var) + " = " + tex(v)
        if not (v.is_Integer or v.is_Rational):
            a_ = num_str(v)
            if a_:
                txt += r" \approx " + a_.replace(",", "{,}")
        itens.append(txt)
    for r in sorted(numericas):
        a_ = num_str(sympify(mpmath.nstr(r, 25)), 12)
        itens.append(tex(var) + r" \approx " + a_.replace(",", "{,}"))
    res = r",\quad ".join(itens)
    passos.append(passo("Verificação", "Todas as soluções foram conferidas substituindo na equação original ✓"))
    return resposta("equacao", "Equação", entrada, res, passos, avisos=avisos,
                    grafico=amostrar(F, var, *intervalo_grafico([float(N(v)) for v in validas] + [float(r) for r in numericas])))


def intervalo_grafico(raizes):
    if not raizes:
        return (-10, 10)
    lo, hi = min(raizes), max(raizes)
    margem = max(2, (hi - lo) * 0.3)
    return (lo - margem, hi + margem)


# ---------------------------------------------------------------------------
# EQUAÇÕES DIFERENCIAIS
# ---------------------------------------------------------------------------

def ler_edo(s):
    Y = yfun(x)
    extras = {"y": Y, "ydddd": Y.diff(x, 4), "yddd": Y.diff(x, 3), "ydd": Y.diff(x, 2), "yd": Y.diff(x)}
    s = re.sub(r"d\^?2\s*y\s*/\s*dx\^?2", "ydd", s)
    s = re.sub(r"dy\s*/\s*dx", "yd", s)
    s = s.replace("y''''", "ydddd").replace("y'''", "yddd").replace("y''", "ydd").replace("y'", "yd")
    return s, extras, Y


def resolver_edo(s):
    s = re.sub(r"\b(?:resolva|resolver|a|edo|equa[çc][ãa]o\s+diferencial)\b\s*:?", " ", s)
    s, extras, Y = ler_edo(s)
    partes = [p.strip() for p in re.split(r"[;,]|\s+e\s+|\bcom\b", s) if p.strip()]
    edo_txt, ics = None, {}
    for p in partes:
        m = re.match(r"^(yd*)\s*\(\s*([^)]+)\)\s*=\s*(.+)$", p)
        if m:
            ordem = m.group(1).count("d")
            ponto = ler(m.group(2))
            valor = ler(m.group(3))
            chave = Y.subs(x, ponto) if ordem == 0 else Y.diff(x, ordem).subs(x, ponto)
            ics[chave] = valor
        elif "=" in p and edo_txt is None:
            edo_txt = p
    if edo_txt is None:
        raise ErroHelpMath("Não encontrei a equação diferencial. Ex.: y'' + y = 0, y(0) = 0, y'(0) = 1")
    esq, dir_ = edo_txt.split("=", 1)
    lhs = ler(esq, extras)
    rhs = ler(dir_, extras)
    eq = Eq(lhs, rhs)
    entrada = tex(lhs) + " = " + tex(rhs)
    try:
        sol = dsolve(eq, Y, ics=ics or None)
    except Exception as ex:
        raise ErroHelpMath("Não consegui resolver essa equação diferencial.")
    sols = sol if isinstance(sol, list) else [sol]
    passos = [passo("Classificação", "Equação diferencial ordinária de ordem " + str(max(
        [d.derivative_count for d in eq.atoms(Derivative)] or [0])) + ".")]
    if ics:
        passos.append(passo("Condições iniciais", "", r",\ ".join(tex(k_) + " = " + tex(v) for k_, v in ics.items())))
    res = r",\quad ".join(tex(s_.lhs) + " = " + tex(expand(s_.rhs) if count_ops(expand(s_.rhs)) <= count_ops(s_.rhs) + 2 else s_.rhs) for s_ in sols)
    ok = True
    try:
        from sympy import checkodesol
        ok = all(checkodesol(eq, s_)[0] for s_ in sols)
    except Exception:
        pass
    passos.append(passo("Verificação", "Substituindo a solução na equação ela é satisfeita ✓" if ok else "Verificação automática inconclusiva."))
    if not ics:
        passos.append(passo("Constantes", "C₁, C₂, … são constantes arbitrárias (dependem das condições iniciais)."))
    return resposta("edo", "Equação diferencial", entrada, res, passos)


# ---------------------------------------------------------------------------
# FUNÇÕES / EXPRESSÕES NUMÉRICAS
# ---------------------------------------------------------------------------

def resolver_expressao(s):
    original = s
    s = re.sub(r"\b(?:calcule|calcular|quanto\s+[ée]|qual\s+o\s+valor\s+de|o\s+valor\s+de|simplifique)\b", " ", s)
    m = re.match(r"^\s*([fgh])\s*\(\s*([xyzt])\s*\)\s*=\s*(.+)$", s)
    if m:
        return resolver_funcao(m.group(3), VARS[m.group(2)])
    m = re.match(r"^\s*y\s*=\s*(.+)$", s)
    if m:
        return resolver_funcao(m.group(1), x)
    expr_txt = s.strip(" :,.?")
    bruto = ler(expr_txt, avaliar=False)
    if bruto.free_symbols:
        return resolver_funcao(expr_txt, None)

    entrada = tex(bruto)
    valor = ler(expr_txt)
    avisos = []
    passos = []
    if re.search(r"(?<![0-9.])0\s*\^\s*\(?\s*0(?![0-9.])", preparar(expr_txt)):
        avisos.append("0⁰ é uma forma indeterminada em limites; em álgebra, por convenção, vale 1.")
    if valor.has(zoo) or valor.has(nan):
        if re.search(r"/\s*\(?\s*0+(?:\.0*)?\s*\)?(?![0-9.])", preparar(expr_txt)):
            return resposta("expressao", "Expressão numérica", entrada, r"\text{Indefinido (divisão por zero)}", [],
                            avisos=["Não existe divisão por zero nos números reais."])
        return resposta("expressao", "Expressão numérica", entrada, r"\text{Indefinido}", [],
                        avisos=["A expressão não tem valor definido."])
    if valor.has(I) or (valor.is_real is False):
        avisos.append("Não existe nos números reais. O valor mostrado é no conjunto dos números complexos.")
    simpl = mais_simples(valor)
    try:
        sn = nsimplify(simpl) if simpl.is_Float else simpl
    except Exception:
        sn = simpl
    inteiro_gauss = simpl.is_number and re_part(simpl).is_Integer and im(simpl).is_Integer
    aprox = None if (inteiro_gauss or simpl.has(zoo)) else num_str(simpl)
    if simpl.is_Float:
        aprox = None
    return resposta("expressao", "Expressão numérica", entrada, tex(simpl), passos, aproximacao=aprox, avisos=avisos)


def resolver_funcao(expr_txt, var):
    f = ler(expr_txt)
    var = variavel_principal(f, var)
    entrada = "f(" + tex(var) + ") = " + tex_entrada(expr_txt)
    passos = []
    try:
        dom = continuous_domain(f, var, S.Reals)
        passos.append(passo("Domínio", "", tex(dom) if dom != S.Reals else r"\mathbb{R}"))
    except Exception:
        dom = S.Reals
    try:
        if dom.contains(0) == True:
            passos.append(passo("Intercepto com o eixo y", "", "f(0) = " + tex(simplify(f.subs(var, 0)))))
    except Exception:
        pass
    raizes_f, criticos_f = [], []
    try:
        cj = solveset(f, var, S.Reals)
        if isinstance(cj, FiniteSet) and len(cj) <= 8:
            raizes_f = list(cj)
    except Exception:
        pass
    # raízes
    try:
        r = resolver_equacao(expr_txt + " = 0")
        if r["resultado"] and "Sem solução" not in r["resultado"]:
            passos.append(passo("Raízes (f = 0)", "", r["resultado"]))
        else:
            passos.append(passo("Raízes (f = 0)", "A função não corta o eixo x."))
    except Exception:
        pass
    df = mais_simples(diff(f, var))
    passos.append(passo("Derivada", "", "f'(" + tex(var) + ") = " + tex(df)))
    # pontos críticos / vértice (só para casos simples)
    try:
        crit = solveset(df, var, S.Reals)
        if isinstance(crit, FiniteSet) and 0 < len(crit) <= 6:
            criticos_f = list(crit)
            itens = []
            d2 = diff(f, var, 2)
            for c in sorted(crit, key=lambda v: float(N(v))):
                tipo = ""
                sinal = d2.subs(var, c)
                if sinal.is_positive:
                    tipo = r"\ (\text{mínimo})"
                elif sinal.is_negative:
                    tipo = r"\ (\text{máximo})"
                itens.append(r"\left(" + tex(c) + r",\ " + tex(simplify(f.subs(var, c))) + r"\right)" + tipo)
            passos.append(passo("Pontos críticos", "", r",\quad ".join(itens)))
    except Exception:
        pass
    if f.is_polynomial(var):
        g = f.as_poly(var).degree()
        nomes = {0: "constante", 1: "afim (1º grau)", 2: "quadrática (2º grau)", 3: "cúbica (3º grau)"}
        passos.insert(0, passo("Tipo", "Função polinomial " + nomes.get(g, f"de grau {g}") + "."))
    pontos_chave = []
    for conj in (raizes_f, criticos_f):
        pontos_chave += [float(N(v)) for v in conj if v.is_real]
    a_, b_ = intervalo_grafico(pontos_chave)
    if not pontos_chave:
        a_, b_ = (-10, 10)
    return resposta("funcao", "Análise da função", entrada, "f(" + tex(var) + ") = " + tex(mais_simples(f)), passos,
                    grafico=amostrar(f, var, a_, b_))


# ---------------------------------------------------------------------------
# Identificação automática
# ---------------------------------------------------------------------------

def identificar(s):
    if re.search(r"y'|dy\s*/\s*dx|d\^?2\s*y|equa[çc][ãa]o\s+diferencial|\bedo\b", s) and "=" in s:
        return "edo"
    if re.search(r"\bderiv|d\^?\(?[\dn]*\)?\s*/\s*d[xyzt]|∂\s*/|\bf'+\s*\(", s):
        return "derivadas"
    if "∫" in s or re.search(r"\bintegr", s):
        return "integrais"
    if re.search(r"\blim(?:ite)?\b|->|tende\s+(?:ao|à|a|para)", s):
        return "limites"
    if "=" in s and not re.match(r"^\s*(?:[fgh]\s*\(\s*[xyzt]\s*\)|y)\s*=", s):
        return "equacoes"
    return "funcoes"


def resolver(texto, assunto="automatico"):
    try:
        s = normalizar(texto)
        if not s:
            raise ErroHelpMath("Digite uma expressão matemática para começar.")
        tipo = identificar(s) if assunto in (None, "", "automatico") else assunto
        if tipo == "equacoes" and re.search(r"y'|dy\s*/\s*dx", s):
            tipo = "edo"
        if tipo == "limites":
            out = resolver_limite(s)
        elif tipo == "derivadas":
            out = resolver_derivada(s)
        elif tipo == "integrais":
            out = resolver_integral(s)
        elif tipo == "equacoes":
            out = resolver_equacao(s)
        elif tipo == "edo":
            raise ErroHelpMath("O HelpMath não resolve equações diferenciais.")
        else:
            out = resolver_expressao(s)
        return json.dumps(out, ensure_ascii=False)
    except ErroHelpMath as e:
        return json.dumps({"ok": False, "erro": str(e)}, ensure_ascii=False)
    except RecursionError:
        return json.dumps({"ok": False, "erro": "Expressão complexa demais para resolver."}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "erro": "Não foi possível resolver: " + type(e).__name__ +
                           ". Confira a escrita da expressão."}, ensure_ascii=False)


if __name__ == "__main__":
    import sys
    print(json.dumps(json.loads(resolver(" ".join(sys.argv[1:]))), ensure_ascii=False, indent=2))
