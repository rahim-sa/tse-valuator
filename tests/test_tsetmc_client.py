from tse_valuator.macro.tsetmc_client import get_current_market_data


def test_shapadis_returns_real_current_data():
    data = get_current_market_data("شپدیس")
    assert data["shares_outstanding"] > 200_000_000_000  # confirmed real scale post capital-increase
    assert data["latest_close_rial"] > 0
    print(data)