import pytest

from tse_valuator.macro.country_risk_client import (
    CountryNotFoundError,
    fetch_country_risk_premium,
)


def test_iran_final_erp_and_crp_are_consistent_with_mature_premium():
    result = fetch_country_risk_premium("Iran")
    final_erp = result["Final ERP"]
    crp = result["CRP"]
    mature_market_premium = 0.0423  # from the dataset's own FAQ sheet, Jan 2026 update
    assert final_erp == pytest.approx(mature_market_premium + crp, abs=0.001)


def test_unknown_country_raises():
    with pytest.raises(CountryNotFoundError):
        fetch_country_risk_premium("Not A Real Country Name")