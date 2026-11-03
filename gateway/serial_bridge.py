"""Ponte IoT -> nuvem: lê as linhas JSON emitidas pela coleira (Arduino físico, Wokwi CLI/VS Code ou
texto colado do Monitor Serial do Wokwi) e envia cada leitura para POST /api/telemetry.

Exemplos:
  # Arduino físico ou Wokwi para VS Code (porta serial / RFC2217)
  python gateway/serial_bridge.py --port COM3
  python gateway/serial_bridge.py --port rfc2217://localhost:4000

  # Colar/encaminhar a saída do Monitor Serial do Wokwi (uma linha JSON por leitura)
  python gateway/serial_bridge.py --stdin < leituras.txt
"""
import argparse
import json
import sys
import urllib.error
import urllib.request


def post(api: str, payload: dict) -> dict:
    req = urllib.request.Request(f"{api}/api/telemetry", data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as res:
        return json.loads(res.read().decode("utf-8"))


def handle_line(api: str, line: str) -> None:
    line = line.strip()
    if not line.startswith("{"):
        return  # ignora o banner e mensagens de log do firmware
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        print(f"[ignorado] linha não é JSON válido: {line[:80]}")
        return
    try:
        result = post(api, payload)
    except urllib.error.HTTPError as exc:
        print(f"[erro {exc.code}] {exc.read().decode('utf-8', 'replace')[:200]}")
        return
    risk = result["risk"]
    status = f"{result['pet_name']}: {risk['risk_label']} ({risk['confidence'] * 100:.0f}%)"
    if result.get("alert"):
        status += f" -> ALERTA #{result['alert']['id']} gerado por {result['alert']['llm_mode']}"
    print(status)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--port", help="porta serial (COM3, /dev/ttyUSB0, rfc2217://localhost:4000)")
    group.add_argument("--stdin", action="store_true", help="lê as linhas JSON da entrada padrão")
    parser.add_argument("--baud", type=int, default=9600)
    args = parser.parse_args()

    if args.stdin:
        for line in sys.stdin:
            handle_line(args.api, line)
        return

    import serial  # pyserial (opcional, só para porta serial)
    with serial.serial_for_url(args.port, baudrate=args.baud, timeout=5) as ser:
        print(f"Lendo {args.port} a {args.baud} baud. Ctrl+C para sair.")
        while True:
            raw = ser.readline().decode("utf-8", "replace")
            if raw:
                handle_line(args.api, raw)


if __name__ == "__main__":
    main()
