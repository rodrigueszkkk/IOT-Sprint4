"""Gera as imagens PNG dos diagramas a partir das fontes Mermaid em assets/diagramas/fonte/.

Opcional: só é preciso rodar se algum diagrama for alterado. As imagens já geradas
ficam versionadas em assets/diagramas/*.png e são as que o README usa.

Requisitos: pip install playwright  (usa o Microsoft Edge ou o Chrome já instalado)
Uso:        python assets/diagramas/gerar_diagramas.py
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent
FONTE = BASE / "fonte"

DIAGRAMAS = {
    "01_arquitetura": ("Arquitetura da solução", "Da coleira IoT às interfaces da clínica e do tutor"),
    "02_sequencia_alerta": ("Integração ponta a ponta", "O que acontece quando a coleira envia uma leitura crítica"),
    "03_fluxo_telemetria": ("Fluxo de uma leitura de telemetria", "Validação, classificação de risco, IA generativa e guardrails"),
    "04_fluxo_chat": ("Fluxo do assistente do tutor", "Guardrails antes e depois do LLM"),
    "05_modelo_dados": ("Modelo de dados", "Tabelas do banco (SQLite na demonstração, MySQL em produção)"),
}

PAGINA = """<!doctype html>
<html><head><meta charset="utf-8">
<style>
  body { margin: 0; background: #ffffff; font-family: "Segoe UI", Arial, sans-serif; }
  #card { display: inline-block; padding: 28px 36px 32px; background: #ffffff; }
  h1 { margin: 0; font-size: 22px; color: #17202e; }
  p { margin: 4px 0 20px; font-size: 14px; color: #5f6b7c; }
  .marca { display: inline-block; width: 10px; height: 22px; background: #0d7c86;
           border-radius: 3px; margin-right: 10px; vertical-align: -3px; }
</style></head>
<body><div id="card"><h1><span class="marca"></span>__TITULO__</h1><p>__SUBTITULO__</p><div id="out"></div></div>
<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.esm.min.mjs";
  mermaid.initialize({
    startOnLoad: false,
    theme: "base",
    fontFamily: "Segoe UI, Arial, sans-serif",
    themeVariables: {
      fontSize: "15px",
      primaryColor: "#e0f3f4", primaryBorderColor: "#0d7c86", primaryTextColor: "#17202e",
      lineColor: "#5f6b7c", textColor: "#17202e",
      actorBkg: "#e0f3f4", actorBorder: "#0d7c86", actorTextColor: "#17202e",
      signalColor: "#17202e", signalTextColor: "#17202e",
      labelBoxBkgColor: "#e0f3f4", sequenceNumberColor: "#ffffff",
      attributeBackgroundColorOdd: "#ffffff", attributeBackgroundColorEven: "#f4f6f9",
      edgeLabelBackground: "#ffffff"
    },
    flowchart: { useMaxWidth: false, curve: "basis", padding: 14, nodeSpacing: 40, rankSpacing: 50 },
    sequence: { useMaxWidth: false, actorMargin: 40, messageFontSize: 14, noteFontSize: 14 },
    er: { useMaxWidth: false, fontSize: 14 }
  });
  const { svg } = await mermaid.render("diagrama", __CODIGO__);
  const out = document.getElementById("out");
  out.innerHTML = svg;
  // Usa o tamanho real do desenho (viewBox) para a imagem não sair cortada nem encolhida
  const el = out.querySelector("svg");
  const vb = el.viewBox.baseVal;
  el.setAttribute("width", vb.width);
  el.setAttribute("height", vb.height);
  el.style.maxWidth = "none";
  window.pronto = true;
</script></body></html>"""


def main() -> None:
    import json

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge")
        except Exception:
            browser = p.chromium.launch(channel="chrome")
        for nome, (titulo, subtitulo) in DIAGRAMAS.items():
            # Página nova por diagrama: o set_content reaproveita o window e o "pronto" anterior
            page = browser.new_page(device_scale_factor=2, viewport={"width": 2400, "height": 1200})
            codigo = (FONTE / f"{nome}.mmd").read_text(encoding="utf-8")
            html = (PAGINA.replace("__TITULO__", titulo)
                    .replace("__SUBTITULO__", subtitulo)
                    .replace("__CODIGO__", json.dumps(codigo)))
            page.set_content(html)
            page.wait_for_function("window.pronto === true", timeout=30000)
            destino = BASE / f"{nome}.png"
            page.locator("#card").screenshot(path=str(destino))
            page.close()
            print(f"ok  {destino.relative_to(BASE.parent.parent)}")
        browser.close()


if __name__ == "__main__":
    main()
