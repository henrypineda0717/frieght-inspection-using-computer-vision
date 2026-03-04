import re

import re
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, CheckConstraint
from sqlalchemy.orm import relationship


def compute_check_digit(owner_category: str, serial_number: str) -> int:
    """
    Compute the ISO 6346 check digit for a container.
    owner_category : first 4 characters (owner code + category, e.g., 'HLXU')
    serial_number  : 6-digit string
    Returns check digit 0-9.
    """
    if len(owner_category) != 4 or len(serial_number) != 6:
        raise ValueError("owner_category must be 4 chars, serial_number 6 digits")
    
    # Mapping letters to numbers (A=10, B=12, ..., Z=38, skipping 11,22,33)
    def char_value(ch: str) -> int:
        if ch.isdigit():
            return int(ch)
        # Letter mapping per ISO 6346
        mapping = {
            'A':10, 'B':12, 'C':13, 'D':14, 'E':15, 'F':16, 'G':17, 'H':18, 'I':19,
            'J':20, 'K':21, 'L':23, 'M':24, 'N':25, 'O':26, 'P':27, 'Q':28, 'R':29,
            'S':30, 'T':31, 'U':32, 'V':34, 'W':35, 'X':36, 'Y':37, 'Z':38
        }
        return mapping.get(ch.upper(), 0)
    
    combined = owner_category + serial_number
    total = 0
    for i, ch in enumerate(combined):
        value = char_value(ch)
        total += value * (2 ** i)  # 2^i weighting
    remainder = total % 11
    return remainder if remainder < 10 else 0

import re

def parse_ocr_results(ocr_text_list):
    four_letter_tokens = []
    six_digit_tokens = []
    iso_type = None

    # First pass: gather all potential container ID parts
    for line in ocr_text_list:
        line_clean = re.sub(r'[^A-Za-z0-9 ]', '', line).upper()
        tokens = line_clean.split()
        for token in tokens:
            if re.fullmatch(r'[A-Z]{4}', token):
                four_letter_tokens.append(token)
            elif re.fullmatch(r'\d{6}', token):
                six_digit_tokens.append(token)

    # Second pass: look for ISO type (stops at first match)
    for line in ocr_text_list:
        line_clean = re.sub(r'[^A-Za-z0-9 ]', '', line).upper()
        tokens = line_clean.split()
        for token in tokens:
            if re.fullmatch(r'\d{2}[A-Z]\d', token) or re.fullmatch(r'\d{4}', token):
                iso_type = token
                break
        if iso_type:
            break

    # Build container ID if we have both parts
    container_id = None
    if four_letter_tokens and six_digit_tokens:
        owner_category = four_letter_tokens[0]   # first 4‑letter token found
        serial = six_digit_tokens[0]             # first 6‑digit token found
        try:
            check = compute_check_digit(owner_category, serial)
            container_id = f"{owner_category}{serial}{check}"
        except ValueError:
            pass   # fallback: container_id stays None

    return container_id, iso_type


class Container():
    """Container entity following ISO 6346 standard"""
    __tablename__ = "containers"

    id = Column(String(11), primary_key=True)  # Full Container ID (e.g., MSCU1234567)
    owner_code = Column(String(3), nullable=True)   # First 3 letters
    category = Column(String(1), nullable=True)     # 4th letter: U=freight, J=detachable, Z=trailer
    serial_number = Column(String(6), nullable=True) # 6-digit serial
    check_digit = Column(Integer, nullable=True)     # ISO 6346 check digit (0-9)
    iso_type = Column(String, nullable=True)         # Container type code (e.g., "45R1")
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    detection_count = Column(Integer, default=0, nullable=False)

    # Relationships (assuming Inspection and Detection models exist)
    inspections = relationship("Inspection", back_populates="container", cascade="all, delete-orphan")
    detections = relationship("Detection", back_populates="container")

    __table_args__ = (
        CheckConstraint("length(id) = 11", name="check_id_length"),
    )

    def __repr__(self):
        return f"<Container(id='{self.id}', owner_code='{self.owner_code}', detection_count={self.detection_count})>"


ocr_texts = ['HLXU', '310227', 'Hapag Lloyd', '2261', '213 01111', 'CUI', '111.1']
container_id, iso_type = parse_ocr_results(ocr_texts)
print(container_id, iso_type)   