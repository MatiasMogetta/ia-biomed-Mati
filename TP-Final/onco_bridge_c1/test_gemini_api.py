"""Comprueba la configuración de Gemini sin enviar información clínica."""
from __future__ import annotations

import os
import sys


def main() -> int:
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("ERROR: Faltan dependencias. Ejecutá: pip install -r requirements.txt")
        return 1
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    print(api_key)
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    if not api_key:
        print("ERROR: No se encontró GEMINI_API_KEY en el archivo .env.")
        return 1

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents="Respondé exactamente con: GEMINI_OK",
        )
        if response.text and "GEMINI_OK" in response.text:
            print(f"OK: Gemini respondió correctamente usando el modelo '{model}'.")
            return 0
        print("ERROR: Gemini respondió, pero no devolvió el texto esperado.")
        return 1
    except Exception as error:
        message = str(error)
        print(f"ERROR al conectar con Gemini: {message}")
        if "leaked" in message.lower() or "permission_denied" in message.lower():
            print("La API key fue bloqueada o marcada como comprometida. Creá una nueva key en Google AI Studio y actualizá .env.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
