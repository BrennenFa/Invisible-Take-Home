import pytest
from pydantic import ValidationError
from uuid import uuid4

# Import schemas to test
from app.schemas import DepositCreate, WithdrawalCreate, CardPaymentCreate


# =================================================================
# DepositCreate Validation Tests
# =================================================================

def test_deposit_valid():
    """Test creating a valid deposit."""
    deposit = DepositCreate(
        account_id=uuid4(),
        amount=100.50,
        description="Test deposit"
    )
    assert deposit.amount == 100.50
    assert deposit.description == "Test deposit"


def test_deposit_amount_zero():
    """Test that deposit amount must be greater than 0."""
    with pytest.raises(ValidationError) as exc:
        DepositCreate(
            account_id=uuid4(),
            amount=0
        )

    assert "greater than 0" in str(exc.value)


def test_deposit_amount_negative():
    """Test that deposit amount cannot be negative."""
    with pytest.raises(ValidationError) as exc:
        DepositCreate(
            account_id=uuid4(),
            amount=-50
        )

    assert "greater than 0" in str(exc.value)


def test_deposit_amount_exceeds_max():
    """Test that deposit amount cannot exceed 100000."""
    with pytest.raises(ValidationError) as exc:
        DepositCreate(
            account_id=uuid4(),
            amount=100001
        )

    assert "less than or equal to 100000" in str(exc.value)


def test_deposit_amount_too_many_decimals():
    """Test that deposit amount must have at most 2 decimal places."""
    with pytest.raises(ValidationError) as exc:
        DepositCreate(
            account_id=uuid4(),
            amount=100.123
        )

    assert "at most 2 decimal places" in str(exc.value)


def test_deposit_description_optional():
    """Test that description is optional."""
    deposit = DepositCreate(
        account_id=uuid4(),
        amount=100.00
    )
    assert deposit.description is None


def test_deposit_description_too_long():
    """Test that description cannot exceed 500 characters."""
    with pytest.raises(ValidationError) as exc:
        DepositCreate(
            account_id=uuid4(),
            amount=100.00,
            description="A" * 501
        )

    assert "at most 500 characters" in str(exc.value)


# =================================================================
# WithdrawalCreate Validation Tests
# =================================================================

def test_withdrawal_valid():
    """Test creating a valid withdrawal."""
    withdrawal = WithdrawalCreate(
        account_id=uuid4(),
        amount=50.25,
        description="ATM withdrawal"
    )
    assert withdrawal.amount == 50.25
    assert withdrawal.description == "ATM withdrawal"


def test_withdrawal_amount_zero():
    """Test that withdrawal amount must be greater than 0."""
    with pytest.raises(ValidationError) as exc:
        WithdrawalCreate(
            account_id=uuid4(),
            amount=0
        )

    assert "greater than 0" in str(exc.value)


def test_withdrawal_amount_negative():
    """Test that withdrawal amount cannot be negative."""
    with pytest.raises(ValidationError) as exc:
        WithdrawalCreate(
            account_id=uuid4(),
            amount=-25
        )

    assert "greater than 0" in str(exc.value)


def test_withdrawal_amount_exceeds_max():
    """Test that withdrawal amount cannot exceed 50000."""
    with pytest.raises(ValidationError) as exc:
        WithdrawalCreate(
            account_id=uuid4(),
            amount=50001
        )

    assert "less than or equal to 50000" in str(exc.value)


def test_withdrawal_amount_too_many_decimals():
    """Test that withdrawal amount must have at most 2 decimal places."""
    with pytest.raises(ValidationError) as exc:
        WithdrawalCreate(
            account_id=uuid4(),
            amount=25.999
        )

    assert "at most 2 decimal places" in str(exc.value)


def test_withdrawal_description_optional():
    """Test that description is optional."""
    withdrawal = WithdrawalCreate(
        account_id=uuid4(),
        amount=100.00
    )
    assert withdrawal.description is None


def test_withdrawal_description_too_long():
    """Test that description cannot exceed 500 characters."""
    with pytest.raises(ValidationError) as exc:
        WithdrawalCreate(
            account_id=uuid4(),
            amount=100.00,
            description="A" * 501
        )

    assert "at most 500 characters" in str(exc.value)


# =================================================================
# CardPaymentCreate Validation Tests
# =================================================================

def test_card_payment_valid():
    """Test creating a valid card payment."""
    payment = CardPaymentCreate(
        card_id=uuid4(),
        amount=25.99,
        description="Coffee shop",
        merchant="Starbucks"
    )
    assert payment.amount == 25.99
    assert payment.description == "Coffee shop"
    assert payment.merchant == "Starbucks"


def test_card_payment_amount_zero():
    """Test that card payment amount must be greater than 0."""
    with pytest.raises(ValidationError) as exc:
        CardPaymentCreate(
            card_id=uuid4(),
            amount=0
        )

    assert "greater than 0" in str(exc.value)


def test_card_payment_amount_negative():
    """Test that card payment amount cannot be negative."""
    with pytest.raises(ValidationError) as exc:
        CardPaymentCreate(
            card_id=uuid4(),
            amount=-10
        )

    assert "greater than 0" in str(exc.value)


def test_card_payment_amount_exceeds_max():
    """Test that card payment amount cannot exceed 10000."""
    with pytest.raises(ValidationError) as exc:
        CardPaymentCreate(
            card_id=uuid4(),
            amount=10001
        )

    assert "less than or equal to 10000" in str(exc.value)


def test_card_payment_amount_too_many_decimals():
    """Test that card payment amount must have at most 2 decimal places."""
    with pytest.raises(ValidationError) as exc:
        CardPaymentCreate(
            card_id=uuid4(),
            amount=99.999
        )

    assert "at most 2 decimal places" in str(exc.value)


def test_card_payment_description_optional():
    """Test that description is optional."""
    payment = CardPaymentCreate(
        card_id=uuid4(),
        amount=50.00
    )
    assert payment.description is None


def test_card_payment_description_too_long():
    """Test that description cannot exceed 500 characters."""
    with pytest.raises(ValidationError) as exc:
        CardPaymentCreate(
            card_id=uuid4(),
            amount=50.00,
            description="A" * 501
        )

    assert "at most 500 characters" in str(exc.value)


def test_card_payment_merchant_optional():
    """Test that merchant is optional."""
    payment = CardPaymentCreate(
        card_id=uuid4(),
        amount=50.00
    )
    assert payment.merchant is None


def test_card_payment_merchant_too_long():
    """Test that merchant cannot exceed 100 characters."""
    with pytest.raises(ValidationError) as exc:
        CardPaymentCreate(
            card_id=uuid4(),
            amount=50.00,
            merchant="A" * 101
        )

    assert "at most 100 characters" in str(exc.value)


def test_card_payment_all_fields():
    """Test card payment with all optional fields."""
    payment = CardPaymentCreate(
        card_id=uuid4(),
        amount=75.50,
        description="Grocery shopping",
        merchant="Whole Foods"
    )
    assert payment.amount == 75.50
    assert payment.description == "Grocery shopping"
    assert payment.merchant == "Whole Foods"
