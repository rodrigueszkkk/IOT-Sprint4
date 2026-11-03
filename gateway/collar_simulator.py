"""Simulador de frota de coleiras: envia leituras periódicas para a API, imitando o firmware.

Cada pet segue um roteiro clínico (recuperação normal, febre que evolui, agitação pós-operatória...)
com ruído de sensor, para demonstrar o pipeline completo em tempo real no painel.

Uso:
  python gateway/collar_simulator.py                         # 3 coleiras, roteiro padrão
  python gateway/collar_simulator.py --interval 2 --steps 30
"""
import argparse
import json
import random
import time
import urllib.request

# device_id -> roteiro: lista de (passo inicial, temperatura alvo, FC alvo, movimento, sos)
SCRIPTS = {
    "CLYVO-COLLAR-01": [(0, 38.6, 96, "REPOUSO", False), (8, 39.3, 118, "MODERADO", False),
                        (14, 39.9, 150, "ALTO", False), (20, 38.9, 104, "REPOUSO", False)],
    "CLYVO-COLLAR-02": [(0, 38.4, 165, "REPOUSO", False), (10, 37.2, 125, "REPOUSO", False),
                        (18, 38.3, 160, "REPOUSO", False)],
    "CLYVO-COLLAR-03": [(0, 38.4, 112, "REPOUSO", False), (22, 38.6, 128, "MODERADO", True),
                        (23, 38.5, 118, "REPOUSO", False)],
}


def state_at(script, step):
    current = script[0]
    for entry in script:
        if step >= entry[0]:
            current = entry
    return current


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--interval", type=float, default=3.0, help="segundos entre leituras (firmware: 3s)")
    parser.add_argument("--steps", type=int, default=26)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    rnd = random.Random(args.seed)

    for step in range(args.steps):
        for device, script in SCRIPTS.items():
            _, temp, hr, movement, sos = state_at(script, step)
            payload = {"deviceId": device, "temperature": round(temp + rnd.gauss(0, 0.08), 1),
                       "heartRateBpm": int(hr + rnd.gauss(0, 3)), "movementLevel": movement, "emergencyPressed": sos}
            req = urllib.request.Request(f"{args.api}/api/telemetry", data=json.dumps(payload).encode("utf-8"),
                                         headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=120) as res:
                result = json.loads(res.read().decode("utf-8"))
            flag = f"  -> ALERTA #{result['alert']['id']}" if result.get("alert") else ""
            print(f"[{step:02d}] {device} {payload['temperature']}°C {payload['heartRateBpm']} BPM {movement:<8} "
                  f"=> {result['risk']['risk_label']}{flag}")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
