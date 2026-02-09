import pytest
from pydantic import ValidationError
from uuid import uuid4

# Import schemas to test
from app.models import CardType
from app.schemas import CardCreate


# =================================================================
# Validation Tests
# =================================================================

def test_card_create_valid():
    """Test creating a valid card."""
    card = CardCreate(
        account_id=uuid4(),
        card_holder_name="John Doe",
        pin="1234",
        card_type=CardType.DEBIT,
        spending_limit=1000.00
    )
    assert card.card_holder_name == "John Doe"
    assert card.pin == "1234"
    assert card.card_type == CardType.DEBIT
    assert card.spending_limit == 1000.00


def test_card_holder_name_too_short():
    """Test that card holder name must be at least 2 characters."""
    with pytest.raises(ValidationError) as exc:
        CardCreate(
            account_id=uuid4(),
            card_holder_name="A",
            pin="1234",
            card_type=CardType.DEBIT
        )

    assert "at least 2 characters" in str(exc.value)


def test_card_holder_name_too_long():
    """Test that card holder name must not exceed 50 characters."""
    with pytest.raises(ValidationError) as exc:
        CardCreate(
            account_id=uuid4(),
            card_holder_name="A" * 51,
            pin="1234",
            card_type=CardType.DEBIT
        )

    assert "at most 50 characters" in str(exc.value)


def test_card_holder_name_invalid_characters():
    """Test that card holder name only allows letters, spaces, hyphens, periods."""
    with pytest.raises(ValidationError) as exc:
        CardCreate(
            account_id=uuid4(),
            card_holder_name="John@Doe123",
            pin="1234",
            card_type=CardType.DEBIT
        )

    assert "can only contain letters" in str(exc.value)


def test_card_holder_name_valid_with_hyphen():
    """Test that card holder name accepts hyphens."""
    card = CardCreate(
        account_id=uuid4(),
        card_holder_name="Mary-Jane Watson",
        pin="1234",
        card_type=CardType.DEBIT
    )
    assert card.card_holder_name == "Mary-Jane Watson"


def test_card_holder_name_valid_with_period():
    """Test that card holder name accepts periods."""
    card = CardCreate(
        account_id=uuid4(),
        card_holder_name="Dr. John Smith",
        pin="1234",
        card_type=CardType.DEBIT
    )
    assert card.card_holder_name == "Dr. John Smith"


def test_card_holder_name_trimmed():
    """Test that card holder name gets trimmed of whitespace."""
    card = CardCreate(
        account_id=uuid4(),
        card_holder_name="  John Doe  ",
        pin="1234",
        card_type=CardType.DEBIT
    )
    assert card.card_holder_name == "John Doe"


def test_pin_valid():
    """Test that valid 4-digit PIN is accepted."""
    card = CardCreate(
        account_id=uuid4(),
        card_holder_name="John Doe",
        pin="9876",
        card_type=CardType.DEBIT
    )
    assert card.pin == "9876"


def test_pin_too_short():
    """Test that PIN must be exactly 4 digits."""
    with pytest.raises(ValidationError) as exc:
        CardCreate(
            account_id=uuid4(),
            card_holder_name="John Doe",
            pin="123",
            card_type=CardType.DEBIT
        )

    assert "at least 4 characters" in str(exc.value) or "String should match pattern" in str(exc.value)


def test_pin_too_long():
    """Test that PIN must be exactly 4 digits."""
    with pytest.raises(ValidationError) as exc:
        CardCreate(
            account_id=uuid4(),
            card_holder_name="John Doe",
            pin="12345",
            card_type=CardType.DEBIT
        )

    assert "at most 4 characters" in str(exc.value) or "String should match pattern" in str(exc.value)


def test_pin_non_numeric():
    """Test that PIN must be numeric only."""
    with pytest.raises(ValidationError) as exc:
        CardCreate(
            account_id=uuid4(),
            card_holder_name="John Doe",
            pin="abcd",
            card_type=CardType.DEBIT
        )

    assert "String should match pattern" in str(exc.value)


def test_card_type_debit():
    """Test that DEBIT is a valid CardType."""
    card = CardCreate(
        account_id=uuid4(),
        card_holder_name="John Doe",
        pin="1234",
        card_type=CardType.DEBIT
    )
    assert card.card_type == CardType.DEBIT


def test_card_type_credit():
    """Test that CREDIT is a valid CardType."""
    card = CardCreate(
        account_id=uuid4(),
        card_holder_name="John Doe",
        pin="1234",
        card_type=CardType.CREDIT
    )
    assert card.card_type == CardType.CREDIT


def test_card_type_string_conversion():
    """Test that string 'DEBIT' gets converted to enum."""
    card = CardCreate(
        account_id=uuid4(),
        card_holder_name="John Doe",
        pin="1234",
        card_type="DEBIT"
    )
    assert card.card_type == CardType.DEBIT


def test_card_type_invalid():
    """Test that invalid card type raises ValidationError."""
    with pytest.raises(ValidationError) as exc:
        CardCreate(
            account_id=uuid4(),
            card_holder_name="John Doe",
            pin="1234",
            card_type="INVALID_TYPE"
        )

    assert "Input should be" in str(exc.value)


def test_spending_limit_valid():
    """Test that valid spending limit is accepted."""
    card = CardCreate(
        account_id=uuid4(),
        card_holder_name="John Doe",
        pin="1234",
        card_type=CardType.DEBIT,
        spending_limit=5000.00
    )
    assert card.spending_limit == 5000.00


def test_spending_limit_zero():
    """Test that spending limit must be greater than 0."""
    with pytest.raises(ValidationError) as exc:
        CardCreate(
            account_id=uuid4(),
            card_holder_name="John Doe",
            pin="1234",
            card_type=CardType.DEBIT,
            spending_limit=0
        )

    assert "greater than 0" in str(exc.value)


def test_spending_limit_negative():
    """Test that spending limit cannot be negative."""
    with pytest.raises(ValidationError) as exc:
        CardCreate(
            account_id=uuid4(),
            card_holder_name="John Doe",
            pin="1234",
            card_type=CardType.DEBIT,
            spending_limit=-100
        )

    assert "greater than 0" in str(exc.value)


def test_spending_limit_exceeds_max():
    """Test that spending limit cannot exceed 50000."""
    with pytest.raises(ValidationError) as exc:
        CardCreate(
            account_id=uuid4(),
            card_holder_name="John Doe",
            pin="1234",
            card_type=CardType.DEBIT,
            spending_limit=50001
        )

    assert "less than or equal to 50000" in str(exc.value)


def test_spending_limit_too_many_decimals():
    """Test that spending limit must have at most 2 decimal places."""
    with pytest.raises(ValidationError) as exc:
        CardCreate(
            account_id=uuid4(),
            card_holder_name="John Doe",
            pin="1234",
            card_type=CardType.DEBIT,
            spending_limit=1000.123
        )

    assert "at most 2 decimal places" in str(exc.value)


def test_spending_limit_optional():
    """Test that spending limit is optional."""
    card = CardCreate(
        account_id=uuid4(),
        card_holder_name="John Doe",
        pin="1234",
        card_type=CardType.DEBIT
    )
    assert card.spending_limit is None


# =================================================================
# Additional Boundary and Edge Case Tests
# =================================================================

def test_spending_limit_minimum_valid():
    """Test that minimum valid spending limit (0.01) is accepted."""
    card = CardCreate(
        account_id=uuid4(),
        card_holder_name="John Doe",
        pin="1234",
        card_type=CardType.DEBIT,
        spending_limit=0.01
    )
    assert card.spending_limit == 0.01


def test_spending_limit_maximum_valid():
    """Test that maximum valid spending limit (50000) is accepted."""
    card = CardCreate(
        account_id=uuid4(),
        card_holder_name="John Doe",
        pin="1234",
        card_type=CardType.DEBIT,
        spending_limit=50000.00
    )
    assert card.spending_limit == 50000.00


def test_card_holder_name_minimum_length():
    """Test that card holder name with minimum length (2 chars) is accepted."""
    card = CardCreate(
        account_id=uuid4(),
        card_holder_name="Jo",
        pin="1234",
        card_type=CardType.DEBIT
    )
    assert card.card_holder_name == "Jo"


def test_card_holder_name_maximum_length():
    """Test that card holder name with maximum length (50 chars) is accepted."""
    name = "A" * 50
    card = CardCreate(
        account_id=uuid4(),
        card_holder_name=name,
        pin="1234",
        card_type=CardType.DEBIT
    )
    assert len(card.card_holder_name) == 50


def test_pin_all_zeros():
    """Test that PIN with all zeros is valid."""
    card = CardCreate(
        account_id=uuid4(),
        card_holder_name="John Doe",
        pin="0000",
        card_type=CardType.DEBIT
    )
    assert card.pin == "0000"


def test_pin_all_nines():
    """Test that PIN with all nines is valid."""
    card = CardCreate(
        account_id=uuid4(),
        card_holder_name="John Doe",
        pin="9999",
        card_type=CardType.DEBIT
    )
    assert card.pin == "9999"


def test_card_create_all_fields():
    """Test card creation with all fields populated."""
    account_id = uuid4()
    card = CardCreate(
        account_id=account_id,
        card_holder_name="Dr. John Doe-Smith",
        pin="5678",
        card_type=CardType.CREDIT,
        spending_limit=25000.50
    )
    assert card.account_id == account_id
    assert card.card_holder_name == "Dr. John Doe-Smith"
    assert card.pin == "5678"
    assert card.card_type == CardType.CREDIT
    assert card.spending_limit == 25000.50
