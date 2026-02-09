import pytest
from pydantic import ValidationError
from uuid import uuid4

# Import schemas to test
from app.schemas import TransferCreate, TransferCreateByAccountNumber


# =================================================================
#  Validation Tests
# =================================================================

def test_transfer_valid():
    """Test creating a valid transfer."""
    source_id = uuid4()
    dest_id = uuid4()

    transfer = TransferCreate(
        source_account_id=source_id,
        destination_account_id=dest_id,
        amount=250.50,
        description="Rent payment"
    )
    assert transfer.source_account_id == source_id
    assert transfer.destination_account_id == dest_id
    assert transfer.amount == 250.50
    assert transfer.description == "Rent payment"


def test_transfer_amount_zero():
    """Test that transfer amount must be greater than 0."""
    with pytest.raises(ValidationError) as exc:
        TransferCreate(
            source_account_id=uuid4(),
            destination_account_id=uuid4(),
            amount=0
        )

    assert "greater than 0" in str(exc.value)


def test_transfer_amount_negative():
    """Test that transfer amount cannot be negative."""
    with pytest.raises(ValidationError) as exc:
        TransferCreate(
            source_account_id=uuid4(),
            destination_account_id=uuid4(),
            amount=-100
        )

    assert "greater than 0" in str(exc.value)


def test_transfer_amount_exceeds_max():
    """Test that transfer amount cannot exceed 1000000."""
    with pytest.raises(ValidationError) as exc:
        TransferCreate(
            source_account_id=uuid4(),
            destination_account_id=uuid4(),
            amount=1000001
        )

    assert "less than or equal to 1000000" in str(exc.value)


def test_transfer_amount_too_many_decimals():
    """Test that transfer amount must have at most 2 decimal places."""
    with pytest.raises(ValidationError) as exc:
        TransferCreate(
            source_account_id=uuid4(),
            destination_account_id=uuid4(),
            amount=500.123
        )

    assert "at most 2 decimal places" in str(exc.value)


def test_transfer_description_optional():
    """Test that description is optional."""
    transfer = TransferCreate(
        source_account_id=uuid4(),
        destination_account_id=uuid4(),
        amount=100.00
    )
    assert transfer.description is None


def test_transfer_description_too_long():
    """Test that description cannot exceed 500 characters."""
    with pytest.raises(ValidationError) as exc:
        TransferCreate(
            source_account_id=uuid4(),
            destination_account_id=uuid4(),
            amount=100.00,
            description="A" * 501
        )

    assert "at most 500 characters" in str(exc.value)


def test_transfer_same_account_rejected():
    """Test that source and destination must be different accounts."""
    same_account_id = uuid4()

    with pytest.raises(ValidationError) as exc:
        TransferCreate(
            source_account_id=same_account_id,
            destination_account_id=same_account_id,
            amount=100.00
        )

    assert "Source and destination accounts must be different" in str(exc.value)


def test_transfer_different_accounts_accepted():
    """Test that different source and destination accounts are accepted."""
    source_id = uuid4()
    dest_id = uuid4()

    transfer = TransferCreate(
        source_account_id=source_id,
        destination_account_id=dest_id,
        amount=500.00
    )
    assert transfer.source_account_id == source_id
    assert transfer.destination_account_id == dest_id
    assert transfer.source_account_id != transfer.destination_account_id


def test_transfer_minimum_amount():
    """Test that minimum valid amount (0.01) is accepted."""
    transfer = TransferCreate(
        source_account_id=uuid4(),
        destination_account_id=uuid4(),
        amount=0.01
    )
    assert transfer.amount == 0.01


def test_transfer_maximum_amount():
    """Test that maximum valid amount (1000000) is accepted."""
    transfer = TransferCreate(
        source_account_id=uuid4(),
        destination_account_id=uuid4(),
        amount=1000000.00
    )
    assert transfer.amount == 1000000.00


def test_transfer_two_decimal_places():
    """Test that amounts with 2 decimal places are accepted."""
    transfer = TransferCreate(
        source_account_id=uuid4(),
        destination_account_id=uuid4(),
        amount=123.45
    )
    assert transfer.amount == 123.45


def test_transfer_one_decimal_place():
    """Test that amounts with 1 decimal place are accepted."""
    transfer = TransferCreate(
        source_account_id=uuid4(),
        destination_account_id=uuid4(),
        amount=100.5
    )
    assert transfer.amount == 100.5


def test_transfer_no_decimal_places():
    """Test that whole number amounts are accepted."""
    transfer = TransferCreate(
        source_account_id=uuid4(),
        destination_account_id=uuid4(),
        amount=100
    )
    assert transfer.amount == 100


def test_transfer_with_all_fields():
    """Test transfer with all fields including optional description."""
    source_id = uuid4()
    dest_id = uuid4()

    transfer = TransferCreate(
        source_account_id=source_id,
        destination_account_id=dest_id,
        amount=1500.75,
        description="Monthly savings transfer"
    )
    assert transfer.source_account_id == source_id
    assert transfer.destination_account_id == dest_id
    assert transfer.amount == 1500.75
    assert transfer.description == "Monthly savings transfer"


# =================================================================
#  Transfer By Account Number Validation Tests
# =================================================================

def test_transfer_by_account_number_valid():
    """Test creating a valid transfer by account number."""
    source_id = uuid4()

    transfer = TransferCreateByAccountNumber(
        source_account_id=source_id,
        destination_account_number="123456789",
        destination_routing_number="987654321",
        amount=250.50,
        description="Rent payment"
    )
    assert transfer.source_account_id == source_id
    assert transfer.destination_account_number == "123456789"
    assert transfer.destination_routing_number == "987654321"
    assert transfer.amount == 250.50


def test_transfer_by_account_routing_number_invalid_length():
    """Test that routing number must be exactly 9 digits."""
    with pytest.raises(ValidationError) as exc:
        TransferCreateByAccountNumber(
            source_account_id=uuid4(),
            destination_account_number="123456789",
            destination_routing_number="12345",  # Only 5 digits
            amount=100.0
        )
    assert "Routing number must be 9 digits" in str(exc.value)


def test_transfer_by_account_routing_number_non_numeric():
    """Test that routing number must be all digits."""
    with pytest.raises(ValidationError) as exc:
        TransferCreateByAccountNumber(
            source_account_id=uuid4(),
            destination_account_number="123456789",
            destination_routing_number="12345678a",  # Contains letter
            amount=100.0
        )
    assert "Routing number must be 9 digits" in str(exc.value)


def test_transfer_by_account_number_too_short():
    """Test that account number must be at least 8 characters."""
    with pytest.raises(ValidationError) as exc:
        TransferCreateByAccountNumber(
            source_account_id=uuid4(),
            destination_account_number="1234567",  # Only 7 chars
            destination_routing_number="123456789",
            amount=100.0
        )
    assert "Invalid account number format" in str(exc.value)


def test_transfer_by_account_number_too_long():
    """Test that account number cannot exceed 17 characters."""
    with pytest.raises(ValidationError) as exc:
        TransferCreateByAccountNumber(
            source_account_id=uuid4(),
            destination_account_number="123456789012345678",  # 18 chars
            destination_routing_number="123456789",
            amount=100.0
        )
    assert "Invalid account number format" in str(exc.value)


def test_transfer_by_account_number_empty():
    """Test that account number cannot be empty."""
    with pytest.raises(ValidationError) as exc:
        TransferCreateByAccountNumber(
            source_account_id=uuid4(),
            destination_account_number="",
            destination_routing_number="123456789",
            amount=100.0
        )
    assert "Invalid account number format" in str(exc.value)


def test_transfer_by_account_number_amount_zero():
    """Test that amount must be greater than 0."""
    with pytest.raises(ValidationError) as exc:
        TransferCreateByAccountNumber(
            source_account_id=uuid4(),
            destination_account_number="123456789",
            destination_routing_number="123456789",
            amount=0
        )
    assert "greater than 0" in str(exc.value)


def test_transfer_by_account_number_amount_exceeds_max():
    """Test that amount cannot exceed 1000000."""
    with pytest.raises(ValidationError) as exc:
        TransferCreateByAccountNumber(
            source_account_id=uuid4(),
            destination_account_number="123456789",
            destination_routing_number="123456789",
            amount=1000001
        )
    assert "less than or equal to 1000000" in str(exc.value)


def test_transfer_by_account_number_decimal_places():
    """Test that amount must have at most 2 decimal places."""
    with pytest.raises(ValidationError) as exc:
        TransferCreateByAccountNumber(
            source_account_id=uuid4(),
            destination_account_number="123456789",
            destination_routing_number="123456789",
            amount=100.123
        )
    assert "at most 2 decimal places" in str(exc.value)


def test_transfer_by_account_number_description_optional():
    """Test that description is optional."""
    transfer = TransferCreateByAccountNumber(
        source_account_id=uuid4(),
        destination_account_number="123456789",
        destination_routing_number="123456789",
        amount=100.00
    )
    assert transfer.description is None


def test_transfer_by_account_number_description_too_long():
    """Test that description cannot exceed 500 characters."""
    with pytest.raises(ValidationError) as exc:
        TransferCreateByAccountNumber(
            source_account_id=uuid4(),
            destination_account_number="123456789",
            destination_routing_number="123456789",
            amount=100.00,
            description="A" * 501
        )
    assert "at most 500 characters" in str(exc.value)


def test_transfer_by_account_number_all_fields():
    """Test transfer by account number with all fields."""
    source_id = uuid4()

    transfer = TransferCreateByAccountNumber(
        source_account_id=source_id,
        destination_account_number="987654321",
        destination_routing_number="123456789",
        amount=5000.99,
        description="Large transfer"
    )
    assert transfer.source_account_id == source_id
    assert transfer.destination_account_number == "987654321"
    assert transfer.destination_routing_number == "123456789"
    assert transfer.amount == 5000.99
    assert transfer.description == "Large transfer"
