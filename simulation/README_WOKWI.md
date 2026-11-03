# Simulação IoT — Wokwi (CLYVO VET Smart Collar)

Firmware e circuito do nó IoT da coleira inteligente. Na Sprint 4 a coleira deixou de ser um protótipo isolado: o JSON impresso no Monitor Serial é enviado para a API da plataforma (`POST /api/telemetry`) pela ponte `gateway/serial_bridge.py`, onde o modelo de Machine Learning e a IA Generativa processam cada leitura.

## 🔌 Componentes e pinos

| Componente | Pino | Função |
| :--- | :--- | :--- |
| Arduino UNO | — | Microcontrolador de borda (edge computing) |
| Potenciômetro "Temp" | A1 | Temperatura corporal (35,0 a 42,0 °C) |
| Potenciômetro "Pulso" | A0 | Frequência cardíaca (50 a 180 BPM) |
| Botão azul "Movimento" | D3 (pull-up) | Acelerômetro: atividade durante o repouso pós-cirúrgico |
| Botão vermelho "SOS Tutor" | D7 (pull-up) | Botão de pânico do tutor |
| LED verde / amarelo / vermelho | D10 / D11 / D12 | Estável / Atenção / Crítico |
| Buzzer | D13 | Alarme sonoro de emergência |

## 🚀 Executar no Wokwi

1. Acesse <https://wokwi.com/projects/475084250105444353> e clique em **Play**.
   - Para usar o firmware atualizado da Sprint 4 (que inclui o `deviceId` no JSON), cole o conteúdo de [`smart_collar.ino`](smart_collar.ino) na aba **sketch.ino**. A API também aceita o JSON antigo, sem `deviceId`, identificando o pet pelo `petId`.
2. Alternativa manual: <https://wokwi.com/projects/new/arduino-uno>, colar `smart_collar.ino` e [`diagram.json`](diagram.json) e clicar em **Play** (sem bibliotecas externas).

## 🔗 Ligar o Wokwi à API (Sprint 4)

Com a API rodando (`python run.py`):

- **Wokwi para VS Code:** ative o servidor RFC2217 da extensão e rode
  `python gateway/serial_bridge.py --port rfc2217://localhost:4000`
- **Wokwi no navegador:** copie as linhas JSON do Monitor Serial para `leituras.txt` e rode
  `python gateway/serial_bridge.py --stdin < leituras.txt` (no PowerShell: `Get-Content leituras.txt | python gateway/serial_bridge.py --stdin`)
- **Arduino físico:** `python gateway/serial_bridge.py --port COM3` (ou `/dev/ttyUSB0`)

Exemplo de linha enviada pelo firmware:
```json
{"deviceId":"CLYVO-COLLAR-01","petId":1,"petName":"Thor","temperatura":39.8,"bpm":152,"movimento":true,"sos":false,"status":"CRITICO","riskScore":6}
```

## 🧪 Cenários para testar ao vivo

| Cenário | Como reproduzir | Borda (LEDs) | Nuvem (modelo + IA) |
| :--- | :--- | :--- | :--- |
| Estável | Temp ≈ 38,5 °C, pulso ≈ 95 BPM, botões soltos | LED verde | ESTÁVEL, sem alerta |
| Atenção | Temp ≈ 39,3 °C ou pulso ≈ 135 BPM | LED amarelo | ATENÇÃO, mensagem de observação ao tutor |
| Crítico | Temp ≥ 39,8 °C + segurar o botão Movimento | LED vermelho + buzzer | CRÍTICO, alerta WhatsApp + rascunho SOAP |
| SOS | Pressionar o botão vermelho | LED vermelho + buzzer | CRÍTICO por regra de segurança, P1 na triagem |

A borda usa regras simples para reagir em milissegundos mesmo sem rede; a nuvem refina a decisão com o modelo de ML (que considera espécie, idade e dias de pós-operatório) e gera a comunicação com IA Generativa.
