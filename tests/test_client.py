import pytest
from unittest.mock import patch, MagicMock
from amazon_sp_api.wrapper import auth, invoices, SPAPIError, RateLimitExceededError


def test_auth_initialization():
    client = auth(access_token='fake_token', region='na')
    assert client.endpoint == 'https://sellingpartnerapi-na.amazon.com'
    assert client.access_token == 'fake_token'


def test_invalid_region():
    with pytest.raises(ValueError):
        auth(access_token='fake', region='invalid')


def test_all_regions():
    for region, expected_url in [
        ('na', 'https://sellingpartnerapi-na.amazon.com'),
        ('eu', 'https://sellingpartnerapi-eu.amazon.com'),
        ('fe', 'https://sellingpartnerapi-fe.amazon.com'),
    ]:
        client = auth(access_token='fake', region=region)
        assert client.endpoint == expected_url


def test_request_returns_response_on_200():
    client = auth(access_token='fake_token', region='na')
    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch('requests.get', return_value=mock_response) as mock_get:
        result = client.request("GET", url="https://example.com")
        assert result == mock_response
        mock_get.assert_called_once()


def test_request_returns_none_on_404():
    client = auth(access_token='fake_token', region='na', print_error=False)
    mock_response = MagicMock()
    mock_response.status_code = 404

    with patch('requests.get', return_value=mock_response):
        result = client.request("GET", url="https://example.com")
        assert result is None


def test_request_returns_none_on_403():
    client = auth(access_token='fake_token', region='na', print_error=False)
    mock_response = MagicMock()
    mock_response.status_code = 403

    with patch('requests.get', return_value=mock_response):
        result = client.request("GET", url="https://example.com")
        assert result is None


def test_request_retries_on_429_and_raises():
    client = auth(access_token='fake_token', region='na', print_error=False)
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.headers = {}

    with patch('requests.get', return_value=mock_response), \
         patch('amazon_sp_api.wrapper.sleep') as mock_sleep:
        with pytest.raises(RateLimitExceededError):
            client.request("GET", url="https://example.com")
        # deve ter dormido _MAX_RETRIES vezes (backoff: 1s, 2s, 4s)
        assert mock_sleep.call_count == client._MAX_RETRIES


def test_request_retry_succeeds_after_429():
    client = auth(access_token='fake_token', region='na', print_error=False)

    mock_429 = MagicMock()
    mock_429.status_code = 429
    mock_429.headers = {}

    mock_200 = MagicMock()
    mock_200.status_code = 200

    with patch('requests.get', side_effect=[mock_429, mock_200]), \
         patch('amazon_sp_api.wrapper.sleep'):
        result = client.request("GET", url="https://example.com")
        assert result == mock_200


def test_invoices_inherits_auth():
    inv = invoices(access_token='fake_token', region='eu')
    assert isinstance(inv, auth)
    assert inv.endpoint == 'https://sellingpartnerapi-eu.amazon.com'


def test_get_invoices_builds_correct_url():
    inv = invoices(access_token='fake_token', region='na')
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"invoices": []}

    with patch('requests.get', return_value=mock_response) as mock_get:
        result = inv.get_invoices('A2Q3Y263D00KWC', dateStart='2026-01-01', dateEnd='2026-01-07')
        called_url = mock_get.call_args[1]['url'] if 'url' in mock_get.call_args[1] else mock_get.call_args[0][0]
        assert '/tax/invoices/2024-06-19/invoices' in called_url
        assert result == {"invoices": []}


def test_get_invoices_returns_empty_dict_on_failure():
    inv = invoices(access_token='fake_token', region='na', print_error=False)
    mock_response = MagicMock()
    mock_response.status_code = 403

    with patch('requests.get', return_value=mock_response):
        result = inv.get_invoices('A2Q3Y263D00KWC')
        assert result == {}


def test_get_invoice_document_builds_correct_url():
    inv = invoices(access_token='fake_token', region='na')
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"documentId": "abc123"}

    with patch('requests.get', return_value=mock_response) as mock_get:
        result = inv.get_invoice_document('abc123')
        called_url = mock_get.call_args[1]['url'] if 'url' in mock_get.call_args[1] else mock_get.call_args[0][0]
        assert '/tax/invoices/2024-06-19/documents/abc123' in called_url
        assert result == {"documentId": "abc123"}

