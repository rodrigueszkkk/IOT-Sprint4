# Resultados da avaliação — CLYVO VET Sprint 4

Gerado automaticamente por `python ai/evaluate.py`. Dataset sintético rotulado por regras clínicas com 4% de ruído de rótulo (ver `ai/generate_dataset.py`).

## 1. Classificador de risco (Machine Learning)

- Linhas do dataset: **4000** — distribuição: {'ESTÁVEL': 1551, 'ATENÇÃO': 1340, 'CRÍTICO': 1109}
- Modelo selecionado: **GradientBoosting** (maior F1-macro na validação cruzada 5-fold)

| Modelo | F1-macro (CV média) | Desvio |
| --- | --- | --- |
| LogisticRegression | 0.6114 | 0.0161 |
| DecisionTree | 0.8546 | 0.0125 |
| RandomForest | 0.8937 | 0.0108 |
| GradientBoosting | 0.8995 | 0.0103 |

**Conjunto de teste (holdout 25%):**

| Métrica | Valor |
| --- | --- |
| Acurácia | 0.893 |
| F1-macro | 0.890 |
| Recall CRÍTICO (modelo puro) | 0.859 |
| Acurácia (sistema final: modelo + dupla checagem) | 0.906 |
| Recall CRÍTICO (sistema final) | 0.917 |

> Os rótulos do dataset têm 4% de ruído proposital (discordância entre veterinários), por isso nem o sistema final chega a 100%.

**Matriz de confusão** (linhas = real, colunas = previsto):

|  | ESTÁVEL | ATENÇÃO | CRÍTICO |
| --- | --- | --- | --- |
| ESTÁVEL | 369 | 19 | 0 |
| ATENÇÃO | 28 | 286 | 21 |
| CRÍTICO | 1 | 38 | 238 |

**Importância das variáveis:**

| Variável | Importância |
| --- | --- |
| temp_celsius | 0.3546 |
| movement_level | 0.1301 |
| emergency_btn | 0.094 |
| needs_post_op | 0.0634 |
| hr_rel_high | 0.0554 |
| days_post_op | 0.0543 |
| age | 0.0502 |
| hr_rel_low | 0.0411 |
| heart_rate_bpm | 0.0011 |
| species | 0.0005 |

## 2. Cenários clínicos de referência

Acerto do modelo puro: **12/12** · acerto do sistema final (modelo + dupla checagem de segurança): **12/12**

| Cenário | Leitura | Esperado | Modelo puro | Sistema final | Override |  |
| --- | --- | --- | --- | --- | --- | --- |
| Cão D4 pós-osteossíntese, sinais normais | 38.5°C / 95 BPM / REPOUSO | ESTÁVEL | ESTÁVEL | ESTÁVEL | - | ✅ |
| Cão D4, febrícula isolada | 39.3°C / 110 BPM / REPOUSO | ATENÇÃO | ATENÇÃO | ATENÇÃO | - | ✅ |
| Cão D4, febre + taquicardia + agitação | 39.9°C / 152 BPM / ALTO | CRÍTICO | CRÍTICO | CRÍTICO | - | ✅ |
| Cão D4, hipertermia severa em repouso | 40.4°C / 120 BPM / REPOUSO | CRÍTICO | CRÍTICO | CRÍTICO | - | ✅ |
| Cão D10, agitação sem febre | 38.7°C / 105 BPM / ALTO | ATENÇÃO | ATENÇÃO | ATENÇÃO | - | ✅ |
| Gata D1 pós-castração, FC 170 (normal felino) | 38.6°C / 170 BPM / REPOUSO | ESTÁVEL | ESTÁVEL | ESTÁVEL | - | ✅ |
| Gata D1, hipotermia pós-anestésica | 36.7°C / 110 BPM / REPOUSO | CRÍTICO | CRÍTICO | CRÍTICO | - | ✅ |
| Gata D1, taquicardia acentuada | 38.9°C / 230 BPM / REPOUSO | ATENÇÃO | ATENÇÃO | ATENÇÃO | - | ✅ |
| Cão idoso cardiopata, sinais normais | 38.4°C / 112 BPM / REPOUSO | ESTÁVEL | ESTÁVEL | ESTÁVEL | - | ✅ |
| Cão idoso cardiopata, taquicardia leve | 38.6°C / 150 BPM / REPOUSO | ATENÇÃO | ATENÇÃO | ATENÇÃO | - | ✅ |
| Cão idoso, bradicardia acentuada | 38.0°C / 45 BPM / REPOUSO | CRÍTICO | CRÍTICO | CRÍTICO | - | ✅ |
| SOS do tutor com sinais normais | 38.5°C / 95 BPM / REPOUSO / SOS | CRÍTICO | CRÍTICO | CRÍTICO | - | ✅ |

## 3. Recuperação de protocolos (RAG)

- Trechos indexados: **37** (10 protocolos clínicos)
- **hit@1 = 14/15 (93%)** · **hit@3 = 15/15 (100%)**

| Pergunta do tutor | Protocolo esperado | 1º recuperado | Top-3 |
| --- | --- | --- | --- |
| febre no quinto dia depois da cirurgia | 02_febre_e_infeccao.md | 02_febre_e_infeccao.md | ✅ |
| posso dar paracetamol para o meu gato | 05_medicamentos_proibidos.md | 05_medicamentos_proibidos.md | ✅ |
| ibuprofeno faz mal para cachorro | 05_medicamentos_proibidos.md | 05_medicamentos_proibidos.md | ✅ |
| gata castrada não quer comer | 08_castracao_felina.md | 08_castracao_felina.md | ✅ |
| cachorro operado do fêmur pulou do sofá | 07_ortopedia_osteossintese.md | 07_ortopedia_osteossintese.md | ✅ |
| temperatura baixa depois da anestesia | 04_hipotermia_pos_anestesica.md | 04_hipotermia_pos_anestesica.md | ✅ |
| convulsão e gengiva roxa | 06_sinais_de_emergencia.md | 06_sinais_de_emergencia.md | ✅ |
| coração acelerado depois da cirurgia dor | 03_alteracoes_cardiacas.md | 03_alteracoes_cardiacas.md | ✅ |
| respiração rápida dormindo cão idoso cardíaco | 09_cardiopatia_geriatrica.md | 09_cardiopatia_geriatrica.md | ✅ |
| ferida vermelha com secreção e pontos | 01_cuidados_pos_operatorios.md | 01_cuidados_pos_operatorios.md | ✅ |
| o que significa prioridade P1 vermelho | 10_protocolo_triagem_clinica.md | 10_protocolo_triagem_clinica.md | ✅ |
| quanto tempo de repouso depois da cirurgia | 01_cuidados_pos_operatorios.md | 01_cuidados_pos_operatorios.md | ✅ |
| meu cachoro ta com febri depois da cirurgia | 02_febre_e_infeccao.md | 01_cuidados_pos_operatorios.md | ✅ |
| gatinha castrda nao qer comer | 08_castracao_felina.md | 08_castracao_felina.md | ✅ |
| ele ta com o coracao muito acelerdo | 03_alteracoes_cardiacas.md | 03_alteracoes_cardiacas.md | ✅ |

## 4. Guardrails do assistente

Acerto: **13/13**

| Mensagem | Esperado | Detectado |  |
| --- | --- | --- | --- |
| Ele está tendo convulsão | emergencia | emergencia | ✅ |
| os pontos abriram | emergencia | emergencia | ✅ |
| está vomitando sangue | emergencia | emergencia | ✅ |
| a gengiva está branca | emergencia | emergencia | ✅ |
| posso dar paracetamol? | medicamento | medicamento | ✅ |
| dou um ibuprofeno? | medicamento | medicamento | ✅ |
| e dipirona de gotas? | medicamento | medicamento | ✅ |
| ele comeu bem hoje | nenhum | nenhum | ✅ |
| qual o horário do meloxicam? | nenhum | nenhum | ✅ |
| pode passear na guia? | nenhum | nenhum | ✅ |
| a gengiva dele está bem roxa | emergencia | emergencia | ✅ |
| ela desmaiou agora | emergencia | emergencia | ✅ |
| ele lambeu a ferida mas está tudo bem | nenhum | nenhum | ✅ |

## 5. Pipeline ponta a ponta (IoT → ML → RAG → IA Generativa → notificação)

Executado com a IA generativa em modo offline (determinístico) para medir a latência do pipeline sem rede.

| Cenário | Pet | Risco | Alerta | Itens no plano SOAP | Protocolos citados | Latência |
| --- | --- | --- | --- | --- | --- | --- |
| normal | Thor | ESTÁVEL | não | - | - | 36 ms |
| atencao | Thor | ATENÇÃO | sim | 4 | K1, K2, K3, K4 | 41 ms |
| critico | Thor | CRÍTICO | sim | 8 | K1, K2, K3, K4 | 49 ms |
| sos | Bob | CRÍTICO | sim | 2 | K1, K2, K3, K4 | 46 ms |
| hipotermia | Luna | CRÍTICO | sim | 5 | K1, K2, K3, K4 | 48 ms |

### Exemplo de alerta gerado (cenário crítico — Thor)

```text
🚨 *ALERTA URGENTE CLYVO VET*

Oi, Mariana! A coleira do(a) *Thor* detectou: temperatura elevada (39.9°C), sinal de febre; coração acelerado (151 batimentos por minuto); movimentação acima do permitido para o repouso da cirurgia.

*O que fazer agora:*
1. Deixe Thor em local fresco e arejado, com água à vontade.
2. Mantenha Thor contido e sem pular ou correr — o esforço pode soltar o implante do fêmur.
3. NÃO ofereça remédios de uso humano (paracetamol, ibuprofeno etc.).
4. Venha agora para o pronto-atendimento da CLYVO VET mais próxima.

📍 A equipe de plantão já recebeu o prontuário do Thor e está aguardando vocês.

_Esta orientação é um apoio da IA CLYVO VET e não substitui a avaliação do médico-veterinário._
```

```text
S: Alerta automático da coleira. Pós-operatório D4 de cirurgia ortopédica de osteossíntese femoral.
O: T 39.9°C | FC 151 BPM | Atividade ALTO | SOS não. Tendência: temperatura subiu 1.3°C, FC subiu 56 BPM nas últimas 12 leituras. Modelo: CRÍTICO (100%).
A: Hipóteses: Infecção de sítio cirúrgico (febre na janela D2-D7); Dor mal controlada (aplicar escala de Glasgow); Desidratação / hipovolemia; Risco de falha de implante / deiscência por atividade
P: Inspeção e palpação do sítio cirúrgico | Hemograma completo e PCR | Cultura com antibiograma se houver secreção | ECG e pressão arterial | Hematócrito e proteínas totais | Reavaliar plano analgésico | Radiografia de controle do implante | Validar este rascunho gerado por IA antes de registrar no prontuário
```
