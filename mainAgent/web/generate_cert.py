"""Generate a self-signed SSL certificate for local HTTPS development.

Required for getUserMedia() to work on mobile browsers (camera access
needs HTTPS on non-localhost origins).
"""

import os
import subprocess
import sys


def generate_self_signed_cert(cert_dir: str = None) -> tuple[str, str]:
    """Generate cert.pem and key.pem in the given directory.

    Returns (cert_path, key_path).
    """
    if cert_dir is None:
        cert_dir = os.path.dirname(__file__)

    cert_path = os.path.join(cert_dir, "cert.pem")
    key_path = os.path.join(cert_dir, "key.pem")

    if os.path.exists(cert_path) and os.path.exists(key_path):
        print(" SSL certificate already exists.")
        return cert_path, key_path

    print(" Generating self-signed SSL certificate...")

    # Try using Python's built-in ssl/cryptography first
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from datetime import datetime, timedelta, timezone

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "Attendance Server"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "University"),
        ])

        # Get LAN IP for SAN
        lan_ip = _get_lan_ip()

        san_names = [
            x509.DNSName("localhost"),
            x509.IPAddress(__import__("ipaddress").IPv4Address("127.0.0.1")),
        ]
        if lan_ip and lan_ip != "127.0.0.1":
            san_names.append(x509.IPAddress(__import__("ipaddress").IPv4Address(lan_ip)))

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
            .add_extension(x509.SubjectAlternativeName(san_names), critical=False)
            .sign(key, hashes.SHA256())
        )

        with open(key_path, "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ))

        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        print(f" Certificate generated: {cert_path}")
        return cert_path, key_path

    except ImportError:
        pass

    # Fallback: use openssl command
    try:
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", key_path, "-out", cert_path,
            "-days", "365", "-nodes",
            "-subj", "/CN=Attendance Server/O=University",
        ], check=True, capture_output=True)
        print(f" Certificate generated (openssl): {cert_path}")
        return cert_path, key_path
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    print(" Cannot generate SSL certificate.")
    print("   Install 'cryptography' package: pip install cryptography")
    sys.exit(1)


def _get_lan_ip() -> str:
    """Get the machine's LAN IP address."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    cert, key = generate_self_signed_cert()
    print(f"Cert: {cert}")
    print(f"Key:  {key}")
