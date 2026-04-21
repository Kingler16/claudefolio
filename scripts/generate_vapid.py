"""Generiert VAPID-Keys für Velora Web-Push.

Ausgabe ist direkt als ENV-Block formatiert — einfach in .env umleiten:

    python scripts/generate_vapid.py >> .env

Keys werden nirgends persistiert — nur stdout.
"""

import base64

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid01


def main() -> None:
    v = Vapid01()
    v.generate_keys()

    # Private Key als PEM mit escaped newlines (systemd EnvironmentFile akzeptiert
    # keine echten \n — \n als Literal-Escape ist korrekt für FastAPI/os.getenv,
    # py-vapid erwartet "\n" -> "\\n" dann später wieder zurück zu "\n")
    priv_pem = v.private_pem().decode()
    priv_escaped = priv_pem.replace("\n", "\\n").strip("\\n")

    # Public Key als URL-safe Base64 (uncompressed EC point, 65 bytes)
    raw = v.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    pub = base64.urlsafe_b64encode(raw).decode().rstrip("=")

    print(f'VAPID_PRIVATE_KEY="{priv_escaped}"')
    print(f"VAPID_PUBLIC_KEY={pub}")
    print("VAPID_SUBJECT=mailto:max.lechner06@gmail.com")


if __name__ == "__main__":
    main()
