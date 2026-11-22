from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

import ofxparse
import pdfplumber

from .models import Transaction

SOURCE_OFX = "ofx"
SOURCE_PDF = "pdf"


class ImportError(Exception):
    """Raised when a statement file cannot be parsed."""


OFX_HEADER = (
    b"OFXHEADER:100\n"
    b"DATA:OFXSGML\n"
    b"VERSION:102\n"
    b"SECURITY:NONE\n"
    b"ENCODING:UTF-8\n"
    b"CHARSET:NONE\n"
    b"COMPRESSION:NONE\n"
    b"OLDFILEUID:NONE\n"
    b"NEWFILEUID:NONE\n"
)


@dataclass
class ParsedTransaction:
    kind: str
    amount: Decimal
    transaction_date: date
    description: str
    fitid: str


@dataclass
class ParsedStatement:
    source: str
    account_id: str = ""
    currency: str = ""
    transactions: list[ParsedTransaction] = field(default_factory=list)


def normalize_description(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).strip().lower().split())


def idempotency_key(source: str, account_id: str, fitid: str) -> str:
    return f"{source}:{account_id}:{fitid}"


def detect_format(filename: str, content: bytes) -> str:
    name = (filename or "").lower()
    stripped = content.lstrip()
    if stripped.startswith(b"%PDF") or name.endswith(".pdf"):
        return SOURCE_PDF
    if name.endswith(".ofx") or stripped.startswith(b"OFXHEADER:") or b"<OFX>" in content:
        return SOURCE_OFX
    raise ImportError("Formato não suportado. Envie um arquivo OFX ou PDF.")


def parse_statement(filename: str, content: bytes) -> ParsedStatement:
    if detect_format(filename, content) == SOURCE_PDF:
        return parse_pdf(content)
    return parse_ofx(content)


def parse_ofx(content: bytes) -> ParsedStatement:
    content = content.lstrip()
    if not content.startswith(b"OFXHEADER:"):
        content = OFX_HEADER + content
    try:
        ofx = ofxparse.OfxParser.parse(io.BytesIO(content))
    except Exception as exc:  # noqa: BLE001
        raise ImportError("Não foi possível ler o arquivo OFX.") from exc

    account = getattr(ofx, "account", None)
    statement = getattr(account, "statement", None) if account else None
    if statement is None:
        raise ImportError("O arquivo OFX não contém extrato de conta.")

    account_id = getattr(account, "account_id", "") or ""

    transactions: list[ParsedTransaction] = []
    for item in statement.transactions:
        amount = Decimal(str(item.amount))
        kind = Transaction.Kind.INCOME if amount >= 0 else Transaction.Kind.EXPENSE

        posted = item.date.date() if hasattr(item.date, "date") else item.date

        transactions.append(
            ParsedTransaction(
                kind=kind,
                amount=abs(amount),
                transaction_date=posted,
                description=(item.memo or "").strip(),
                fitid=str(item.id or ""),
            )
        )

    if not transactions:
        raise ImportError("O extrato não contém lançamentos.")

    return ParsedStatement(
        source=SOURCE_OFX,
        account_id=account_id,
        currency=getattr(statement, "currency", "") or "",
        transactions=transactions,
    )


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------


def _parse_br_number(value: str) -> Decimal:
    normalized = value.strip().replace(".", "").replace(",", ".")
    return Decimal(normalized)


def _parse_br_date(value: str) -> date:
    return datetime.strptime(value, "%d/%m/%Y").date()


class BasePdfParser:
    bank: str = ""

    def detect(self, text: str) -> bool:
        raise NotImplementedError

    def parse(self, text: str) -> ParsedStatement:
        raise NotImplementedError


class SantanderPdfParser(BasePdfParser):
    """Parser for Santander checking-account statements (text layer)."""

    bank = "santander"

    WEEKDAY_RE = re.compile(
        r"^(?:Segunda|Terça|Quarta|Quinta|Sexta|S[áa]bado|Domingo),\s", re.IGNORECASE
    )
    VALUE_RE = re.compile(r"^(\d{2}/\d{2}/\d{4})\s+(.*?)\s*(-?)\s*R\$\s*([\d.,]+)")
    PAGE_RE = re.compile(r"^\d+/\d+$")
    ACCOUNT_RE = re.compile(r"Conta:\s*([\d.\-]+)", re.IGNORECASE)

    HEADER_EXACT = {"EXTRATO DE CONTA", "DETALHE DOS MOVIMENTOS", "Data Descrição Valor Saldo"}

    def detect(self, text: str) -> bool:
        return "EXTRATO DE CONTA" in text and "DETALHE DOS MOVIMENTOS" in text

    def _is_header(self, line: str) -> bool:
        if line in self.HEADER_EXACT:
            return True
        return line.startswith(("Agência:", "Período:", "Nome:", "Saldo inicial"))

    def parse(self, text: str) -> ParsedStatement:
        account_id = ""
        match = self.ACCOUNT_RE.search(text)
        if match:
            account_id = match.group(1)

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        transactions: list[ParsedTransaction] = []
        seen_hashes: dict[str, int] = {}

        pending_description = ""
        for index, line in enumerate(lines):
            if self.WEEKDAY_RE.match(line) or self.PAGE_RE.match(line) or self._is_header(line):
                continue

            value_match = self.VALUE_RE.match(line)
            if value_match:
                transaction_date = _parse_br_date(value_match.group(1))
                inline_description = value_match.group(2).strip()
                amount = _parse_br_number(value_match.group(4))
                if value_match.group(3):
                    amount = -amount

                if inline_description:
                    description = inline_description
                else:
                    description = pending_description
                    detail = ""
                    if index + 1 < len(lines):
                        next_line = lines[index + 1]
                        if not (
                            self.VALUE_RE.match(next_line)
                            or self.WEEKDAY_RE.match(next_line)
                            or self.PAGE_RE.match(next_line)
                            or self._is_header(next_line)
                        ):
                            detail = next_line
                    if detail.lower().startswith("periodo:"):
                        detail = ""
                    description = (
                        f"{description} - {detail}"
                        if description and detail
                        else description or detail
                    )

                kind = Transaction.Kind.INCOME if amount >= 0 else Transaction.Kind.EXPENSE

                base = hashlib.sha256(
                    f"{transaction_date}|{amount}|{description}".encode()
                ).hexdigest()[:16]
                counter = seen_hashes.get(base, 0)
                seen_hashes[base] = counter + 1
                fitid = base if counter == 0 else f"{base}-{counter}"

                transactions.append(
                    ParsedTransaction(
                        kind=kind,
                        amount=abs(amount),
                        transaction_date=transaction_date,
                        description=description,
                        fitid=fitid,
                    )
                )
                pending_description = ""
                continue

            pending_description = line

        if not transactions:
            raise ImportError("O extrato não contém lançamentos.")

        return ParsedStatement(
            source=SOURCE_PDF,
            account_id=account_id,
            transactions=transactions,
        )


PDF_PARSERS: list[BasePdfParser] = [SantanderPdfParser()]


def _extract_pdf_text(content: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as exc:  # noqa: BLE001
        raise ImportError("Não foi possível ler o arquivo PDF.") from exc


def parse_pdf(content: bytes) -> ParsedStatement:
    text = _extract_pdf_text(content)
    if not text.strip():
        raise ImportError(
            "O PDF não contém texto selecionável (extrato escaneado). Esse formato ainda não é suportado."
        )
    for parser in PDF_PARSERS:
        if parser.detect(text):
            return parser.parse(text)
    raise ImportError("Não reconhecemos o layout deste extrato em PDF.")
