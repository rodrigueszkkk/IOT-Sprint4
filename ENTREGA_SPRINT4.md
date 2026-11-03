# FIAP — Faculdade de Informática e Administração Paulista

**Tecnologia em Desenvolvimento de Sistemas**
**Disciplina:** Disruptive Architectures: IoT, IoB & Generative AI
**Professor:** Renan Rodrigues Mendes

# 4ª Sprint: Clyvo Pet — Coleira Inteligente com IA Generativa

**Integrantes:**
1. Kaiky Pereira Rodrigues da Silva — RM 564578
2. Gabriel Costa Solano — RM 562325
3. Leandro Guarido de Oliveira — RM 561760

**YouTube (não listado):** _adicionar link do vídeo pitch_
**GitHub:** _adicionar link do repositório (ex.: https://github.com/rodrigueszkkk/Sprint04-IOT)_
**Wokwi:** https://wokwi.com/projects/475084250105444353
**Entrega anterior (Sprint 3):** https://github.com/rodrigueszkkk/Sprint03-IOT

---

## Solução implementada

Nesta sprint, a solução de IA especificada na Sprint 3 foi implementada e integrada à aplicação da CLYVO VET:

- **Coleira IoT (Arduino/Wokwi):** monitora temperatura, frequência cardíaca, movimento pós-operatório e botão SOS, e envia JSON para a nuvem por uma ponte serial.
- **API REST (FastAPI) + banco de dados:** recebe a telemetria, guarda pets, prontuários, leituras, alertas, conversas e notificações.
- **Classificação de risco (Machine Learning):** Gradient Boosting escolhido entre 4 algoritmos por validação cruzada, treinado com 4.000 leituras. Classifica cada leitura em ESTÁVEL, ATENÇÃO ou CRÍTICO, com probabilidade, explicação e dupla checagem clínica (recall de casos críticos de 91,7%).
- **Copiloto clínico com IA Generativa (LLM + RAG):** usa o Google Gemini (API do Google AI Studio) com protocolos clínicos recuperados e o prontuário do paciente para escrever a mensagem de WhatsApp do tutor e o rascunho SOAP para a equipe veterinária, em JSON estruturado.
- **Assistente do tutor:** chat personalizado com o contexto do pet, guardrails para medicamentos humanos e escalonamento automático de emergências.
- **Resumo diário personalizado** da recuperação.
- **Painel web:** triagem da clínica, app do tutor e simulador da coleira.
- **Validação:** 38 testes automatizados e relatório de avaliação (`docs/RESULTADOS.md`): 12/12 cenários clínicos, RAG com 100% de acerto no top-3 e guardrails com 13/13.

Instruções de uso, tecnologias e resultados estão no `README.md` do repositório.
