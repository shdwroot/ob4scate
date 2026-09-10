"""Default sensitive-data detector catalog for the policy engine."""

from typing import TypedDict


class SensitiveDataDefinition(TypedDict):
    name: str
    category: str
    description: str
    example: str
    pattern: str


DEFAULT_SENSITIVE_DATA: tuple[SensitiveDataDefinition, ...] = (
    {
        "name": "PRIVATE_KEY",
        "category": "Credentials",
        "description": "PEM-encoded private keys",
        "example": "-----BEGIN PRIVATE KEY-----\nabc123secretmaterial\n-----END PRIVATE KEY-----",
        "pattern": (
            r"-----BEGIN(?: [A-Z]+)? PRIVATE KEY-----[\s\S]{8,}?"
            r"-----END(?: [A-Z]+)? PRIVATE KEY-----"
        ),
    },
    {
        "name": "BEARER_TOKEN",
        "category": "Credentials",
        "description": "Bearer authorization credentials",
        "example": "Bearer mF_9.B5f-4.1JqMverySecretTokenValue",
        "pattern": r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}\b",
    },
    {
        "name": "JWT",
        "category": "Credentials",
        "description": "JSON Web Tokens",
        "example": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signatureValue123",
        "pattern": r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b",
    },
    {
        "name": "API_SECRET",
        "category": "Credentials",
        "description": "Labeled API keys, access tokens, and client secrets",
        "example": "API key: sk_live_51VerySecretValue12345",
        "pattern": (
            r"\b(?:api[_ -]?key|access[_ -]?token|client[_ -]?secret|secret[_ -]?key)"
            r"\s*[:=]\s*[A-Za-z0-9._~+/=-]{16,}"
        ),
    },
    {
        "name": "PASSWORD_OR_PIN",
        "category": "Credentials",
        "description": "Labeled passwords, passcodes, and PINs",
        "example": "password: CorrectHorseBatteryStaple!",
        "pattern": r"\b(?:password|passcode|passphrase|pin)\s*[:=]\s*[^\s,;]{4,}",
    },
    {
        "name": "ZA_ID_NUMBER",
        "category": "Government IDs",
        "description": "South African 13-digit identity numbers",
        "example": "South African ID: 9001015009087",
        "pattern": r"\b(?:south african\s+)?(?:id|identity)(?:\s+number)?\s*[:=#-]?\s*\d{13}\b",
    },
    {
        "name": "US_SSN",
        "category": "Government IDs",
        "description": "United States Social Security numbers",
        "example": "SSN: 123-45-6789",
        "pattern": (
            r"\b(?:ssn\s*[:=#-]?\s*)?(?!000|666|9\d{2})\d{3}[- ]?"
            r"(?!00)\d{2}[- ]?(?!0000)\d{4}\b"
        ),
    },
    {
        "name": "NATIONAL_IDENTIFIER",
        "category": "Government IDs",
        "description": "Context-labeled national or citizen identifiers",
        "example": "National ID: AB-80442199",
        "pattern": (
            r"\b(?:national|citizen|identity)\s+(?:id|number)\s*[:=#-]?\s*"
            r"[A-Z0-9][A-Z0-9-]{5,24}\b"
        ),
    },
    {
        "name": "PASSPORT_NUMBER",
        "category": "Government IDs",
        "description": "Context-labeled passport numbers",
        "example": "Passport number: A12345678",
        "pattern": r"\bpassport(?:\s+(?:number|no\.?))?\s*[:=#-]?\s*[A-Z0-9]{6,12}\b",
    },
    {
        "name": "DRIVER_LICENSE",
        "category": "Government IDs",
        "description": "Context-labeled driving licence numbers",
        "example": "Driver license: DL-90884421",
        "pattern": (
            r"\b(?:driver'?s?\s+licen[cs]e|driving\s+licen[cs]e)"
            r"\s*[:=#-]?\s*[A-Z0-9-]{5,24}\b"
        ),
    },
    {
        "name": "TAX_IDENTIFIER",
        "category": "Government IDs",
        "description": "Context-labeled tax identifiers",
        "example": "Tax ID: TX-88442190",
        "pattern": r"\b(?:tax|taxpayer|vat)\s+(?:id|number|code)\s*[:=#-]?\s*[A-Z0-9-]{5,24}\b",
    },
    {
        "name": "IBAN",
        "category": "Financial",
        "description": "International bank account numbers",
        "example": "IBAN: GB82 WEST 1234 5698 7654 32",
        "pattern": r"\b(?:IBAN\s*[:=#-]?\s*)?[A-Z]{2}\d{2}(?: ?[A-Z0-9]){11,30}\b",
    },
    {
        "name": "CREDIT_CARD",
        "category": "Financial",
        "description": "Payment card numbers from 13 to 19 digits",
        "example": "4111 1111 1111 1111",
        "pattern": r"(?<![A-Za-z0-9])(?:\d[ -]?){12,18}\d(?![A-Za-z0-9])",
    },
    {
        "name": "BANK_ACCOUNT",
        "category": "Financial",
        "description": "Context-labeled bank account and routing numbers",
        "example": "Bank account: 123456789012",
        "pattern": (
            r"\b(?:bank\s+account|account\s+number|routing\s+number)"
            r"\s*[:=#-]?\s*[A-Z0-9-]{6,24}\b"
        ),
    },
    {
        "name": "CRYPTO_WALLET",
        "category": "Financial",
        "description": "Bitcoin wallet addresses",
        "example": "1BoatSLRHtKNngkdXEeobR76b53LETtpyT",
        "pattern": r"\b(?:bc1[a-zA-HJ-NP-Z0-9]{25,62}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b",
    },
    {
        "name": "MEDICAL_RECORD",
        "category": "Health and insurance",
        "description": "Patient, medical-record, and medical-license identifiers",
        "example": "Medical record: MRN-884421",
        "pattern": (
            r"\b(?:patient|medical\s+record|mrn|medical\s+licen[cs]e)"
            r"\s*(?:id|number|no\.?)?\s*[:=#-]?\s*[A-Z0-9-]{5,24}\b"
        ),
    },
    {
        "name": "INSURANCE_IDENTIFIER",
        "category": "Health and insurance",
        "description": "Insurance policy, member, and beneficiary identifiers",
        "example": "Policy number: MED88442190",
        "pattern": (
            r"\b(?:insurance\s+)?(?:policy|member|beneficiary)\s+"
            r"(?:id|number|no\.?)\s*[:=#-]?\s*[A-Z0-9-]{5,24}\b"
        ),
    },
    {
        "name": "HEALTH_DATA",
        "category": "Health and insurance",
        "description": "Labeled diagnoses, medications, allergies, and genetic data",
        "example": "Diagnosis: hypertension",
        "pattern": (
            r"\b(?:diagnosis|medical\s+condition|medication|prescription|allergy|"
            r"blood\s+type|genetic\s+(?:marker|data)|dna\s+profile)"
            r"\s*[:=]\s*[^,;\n]{2,100}"
        ),
    },
    {
        "name": "MEDICAL_CONDITION",
        "category": "Health and insurance",
        "description": "Common standalone high-sensitivity medical-condition terms",
        "example": "Diabetes",
        "pattern": r"\b(?:HIV|AIDS|diabetes|cancer|hypertension)\b",
    },
    {
        "name": "BIOMETRIC_DATA",
        "category": "Health and insurance",
        "description": "Labeled biometric templates and measurements",
        "example": "Fingerprint template: AF91B28C77D0",
        "pattern": (
            r"\b(?:fingerprint|face|facial|voiceprint|retina|iris|biometric)"
            r"(?:\s+(?:template|data|id))?\s*[:=]\s*[A-Z0-9+/=-]{8,120}\b"
        ),
    },
    {
        "name": "PERSON_NAME",
        "category": "Identity and contact",
        "description": "Context-labeled full names when NLP is unavailable",
        "example": "Customer name: Jane Doe",
        "pattern": (
            r"\b(?:full[ \t]+name|customer[ \t]+name|patient[ \t]+name|name)"
            r"[ \t]*[:=][ \t]*[A-Z][A-Za-z'’-]+"
            r"(?:[ \t]+[A-Z][A-Za-z'’-]+){1,4}\b"
        ),
    },
    {
        "name": "DATE_OF_BIRTH",
        "category": "Identity and contact",
        "description": "Context-labeled dates of birth",
        "example": "Date of birth: 1990-04-12",
        "pattern": (
            r"\b(?:date\s+of\s+birth|birth\s+date|dob)\s*[:=]\s*"
            r"(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b"
        ),
    },
    {
        "name": "POSTAL_ADDRESS",
        "category": "Identity and contact",
        "description": "Context-labeled street and postal addresses",
        "example": "Home address: 12 Long Street, Cape Town, 8001",
        "pattern": (
            r"\b(?:home|postal|street|residential|billing|shipping)\s+address"
            r"\s*[:=]\s*[^\n;]{5,160}"
        ),
    },
    {
        "name": "USER_ACCOUNT",
        "category": "Identity and contact",
        "description": "Context-labeled usernames and account IDs",
        "example": "Username: jane.doe_90",
        "pattern": (
            r"\b(?:username|user\s+id|account\s+id|customer\s+id)"
            r"\s*[:=#-]?\s*[A-Za-z0-9_.@-]{3,64}\b"
        ),
    },
    {
        "name": "IPV4_ADDRESS",
        "category": "Network and device",
        "description": "IPv4 network addresses",
        "example": "192.168.10.24",
        "pattern": r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d{1,2})\.){3}(?:25[0-5]|2[0-4]\d|1?\d{1,2})\b",
    },
    {
        "name": "MAC_ADDRESS",
        "category": "Network and device",
        "description": "Network-interface hardware addresses",
        "example": "00:1A:2B:3C:4D:5E",
        "pattern": r"\b(?:[0-9A-F]{2}[:-]){5}[0-9A-F]{2}\b",
    },
    {
        "name": "IPV6_ADDRESS",
        "category": "Network and device",
        "description": "Expanded and commonly compressed IPv6 addresses",
        "example": "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
        "pattern": (
            r"(?<![0-9A-Fa-f:])(?:(?:[0-9A-Fa-f]{1,4}:){2,7}[0-9A-Fa-f]{1,4}|"
            r"(?:[0-9A-Fa-f]{1,4}:){1,7}:[0-9A-Fa-f]{0,4})(?![0-9A-Fa-f:])"
        ),
    },
    {
        "name": "DEVICE_IDENTIFIER",
        "category": "Network and device",
        "description": "Context-labeled IMEI, device, and advertising identifiers",
        "example": "Device ID: 550e8400-e29b-41d4-a716-446655440000",
        "pattern": r"\b(?:imei|device\s+id|advertising\s+id)\s*[:=#-]?\s*[A-F0-9][A-F0-9-]{7,40}\b",
    },
    {
        "name": "GPS_COORDINATES",
        "category": "Network and device",
        "description": "Context-labeled latitude and longitude pairs",
        "example": "GPS coordinates: -33.9249, 18.4241",
        "pattern": (
            r"(?<!\w)(?:gps|coordinates|location)\s*[:=]\s*"
            r"-?(?:[0-8]?\d(?:\.\d+)?|90(?:\.0+)?),\s*"
            r"-?(?:1[0-7]\d(?:\.\d+)?|(?:\d?\d)(?:\.\d+)?|180(?:\.0+)?)"
        ),
    },
    {
        "name": "URL",
        "category": "Network and device",
        "description": "Web addresses which may contain identifying paths or queries",
        "example": "https://portal.example/users/jane?token=private",
        "pattern": r"\bhttps?://[^\s<>\"']+",
    },
    {
        "name": "VEHICLE_REGISTRATION",
        "category": "Network and device",
        "description": "Context-labeled vehicle registration or VIN values",
        "example": "Vehicle registration: CA 123-456",
        "pattern": (
            r"\b(?:vehicle\s+(?:registration|reg)|licen[cs]e\s+plate|vin)"
            r"\s*[:=#-]?\s*[A-Z0-9][A-Z0-9 -]{4,20}\b"
        ),
    },
)


CORE_DETECTORS: tuple[dict[str, str], ...] = (
    {
        "name": "EMAIL_ADDRESS",
        "category": "Identity and contact",
        "description": "Email mailbox addresses",
        "example": "jane.doe@example.com",
    },
    {
        "name": "PHONE_NUMBER",
        "category": "Identity and contact",
        "description": "International and local phone numbers",
        "example": "+27 82 123 4567",
    },
    {
        "name": "PERSON_AND_LOCATION_NLP",
        "category": "Identity and contact",
        "description": "Free-form person names and locations when the spaCy model is installed",
        "example": "Jane Doe lives in Cape Town",
    },
)


DEFAULT_EXAMPLE_TEXT = """Customer name: Jane Doe
Email: jane.doe@example.com
Phone: +27 82 123 4567
Home address: 12 Long Street, Cape Town, 8001
Date of birth: 1990-04-12
South African ID: 9001015009087
Passport number: A12345678
Credit card: 4111 1111 1111 1111
IBAN: GB82 WEST 1234 5698 7654 32
Policy number: MED88442190
Medical record: MRN-884421
Diagnosis: hypertension
IP address: 192.168.10.24
Device ID: 550e8400-e29b-41d4-a716-446655440000
GPS coordinates: -33.9249, 18.4241
API key: sk_live_51VerySecretValue12345
Password: CorrectHorseBatteryStaple!
Profile: https://portal.example/users/jane?token=private"""
