from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

import ofxparse

from .models import Transaction


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
    account_id: str = ""
    currency: str = ""
    transactions: list[ParsedTransaction] = field(default_factory=list)


def normalize_description(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).strip().lower().split())


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
        if amount >= 0:
            kind = Transaction.Kind.INCOME
        else:
            kind = Transaction.Kind.EXPENSE

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
        account_id=account_id,
        currency=getattr(statement, "currency", "") or "",
        transactions=transactions,
    )


def idempotency_key(account_id: str, fitid: str) -> str:
    return f"ofx:{account_id}:{fitid}"
