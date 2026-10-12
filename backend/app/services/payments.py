"""Payment provider abstraction. `manual_upi` is live; `razorpay` is a documented stub."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.parse import quote, urlencode

from app.models import Order, Society


@dataclass
class PaymentInstructions:
    provider: str
    amount: int
    currency: str = "INR"
    upi_id: str | None = None
    payee_name: str | None = None
    note: str | None = None
    upi_uri: str | None = None
    requires_proof: bool = True  # screenshot / UTR must be submitted for manual review


class PaymentProvider(ABC):
    name: str
    enabled: bool = True
    requires_manual_review: bool = True

    @abstractmethod
    def instructions(self, order: Order, society: Society) -> PaymentInstructions: ...


class ManualUpiProvider(PaymentProvider):
    """Member pays the society's UPI ID directly, uploads screenshot + UTR, an admin reviews."""

    name = "manual_upi"

    def instructions(self, order: Order, society: Society) -> PaymentInstructions:
        note = f"Order {order.ref_code}"
        uri = None
        if society.upi_id:
            q = urlencode(
                {"pa": society.upi_id, "pn": society.upi_name or society.name, "am": f"{order.total_amount:.2f}",
                 "cu": "INR", "tn": note},
                quote_via=quote,
            )
            uri = f"upi://pay?{q}"
        return PaymentInstructions(
            provider=self.name,
            amount=order.total_amount,
            upi_id=society.upi_id,
            payee_name=society.upi_name or society.name,
            note=note,
            upi_uri=uri,
        )


class RazorpayProvider(PaymentProvider):
    """Not wired. TODO:
    - Create a Razorpay Order per Order (amount in paise) and return `order_id` to the app's checkout.
    - Verify the payment signature server-side and via webhook (`payment.captured`), auto-approve the order.
    - Route / split payouts: use Razorpay Route linked accounts so each society settles to its own bank
      account (onboard societies as linked accounts, set `transfers` on the Razorpay order, hold settlements
      until the event ends if desired, and take a platform fee).
    - Refunds on reject/cancel; reconcile via payouts report.
    """

    name = "razorpay"
    enabled = False
    requires_manual_review = False

    def instructions(self, order: Order, society: Society) -> PaymentInstructions:  # pragma: no cover
        raise NotImplementedError("Razorpay provider is not wired yet")


PROVIDERS: dict[str, PaymentProvider] = {p.name: p for p in (ManualUpiProvider(), RazorpayProvider())}


def get_provider(name: str) -> PaymentProvider:
    provider = PROVIDERS.get(name)
    if provider is None or not provider.enabled:
        raise ValueError(f"payment provider '{name}' is not available")
    return provider
