# Checklist da entrega final — Sprint 4

## 1. Rodar e validar localmente
- [ ] Criar o ambiente virtual e instalar as dependências: `pip install -r requirements.txt`
- [ ] Gerar a chave gratuita em <https://aistudio.google.com/apikey>
- [ ] Copiar `.env.example` para `.env` e preencher `GEMINI_API_KEY`
- [ ] Rodar os testes: `pytest -q` (esperado: **38 passed**)
- [ ] Subir a aplicação: `python run.py` e abrir <http://localhost:8000>
- [ ] Conferir no topo do painel: **"IA Generativa: Gemini (...)"** (se aparecer "modo offline", a chave não foi lida)
- [ ] Simular "Febre progressiva" e conferir se o alerta mostra **"gerado por gemini (...)"**
- [ ] Testar o chat do tutor com as perguntas sugeridas e o botão "Gerar resumo"
- [ ] Se o modelo padrão der erro, trocar `CLYVO_LLM_MODEL` no `.env` por um modelo listado no AI Studio (ex.: `gemini-2.5-flash`)
- [ ] Rodar `python ai/evaluate.py --with-llm` para registrar uma resposta real do Gemini em `docs/RESULTADOS.md`

## 2. Wokwi
- [ ] Colar o `simulation/smart_collar.ino` atualizado (com `deviceId`) no projeto do Wokwi e salvar
- [ ] Testar a ponte: `python gateway/serial_bridge.py --stdin < leituras.txt` (ou via RFC2217 no VS Code)
- [ ] Confirmar que o link do Wokwi no README e no `ENTREGA_SPRINT4.md` é o projeto correto

## 3. Repositório GitHub (vale até 20 pontos)
- [ ] Criar o repositório (sugestão: `Sprint04-IOT`) e subir o conteúdo da pasta `Sprint04-IOT/`
- [ ] **Não** subir o `.env` (já está no `.gitignore`); conferir que a chave não aparece em nenhum arquivo
- [ ] Conferir que `models/risk_model.joblib`, `ai/data/` e `docs/RESULTADOS.md` foram enviados
- [ ] Atualizar no README: link do repositório (seção 7.1, `git clone ...`) e link do vídeo
- [ ] Abrir o README no GitHub e verificar se os diagramas Mermaid e as tabelas aparecem corretamente
- [ ] Deixar o repositório **público** (ou dar acesso ao professor)

## 4. Vídeo pitch (vale até 20 pontos)
- [ ] Ensaiar com o roteiro em `docs/ROTEIRO_VIDEO_PITCH.md` (cerca de 5 min, os três integrantes falando)
- [ ] Apagar `database/clyvo.db` antes de gravar, para começar com os pacientes estáveis
- [ ] Mostrar: problema, arquitetura, Wokwi, painel da clínica (P1 + SOAP), app do tutor (WhatsApp, chat, guardrails, emergência), resumo diário e resultados
- [ ] Mostrar que a IA online é o Gemini (selo no topo e "gerado por gemini" no alerta)
- [ ] Gravar com áudio claro e zoom do navegador em 110–125%
- [ ] Publicar no YouTube como **não listado** e testar o link numa aba anônima

## 5. Documento e arquivo .zip
- [ ] Preencher em `ENTREGA_SPRINT4.md` os links do **YouTube** e do **GitHub**
- [ ] Exportar o documento para PDF (mesmo formato da entrega da Sprint 3)
- [ ] Montar o **.zip** com o PDF (ou um .txt) contendo os dois links obrigatórios
- [ ] Abrir o .zip depois de criado para garantir que não está vazio nem corrompido
- [ ] Enviar pela plataforma oficial dentro do prazo (não pelo Teams)

## 6. Conferência final com os critérios de avaliação
- [ ] **Aplicação técnica de IA (60 pts):** ML com comparação de modelos, LLM Gemini com RAG, guardrails e testes aparecem no vídeo e no README
- [ ] **Vídeo (20 pts):** claro, didático, cerca de 5 min, demonstração funcionando
- [ ] **Repositório e documentação (20 pts):** README com instruções de uso, tecnologias e resultados; estrutura organizada
